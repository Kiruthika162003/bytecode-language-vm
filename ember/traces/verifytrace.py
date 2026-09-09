"""The verifier measured against the compiler: nothing it emits is ever unsafe.

A verifier is only worth having if the code it guards passes it, and the way to
show that is to run every construct the language has through the compiler and
insist the verifier finds no fault in any of them. This trace does that across a
corpus covering arithmetic, blocks, branches, both loops, closures, classes with
inheritance and super, exceptions with handlers, match, interpolation and calls
with defaults, and it repeats the whole corpus after each optimiser and after both
together, because an optimiser that produced unverifiable bytecode would be a
worse bug than the one it fixed. The second number is the more interesting one.
The corpus does carry unreachable instructions, and they are real: the compiler
ends every function with a nil-and-return epilogue that a body already returning
on every path can never reach. The peephole pass deletes them, and this trace is
where that shows as a number rather than an assertion, because the count of
unreachable reports falls from thirteen to one while the count of faults stays at
zero throughout. That is the honest shape of the result: the compiler emits safe
bytecode that is slightly wasteful, and the peephole pass is what removes the
waste, so unreachable code is recorded as a warning rather than treated as an
error.
"""

from __future__ import annotations

from ember.interpreter import build
from ember.traces.finding import Finding
from ember.verifier import faults_deeply, warnings_deeply

NAME = "verify"

CORPUS = (
    "print 1 + 2 * 3;",
    "let x = 1; x = 2; print x;",
    "{ let a = 1; let b = 2; print a + b; }",
    'if (1 < 2) print "a"; else print "b";',
    "let n = 0; while (n < 3) { n = n + 1; if (n == 2) break; } print n;",
    "let s = 0; for (let i = 0; i < 5; i = i + 1) s = s + i; print s;",
    "for (x in [1, 2, 3]) { if (x == 2) continue; print x; }",
    "fn fib(n) { if (n < 2) return n; return fib(n-1) + fib(n-2); } print fib(10);",
    "fn make() { let c = 0; fn inc() { c = c + 1; return c; } return inc; } print make()();",
    "class A { init(x) { this.x = x; } m() { return this.x * 2; } } print A(3).m();",
    "class A { m() { return 1; } } class B < A { m() { return super.m()+1; } } print B().m();",
    'try { throw "x"; } catch (e) { print e; }',
    'try { print 1 / 0; } catch (e) { print "caught"; } print "after";',
    'fn f() { try { return "a"; } catch (e) { return "b"; } } print f();',
    'for (i in [1, 2]) { try { if (i == 2) break; print i; } catch (e) { } }',
    'match (2) { case 1: print "a"; case 2, 3: print "b"; default: print "c"; }',
    'let m = {"a": 1}; m["b"] = 2; print m["a"]; print len(m);',
    'let name = "ada"; print "hi ${name}, ${1 + 2}";',
    "print 12 & 10 | 3; print ~5; print 1 << 3;",
    'print 1 > 0 ? "y" : "n";',
    "fn f(a, b = 2, ...rest) { return a + b + len(rest); } print f(1); print f(1, 2, 3);",
    "fn dbl(n) { return n * 2; } print map([1, 2, 3], dbl);",
)

_SETTINGS = ((False, False), (True, False), (False, True), (True, True))


def _totals(optimize: bool, peephole: bool) -> tuple[int, int]:
    faulted = 0
    warned = 0
    for source in CORPUS:
        function = build(source, optimize=optimize, peephole=peephole)
        faulted += len(faults_deeply(function))
        warned += len(warnings_deeply(function))
    return faulted, warned


def run() -> Finding:
    counts = {setting: _totals(*setting) for setting in _SETTINGS}
    faults_everywhere = all(faulted == 0 for faulted, _ in counts.values())
    plain = counts[(False, False)][1]
    swept = counts[(False, True)][1]
    holds = faults_everywhere and plain == 13 and swept == 1
    claim = (
        f"every one of {len(CORPUS)} programs verifies without a fault, before and "
        f"after both optimisers, and the {plain} unreachable instructions the "
        f"compiler leaves behind fall to {swept} once the peephole pass has run"
    )
    return Finding(NAME, claim, holds)
