"""The same program run two ways, and what the comparison is and is not worth.

This runtime has two independent implementations of one language: a compiler
with a stack machine, and an interpreter that walks the tree. Running the same
program through both and demanding identical output is the strongest evidence in
the repository that either is correct, because a bug would have to be present in
both, in the same direction, to escape it. This example does that on a handful
of programs and then reports what each backend counted while doing it. The
counts are where care is needed. The machine reports instructions dispatched and
the tree-walker reports nodes visited, and those are different units of work, so
their ratio is not a speed ratio and this example refuses to present it as one.
What the numbers do show is that both are doing work of the same order on the
same program, which is the honest claim. The example ends on the limit of the
whole technique: agreement is not proof. Both backends could be wrong the same
way about something neither program here exercises, which is why the shared set
grows whenever a feature is added rather than being treated as finished.
"""

from __future__ import annotations

from ember.interpreter import run, run_treewalk

PROGRAMS = (
    ("arithmetic", "print 1 + 2 * 3 - 4 / 2;"),
    ("a counting loop", "let s = 0; for (let i = 0; i < 20; i = i + 1) s = s + i; print s;"),
    (
        "recursion",
        "fn fib(n) { if (n < 2) return n; return fib(n-1) + fib(n-2); } print fib(12);",
    ),
    (
        "a closure",
        "fn make() { let c = 0; fn inc() { c = c + 1; return c; } return inc; }"
        " let g = make(); g(); g(); print g();",
    ),
    (
        "inheritance",
        "class A { m() { return 1; } } class B < A { m() { return super.m() + 1; } }"
        " print B().m();",
    ),
    ("iteration", "let t = 0; for (x in [1, 2, 3, 4]) t = t + x; print t;"),
)


def main() -> None:
    print("running each program through both backends")
    print()
    agreements = 0
    for label, source in PROGRAMS:
        machine = run(source)
        walker = run_treewalk(source)
        agrees = machine.output == walker.output
        agreements += 1 if agrees else 0
        verdict = "agree" if agrees else "DISAGREE"
        print(f"{label}:")
        print(f"  both printed {machine.output} ({verdict})")
        print(f"  machine dispatched {machine.instruction_count} instructions, "
              f"peak stack {machine.max_stack}")
        print(f"  tree-walker visited {walker.steps} nodes")

    print()
    print(f"agreement: {agreements} of {len(PROGRAMS)} programs")
    print()
    print("what the two counts do not say:")
    print("  an instruction and a tree node are different units of work, so the")
    print("  ratio between these numbers is not a speed ratio and is not reported")
    print("  as one; what they show is effort of the same order on the same program")
    print()
    print("and the limit of agreement itself:")
    print("  agreement is not proof. both backends could be wrong the same way")
    print("  about something no program here exercises, so the shared set grows")
    print("  whenever a feature lands rather than being treated as finished")


if __name__ == "__main__":
    main()
