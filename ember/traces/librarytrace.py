"""The library measured against itself: every registered name reaches the machine, once.

A standard library assembled from thirty separate registries has two failure modes that no test
of any one library can see, because both are about the relationship between them. A name two
libraries register is installed twice, and whichever installs last wins silently, leaving a
function that has quietly been replaced by another with its name. And a name a library registers
but the machine never receives means a library was written and never wired in, which is equally
invisible from inside that library, where its own registry looks complete.

Both were real rather than hypothetical. The first run of the generated reference found two
collisions: the text library had redefined repeating a string and splitting one into
lines, and the core string library already provided both. The two versions of splitting
into lines did not agree about a carriage return before a newline, so adding the text
library had quietly changed how programs split text written on another system, and every
test of both libraries passed throughout. That is precisely the kind of fault a trace is
for: nothing failed, and something was wrong.

So this trace holds when three counts are as they should be. No name is claimed by two
libraries. Every name a library registers is a name the machine has. And the total is the
sum of the libraries, which catches a library listed in the reference but silently empty.
The numbers are reported rather than only checked, because the size of the library is
itself worth knowing and nobody has counted it by hand since it was small.
"""

from __future__ import annotations

from ember.builtins import builtin_names
from ember.manual import missing_from_machine, reference, unlisted
from ember.traces.finding import Finding

NAME = "library"


def run() -> Finding:
    found = reference()
    collisions = len(found.collisions)
    unwired = len(missing_from_machine())
    listed = {name for names in found.libraries.values() for name in names}
    accounted = listed | set(unlisted()) == set(builtin_names())
    empty = [library for library, names in found.libraries.items() if not names]
    holds = collisions == 0 and unwired == 0 and accounted and not empty
    claim = (
        f"the {found.total} functions across {found.library_count} libraries are each "
        f"registered by exactly one of them, {collisions} names being claimed twice, "
        f"every one reaches the machine, {unwired} being registered and never installed, "
        f"and the libraries together with the {len(unlisted())} the core supplies account "
        "for every name a program can call"
    )
    return Finding(NAME, claim, holds)
