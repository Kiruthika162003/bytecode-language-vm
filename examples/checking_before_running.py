"""The four checks a program can face before it runs, and what each one catches.

A program can be wrong in several ways, and this project has grown a separate
check for each. The point of putting them side by side is that they catch
genuinely different things: a program can pass all four and still be wrong, and
a program failing one usually passes the others. Running them together on the
same handful of programs makes the division of labour concrete in a way reading
their docstrings does not.

The verifier asks whether the bytecode is well formed, which is a question about
the compiler rather than about the program: the answer is always yes for anything
this compiler emits, and the reason to have it is bytecode arriving from anywhere
else. The type checker asks whether the program contains an operation that must
fault, which is a question about the source, and it is silent about anything
involving a function parameter because a parameter has no declared type. The
linter asks whether the program says something a reader would question, which is
advice rather than error. And the graph asks which of its own instructions can
never run, which is a question about the compiler again and which the block pass
now answers by removing them.

What the example shows is that the four rarely overlap. The program with a type
mistake verifies cleanly, because a mistake that will fault at run time is still
well formed bytecode. The program with an unused local passes the type checker,
because an unused local is not a type error. And the dead epilogue every function
carries is invisible to all three of the others, because it is a fact about the
compiler that no reading of the source would reveal.

The honest limit is worth stating alongside the table, because four green columns
read like a guarantee and are not one. None of the four knows what the program was
meant to compute, so the one kind of wrongness that matters most is the one kind
none of them can see. What they buy is narrower than it looks: they cost a fraction
of a second and they rule out four specific families of mistake, which is worth
having precisely because it is cheap, not because it is complete.
"""

from __future__ import annotations

from ember.analyzer import analyze
from ember.blockopt import optimise_deeply
from ember.cfg import graph_of
from ember.function import Function
from ember.interpreter import build
from ember.parser import parse
from ember.scanner import scan
from ember.typecheck import check
from ember.verifier import faults_deeply, warnings_deeply

PROGRAMS = {
    "clean": "fn add(a, b) { return a + b; } print add(1, 2);",
    "type mistake": 'let name = "ada"; print name - 1;',
    "wrong arity": "fn add(a, b) { return a + b; } print add(1);",
    "unused local": "fn f(a) { let scratch = 1; return a; } print f(1);",
    "always returns": "fn f() { return 1; } print f();",
    "dead branch": 'if (false) { print "never"; } print "after";',
}


def _dead_blocks(source: str) -> int:
    """Every unreachable block in the tree, not only in the script.

    Counting the script alone reported nothing for the program whose dead code is
    the whole point, because the epilogue that can never run sits inside the
    function rather than beside it.
    """
    def walk(one: Function) -> int:
        found = len(graph_of(one).unreachable())
        for constant in one.chunk.constants:
            if isinstance(constant, Function):
                found += walk(constant)
        return found

    return walk(build(source))


def _dead_after_the_pass(source: str) -> int:
    function = build(source)
    optimise_deeply(function)
    return len(warnings_deeply(function))


def main() -> None:
    print("what each check finds, over the same programs")
    print()
    header = f"{'verifier':>9}  {'types':>6}  {'lint':>5}  {'dead':>5}   program"
    print(header)
    print("-" * len(header))
    for label, source in PROGRAMS.items():
        faults = len(faults_deeply(build(source)))
        mistakes = len(check(source))
        advice = len(analyze(parse(scan(source))))
        dead = _dead_blocks(source)
        print(f"{faults:>9}  {mistakes:>6}  {advice:>5}  {dead:>5}   {label}")
    print()
    print("the verifier finds no fault anywhere, which is the claim it exists to make:")
    print("everything this compiler emits is well formed, and the check is there for")
    print("bytecode that came from somewhere else")
    print()
    print("the checks do not overlap:")
    for label, source in PROGRAMS.items():
        mistakes = len(check(source))
        advice = len(analyze(parse(scan(source))))
        if mistakes and not advice:
            print(f"  {label} has a type mistake and nothing a linter would question")
        if advice and not mistakes:
            print(f"  {label} has something a reader would question and no type mistake")
    print()
    print("and the dead code none of them look at:")
    for label, source in PROGRAMS.items():
        before = _dead_blocks(source)
        after = _dead_after_the_pass(source)
        if before:
            print(f"  {label}: {before} unreachable blocks, {after} after the block pass")
    print()
    print("a program can pass every check and still be wrong: not one of them knows")
    print("what the program was supposed to compute, which is the limit of all four")


if __name__ == "__main__":
    main()
