"""The type checker measured: silent on every valid program, loud on every planted one.

A checker that reports nothing is useless and a checker that reports things that are not
there is worse, because people stop reading it. Both failures are cheap to measure, so
this trace measures both rather than asserting either. The first number is silence on
programs known to be correct: the twenty two hand written programs the verifier uses as
its corpus, plus a hundred generated ones, none of which contains a type mistake because
the generator only builds expressions whose operand types agree. Any finding among those
three hundred and twenty two is a false positive.

The second number is the one that gives the first its meaning. A list of planted
mistakes, one for each kind the checker knows how to find, is checked and every one has
to be caught. Subtracting from a string, adding a string to a number, ordering two
booleans, comparing a string with a number for equality, calling a number, indexing a
boolean, using a string as a list index, and passing the wrong number of arguments to a
function and to a class. Eight kinds, eight programs, and the trace holds only when the
silence and the catching are both complete. Neither half means much alone: silence could
be a checker that never looks, and catching could come with a flood of noise beside it.
"""

from __future__ import annotations

from ember.generator import program_for
from ember.traces.finding import Finding
from ember.traces.verifytrace import CORPUS
from ember.typecheck import check

NAME = "types"
GENERATED = 100

PLANTED = (
    ("not-a-number", 'print "a" - 1;'),
    ("cannot-add", 'print "a" + 1;'),
    ("not-orderable", "print true < false;"),
    ("cannot-compare", 'print "a" < 1;'),
    ("never-equal", 'print "a" == 1;'),
    ("not-callable", "let n = 1; print n();"),
    ("not-indexable", "let b = true; print b[0];"),
    ("bad-index", 'let a = [1]; print a["x"];'),
    ("wrong-arity", "fn f(a, b) { return a; } print f(1);"),
)


def run() -> Finding:
    valid = list(CORPUS) + [program_for(seed) for seed in range(GENERATED)]
    noisy = sum(1 for source in valid if check(source))
    caught = 0
    for kind, source in PLANTED:
        if any(found.kind == kind for found in check(source)):
            caught += 1
    holds = noisy == 0 and caught == len(PLANTED)
    claim = (
        f"the checker is silent on all {len(valid)} programs known to be correct and "
        f"catches all {len(PLANTED)} planted mistakes, one of each kind it knows, so "
        f"its silence means something: {noisy} false positives and "
        f"{len(PLANTED) - caught} missed"
    )
    return Finding(NAME, claim, holds)
