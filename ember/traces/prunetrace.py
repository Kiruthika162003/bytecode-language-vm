"""Dead code measured: what a branch guarded by a compile-time falsehood costs.

The interesting property of removing an unreachable branch is not that the
output gets a little smaller but that the branch's contents leave the
program completely. This trace guards three prints behind a literal
falsehood and measures both the bytes and the constant pool. The pool is
the honest witness: if the strings inside the dead branch were still listed
there, the branch would only have been jumped over, not removed, and the
program would still be carrying them. After pruning the pool holds only the
string that can actually print, so the cost of the dead branch is nothing
rather than a jump. The trace pairs that with the surviving output, because
a pass that removes the wrong arm would also shrink the program and would
be a bug rather than an optimisation, and comparing the two runs is what
separates those cases.
"""

from __future__ import annotations

from ember.interpreter import build, run_output
from ember.traces.finding import Finding

NAME = "prune"
SOURCE = 'if (false) { print "a"; print "b"; print "c"; } print "d";'


def run() -> Finding:
    plain = build(SOURCE, optimize=False).chunk
    tight = build(SOURCE, optimize=True).chunk
    plain_output = run_output(SOURCE, optimize=False)
    tight_output = run_output(SOURCE, optimize=True)
    dead_strings = [name for name in ("a", "b", "c") if name in tight.constants]
    holds = (
        len(plain.code) == 23
        and len(tight.code) == 5
        and len(plain.constants) == 4
        and len(tight.constants) == 1
        and dead_strings == []
        and plain_output == tight_output == ["d"]
    )
    claim = (
        f"a branch behind a compile-time falsehood costs nothing: {len(plain.code)} "
        f"bytes and {len(plain.constants)} constants become {len(tight.code)} and "
        f"{len(tight.constants)}, all {3 - len(dead_strings)} unreachable strings "
        f"leaving the pool entirely, and both forms print {tight_output[0]!r}"
    )
    return Finding(NAME, claim, holds)
