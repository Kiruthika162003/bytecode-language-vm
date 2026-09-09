"""Coverage: which lines of a program actually ran, and which only compiled.

Coverage is measured here without adding anything to the machine, which is the point
worth explaining. The profiler already records the source line of every instruction it
dispatches, so the set of lines that ran is a by-product of running with profiling on,
and the only new work is establishing what the denominator should be. That comes from
the other side of the compiler: a chunk's line table names the line of every
instruction it holds, so walking the tables of a function and every function nested in
its constant pool gives every line the compiler emitted code for. Coverage is then the
difference between two sets that both come from information already lying around.

The denominator is the honest part and needs stating carefully, because a coverage
figure is only as meaningful as what it divides by. A line the compiler emitted no
instruction for is not counted as missed, and there are several such lines in a normal
program: a closing brace, a blank line, a comment, and a function declaration whose
line contributes only the instruction that creates the closure. This means the figure
here is coverage of emitted code rather than coverage of source text, and it will read
higher than a tool that counts every line of the file. The alternative would be to
count lines the compiler never emits and report them permanently missed, which would
make full coverage unreachable and the number useless.

One consequence is worth knowing before trusting a hundred percent. A line holding two
statements is one line, so covering either covers both, and a conditional expression
whose two arms sit on one line reports covered when only one arm ran. Line coverage
cannot see inside a line: that needs branch coverage, which needs the graph rather
than the line table, and this module deliberately measures the cheaper thing and says
which one it measured rather than implying the stronger claim.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ember.builtins import install_builtins
from ember.function import Function
from ember.interpreter import build
from ember.vm import VM


def lines_in(function: Function) -> set[int]:
    """Every line the compiler emitted an instruction for, nested functions included."""
    found = {line for line, _ in function.chunk.line_runs}
    for constant in function.chunk.constants:
        if isinstance(constant, Function):
            found |= lines_in(constant)
    return found


@dataclass
class Report:
    """What ran, what did not, and the share of emitted lines that did."""

    executable: set[int] = field(default_factory=set)
    covered: set[int] = field(default_factory=set)

    @property
    def missed(self) -> set[int]:
        return self.executable - self.covered

    @property
    def share(self) -> float:
        if not self.executable:
            # nothing to cover is complete coverage rather than a division by zero
            return 1.0
        return len(self.covered & self.executable) / len(self.executable)

    @property
    def percentage(self) -> int:
        return round(self.share * 100)

    @property
    def complete(self) -> bool:
        return not self.missed

    def summary(self) -> str:
        return (
            f"{len(self.covered & self.executable)} of {len(self.executable)} emitted "
            f"lines ran, which is {self.percentage} percent"
        )

    def render(self, source: str | None = None) -> list[str]:
        lines = [self.summary()]
        if self.complete:
            return lines
        listed = ", ".join(str(line) for line in sorted(self.missed))
        lines.append(f"lines that never ran: {listed}")
        if source is not None:
            text = source.splitlines()
            for line in sorted(self.missed):
                if 1 <= line <= len(text):
                    lines.append(f"  {line}: {text[line - 1].strip()}")
        return lines


def measure(source: str, optimize: bool = False, peephole: bool = False) -> Report:
    """Run a program with profiling on and compare the lines it hit against the rest."""
    function = build(source, optimize=optimize, peephole=peephole)
    machine = VM()
    install_builtins(machine)
    profile = machine.enable_profiling()
    machine.interpret(function)
    return Report(
        executable=lines_in(function),
        covered={line for line, _ in profile.by_line()},
    )


def measure_function(machine: VM, function: Function) -> Report:
    """Coverage of one already compiled function, using a machine already prepared."""
    profile = machine.enable_profiling()
    machine.interpret(function)
    return Report(
        executable=lines_in(function),
        covered={line for line, _ in profile.by_line()},
    )


def uncovered_source(source: str) -> list[str]:
    """The text of every emitted line that never ran, for a person to read."""
    report = measure(source)
    text = source.splitlines()
    return [
        text[line - 1].strip()
        for line in sorted(report.missed)
        if 1 <= line <= len(text)
    ]
