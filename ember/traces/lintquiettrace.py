"""The analyzer measured: silence on good code is the property that matters.

A linter is judged by its false positives, not by its catches. A rule that fires
on reasonable code gets the whole tool switched off, and then the rules that were
right go unheard along with it. So the claim this trace makes is mostly about
silence: six programs written the way the language intends, including a closure
factory, a loop that breaks out of a while-true, an underscore-prefixed binding
that exists on purpose, and a try with a catch, must produce no diagnostics at
all. Against that it checks one program that deserves two, an unread local and an
unread parameter, to confirm the rules still fire when they should. The closure
program is in the quiet set deliberately, because it is exactly where this
analyzer was once wrong: a captured variable is read inside a nested function, and
searching only the innermost function's scopes reported every closure's variable
as unused. That was a false positive on the most ordinary closure there is, which
is why the quiet set is the part of this trace worth trusting.
"""

from __future__ import annotations

from ember.analyzer import analyze
from ember.parser import parse
from ember.scanner import scan
from ember.traces.finding import Finding

NAME = "lint-quiet"

QUIET = (
    "fn add(a, b) { return a + b; } print add(1, 2);",
    "{ let x = 1; print x; }",
    "fn outer() { let c = 0; fn inc() { c = c + 1; return c; } return inc; }"
    " print outer()();",
    "let n = 0; while (true) { n = n + 1; if (n > 2) break; } print n;",
    "{ let _deliberate = 1; print 2; }",
    'try { throw "x"; } catch (e) { print e; }',
)

NOISY = "fn f(a, b) { let scratch = 1; return a; } print f(1, 2);"


def run() -> Finding:
    counts = [len(analyze(parse(scan(source)))) for source in QUIET]
    noisy = analyze(parse(scan(NOISY)))
    kinds = sorted(diagnostic.kind for diagnostic in noisy)
    holds = (
        counts == [0] * len(QUIET)
        and len(noisy) == 2
        and kinds == ["unused-local", "unused-parameter"]
    )
    claim = (
        f"{len(QUIET)} programs written the way the language intends draw "
        f"{sum(counts)} diagnostics between them, including the closure factory "
        "that once reported its captured variable as unused, while a function with "
        f"an unread local and an unread parameter still draws exactly {len(noisy)}"
    )
    return Finding(NAME, claim, holds)
