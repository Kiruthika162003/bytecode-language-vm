"""Two backends measured: how many programs the compiled and walked forms agree on.

Having two independent implementations of one language is only valuable if
they are held to each other, so this trace sweeps a set of programs covering
arithmetic, control flow, collections, closures, classes, inheritance, and
the standard library, runs each through both the bytecode machine and the
tree-walker, and counts the agreements. The count is the claim. Agreement is
compared on printed output rather than on any internal state, because output
is the only thing the language promises and the two backends differ
completely inside; the tree-walker has no chunks and the machine has no
environments. This is the strongest evidence in the repository that either
backend is correct, because a bug would have to be present in both, in the
same direction, to escape it. The honest limit is that agreement is not
proof: both could be wrong the same way about something neither program in
this set exercises, which is why the set grows whenever a feature is added
rather than being treated as finished.
"""

from __future__ import annotations

from ember.interpreter import run_output, run_treewalk_output
from ember.traces.finding import Finding

NAME = "agree"

PROGRAMS = (
    "print 1 + 2 * 3 - 4 / 2;",
    "print 17 % 5; print -(-5); print not false;",
    'print "a" + "b"; print len("hello");',
    'if (2 > 3) print "a"; else print "b";',
    "let s = 0; for (let i = 0; i < 6; i = i + 1) s = s + i; print s;",
    "let n = 3; while (n > 0) { print n; n = n - 1; }",
    "fn fib(n) { if (n < 2) return n; return fib(n-1) + fib(n-2); } print fib(12);",
    "let a = [3, 1, 2]; a[0] = 9; print a; print sorted([3, 1, 2]); print sum(a);",
    'let m = {"x": 1}; m["y"] = 2; print keys(m); print m["y"];',
    "fn make() { let c = 0; fn inc() { c = c + 1; return c; } return inc; }"
    " let g = make(); print g(); print g();",
    "fn adder(n) { fn add(x) { return x + n; } return add; } print adder(5)(3);",
    "class P { init(x, y) { this.x = x; this.y = y; } sum() { return this.x + this.y; } }"
    " print P(3, 4).sum();",
    "class A { m() { return 1; } } class B < A { m() { return super.m() + 1; } }"
    " print B().m(); print type(B());",
    'class S { name() { return "m"; } } let s = S(); print s.name(); s.name = "f";'
    " print s.name;",
    "print pow(2, 8); print gcd(24, 18); print factorial(6); print clamp(20, 0, 9);",
)


def run() -> Finding:
    agreements = 0
    for source in PROGRAMS:
        if run_output(source) == run_treewalk_output(source):
            agreements += 1
    holds = agreements == len(PROGRAMS)
    claim = (
        f"the compiled and walked backends agree on {agreements} of "
        f"{len(PROGRAMS)} programs spanning arithmetic, control flow, "
        "collections, closures, classes, inheritance, and the library, compared "
        "on printed output alone since that is all the language promises"
    )
    return Finding(NAME, claim, holds)
