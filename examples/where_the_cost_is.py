"""Two ways to compute one answer, measured in instructions rather than in seconds.

Everyone knows the recursive Fibonacci is slow and the iterative one is fast, and
almost nobody has a number for how slow. This example produces one, and the number
is exact rather than approximate: instructions dispatched by the machine, which is
the same on every run and on every computer, so the comparison is a fact about the
two programs rather than about the afternoon they were measured on.

The gap is larger than most people expect. The recursive form recomputes the same
values over and over, so its cost grows with the answer rather than with the input,
and by the fifteenth term it dispatches something like sixty times what the loop
does. Printing the ratio at several inputs shows the shape of that: the loop grows
in a straight line and the recursion does not, which is visible in three columns of
numbers in a way it is not visible in the source.

The example ends on the thing counting instructions cannot tell you. A third version
computes the same answer using a native that does the work in one instruction, and
it shows the fewest instructions of the three while doing the most work per
instruction. That is the honest limit of this measurement: it counts what the machine
dispatched, and a single dispatch can be a whole sort. Anything about elapsed time
needs a clock, and a clock measures the machine as much as the program.
"""

from __future__ import annotations

from ember.benchlib import compare, measure

RECURSIVE = "fn fib(n) { if (n < 2) return n; return fib(n-1) + fib(n-2); } print fib(%d);"
ITERATIVE = (
    "let a = 0; let b = 1;"
    " for (let i = 0; i < %d; i = i + 1) { let t = a + b; a = b; b = t; }"
    " print a;"
)
INPUTS = (5, 8, 11, 14, 17)


def main() -> None:
    print("two ways to reach the same answer, counted in instructions")
    print()
    header = f"{'n':>3}  {'recursive':>11}  {'iterative':>11}  {'ratio':>7}  answer"
    print(header)
    print("-" * len(header))
    for n in INPUTS:
        one = measure(RECURSIVE % n, "recursive")
        other = measure(ITERATIVE % n, "iterative")
        ratio = one.instructions / other.instructions
        agreed = "same" if one.output == other.output else "DIFFERENT"
        print(
            f"{n:>3}  {one.instructions:>11}  {other.instructions:>11}  "
            f"{ratio:>7.1f}  {agreed}"
        )
    print()
    print("the loop grows in a straight line and the recursion does not, which is why")
    print("the ratio grows rather than staying put")
    print()
    biggest = INPUTS[-1]
    for line in compare(
        RECURSIVE % biggest, ITERATIVE % biggest, ("recursive", "iterative")
    ).render():
        print(line)
    print()
    print("the stack tells the same story from the other side:")
    for n in (5, 11, 17):
        one = measure(RECURSIVE % n)
        other = measure(ITERATIVE % n)
        print(
            f"  n={n:<3} recursive reaches {one.stack_high_water} deep, "
            f"iterative reaches {other.stack_high_water}"
        )
    print()
    print("and what counting instructions cannot tell you:")
    building = "let a = [];" + chr(10)
    building += "for (let i = 0; i < 300; i = i + 1) { a = push(a, 300 - i); }" + chr(10)
    by_hand = building + "print len(a);"
    by_native = building + "print len(ordered(a));"
    without = measure(by_hand, "without sorting")
    with_sort = measure(by_native, "with sorting")
    print(f"  {without.render()}")
    print(f"  {with_sort.render()}")
    extra = with_sort.instructions - without.instructions
    print(f"  sorting three hundred values cost {extra} more instructions")
    print("  because the sort is one instruction that does a great deal of work, which")
    print("  is exactly why this count is not a measure of time")


if __name__ == "__main__":
    main()
