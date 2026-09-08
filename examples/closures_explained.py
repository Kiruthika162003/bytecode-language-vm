"""A counter factory, and the indirection that lets a variable outlive its frame.

The hard part of closures is not that a function can be returned but that the
variable it uses has to survive the call that declared it. This example makes
that concrete. A factory declares a local, returns an inner function that reads
and writes it, and then the factory returns, which destroys its slice of the
value stack. The counters keep working anyway, and the example reaches into the
closure to show why: the upvalue behind each one has been closed, meaning the
value was copied out of the stack slot before that slot vanished. It also shows
the two properties that make closures useful rather than merely possible. Two
counters from one factory advance independently, because each instantiation gets
its own upvalue while sharing one compiled body. And two functions closing over
the same variable share a single upvalue, so incrementing through one is visible
through the other; if each held a copy, a reader and a writer over the same
counter would disagree. The example ends on the cost this buys with: every access
to a captured variable pays an indirection that a plain local does not, which is
the price of letting a variable outlive the frame it was declared in.
"""

from __future__ import annotations

from ember.interpreter import run

FACTORY = "fn make() { let c = 0; fn inc() { c = c + 1; return c; } return inc; }"


def main() -> None:
    print("two counters from one factory")
    machine = run(
        FACTORY + " let a = make(); let b = make();"
        " print a(); print a(); print a(); print b();"
    )
    print(f"  a() three times, then b() once: {machine.output}")
    first = machine.globals["a"]
    second = machine.globals["b"]
    print(f"  they share one compiled body: {first.function is second.function}")
    print(f"  they hold different upvalues: {first.upvalues[0] is not second.upvalues[0]}")

    print()
    print("the factory has already returned, so where does the variable live?")
    print(f"  a's upvalue is closed: {first.upvalues[0].is_closed}")
    print("  closed means the value was copied out of the stack slot before that")
    print("  slot disappeared, so the closure owns it now rather than pointing at it")

    print()
    print("two functions over one variable must share it")
    shared = run(
        "fn pair() { let n = 0;"
        " fn up() { n = n + 1; return n; }"
        " fn get() { return n; }"
        " up(); up(); up(); return get(); }"
        " print pair();"
    )
    print(f"  three increments through one, then read through the other: {shared.output}")
    print("  a copy each would have read 0 here, so the sharing is what is measured")

    print()
    print("capture reaches through nesting, not just one level")
    deep = run(
        "fn outer() { let x = 7;"
        " fn mid() { fn inner() { return x; } return inner(); } return mid(); }"
        " print outer();"
    )
    print(f"  inner reads outer's local through mid: {deep.output}")

    print()
    print("what it costs:")
    print("  every read of a captured variable goes through the upvalue, one hop")
    print("  more than a plain local, which is indexed directly off the frame")
    print("  that hop is the price of outliving the frame, and it is not optional")


if __name__ == "__main__":
    main()
