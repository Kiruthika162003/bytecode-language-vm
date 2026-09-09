"""The test runner: execute a program's test functions and report which held.

A language people write real programs in needs a way to test them in the language
itself, and the cheapest such way that is still honest is a naming convention plus a
runner. Any top level function whose name begins with the word test is a test; the
runner calls each one with no arguments and decides the outcome from what happened. A
function that returns is a pass, a function that throws is a failure carrying the
thrown value, and a function that faults, dividing by zero or reading an unbound name,
is an error rather than a failure, because the distinction matters when reading a
report: a failure means the program under test behaved wrongly, an error usually means
the test itself is wrong.

The convention is deliberately a convention rather than syntax. Adding a test keyword
would mean touching the scanner, the parser, the compiler and both backends, and would
put a testing feature in the language's grammar forever, whereas a naming rule costs
nothing and can be replaced. The cost is real and worth stating: a function
accidentally named testTheWaters is a test whether its author meant it or not, and
there is no way to mark a test as expected to fail or to skip one.

Two decisions about running matter. Each test runs on a machine of its own, freshly
built from the same compiled program, so a test that leaves a global modified cannot
change what the next test sees; the alternative, sharing one machine, makes tests pass
or fail depending on their order, which is the failure mode that makes a suite
untrustworthy. And a test's printed output is captured and reported with its result
rather than discarded, because print is the language's only way to say anything and a
failing test's output is usually the most useful thing about it. Running each test
against its own machine means compiling once and interpreting many times, which is
slower than sharing, and the isolation is worth more than the speed at these sizes.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ember.builtins import install_builtins
from ember.errors import EmberError, Thrown
from ember.function import Function
from ember.interpreter import build
from ember.valueops import stringify
from ember.vm import VM

PASSED = "passed"
FAILED = "failed"
ERRORED = "errored"

_PREFIX = "test"


@dataclass
class Result:
    """What one test did: passed, failed by throwing, or errored by faulting."""

    name: str
    outcome: str
    detail: str = ""
    output: list[str] = field(default_factory=list)

    @property
    def held(self) -> bool:
        return self.outcome == PASSED

    def render(self) -> str:
        if self.outcome == PASSED:
            return f"{self.name}: passed"
        return f"{self.name}: {self.outcome}: {self.detail}"


@dataclass
class Suite:
    """Every test in a program and how each one turned out."""

    results: list[Result] = field(default_factory=list)

    @property
    def passed(self) -> list[Result]:
        return [result for result in self.results if result.outcome == PASSED]

    @property
    def failed(self) -> list[Result]:
        return [result for result in self.results if result.outcome == FAILED]

    @property
    def errored(self) -> list[Result]:
        return [result for result in self.results if result.outcome == ERRORED]

    @property
    def all_held(self) -> bool:
        return all(result.held for result in self.results)

    @property
    def count(self) -> int:
        return len(self.results)

    def summary(self) -> str:
        if not self.results:
            return "no tests found; a test is a function whose name begins with test"
        parts = [f"{len(self.passed)} passed"]
        if self.failed:
            parts.append(f"{len(self.failed)} failed")
        if self.errored:
            parts.append(f"{len(self.errored)} errored")
        return f"{self.count} tests: " + ", ".join(parts)

    def render(self) -> list[str]:
        lines = [result.render() for result in self.results]
        for result in self.results:
            if not result.held and result.output:
                lines.append(f"  what {result.name} printed before it stopped:")
                lines.extend("    " + printed for printed in result.output)
        lines.append(self.summary())
        return lines


def is_test_name(name: str) -> bool:
    """Whether a function's name marks it as a test, which is a convention not syntax."""
    return name.startswith(_PREFIX)


def _prepared(function: Function) -> VM:
    machine = VM()
    install_builtins(machine)
    # interpreting the script defines its globals, which is what makes the tests
    # reachable; every test gets its own machine so none can disturb another
    machine.interpret(function)
    return machine


def discover_tests(source: str) -> list[str]:
    """The names of every test in a program, in the order the machine holds them."""
    machine = _prepared(build(source))
    return [
        name
        for name, value in machine.globals.items()
        if is_test_name(name) and hasattr(value, "function")
    ]


def _run_one(function: Function, name: str) -> Result:
    machine = _prepared(function)
    callee = machine.globals[name]
    machine.output.clear()
    try:
        machine.call_value(callee, [])
    except Thrown as thrown:
        # a throw means the program under test behaved wrongly
        return Result(
            name=name,
            outcome=FAILED,
            detail=stringify(thrown.value),
            output=list(machine.output),
        )
    except EmberError as faulted:
        # a fault usually means the test itself is wrong
        return Result(
            name=name,
            outcome=ERRORED,
            detail=str(faulted),
            output=list(machine.output),
        )
    return Result(name=name, outcome=PASSED, output=list(machine.output))


def run_suite(source: str, optimize: bool = False, peephole: bool = False) -> Suite:
    """Compile once, then run each test on a machine of its own."""
    function = build(source, optimize=optimize, peephole=peephole)
    suite = Suite()
    for name in discover_tests(source):
        suite.results.append(_run_one(function, name))
    return suite


def report(source: str) -> list[str]:
    return run_suite(source).render()
