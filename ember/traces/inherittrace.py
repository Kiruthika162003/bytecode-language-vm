"""Inheritance measured: a super chain three classes deep, each level adding one.

The risk with copying a superclass's methods into a subclass, which is what
this runtime does, is that super would then find the copy rather than the
original and a chain of overrides would either loop or stop early. This
trace builds three classes where each override adds one to the result of
the level above, so the answer is a direct count of how many levels were
actually traversed: one, two, three. Anything less than three would mean a
level was skipped, and anything that hangs would mean super found the method
it was called from. The trace also checks that the base class still answers
one, since flattening methods into subclasses must not disturb the class
they were copied from, and that an instance of the deepest subclass reports
its own type rather than an ancestor's, which is what confirms the copying
did not blur the classes together.
"""

from __future__ import annotations

from ember.interpreter import run_output
from ember.traces.finding import Finding

NAME = "inherit"
SOURCE = (
    "class A { m() { return 1; } }"
    " class B < A { m() { return super.m() + 1; } }"
    " class C < B { m() { return super.m() + 1; } }"
    " print A().m(); print B().m(); print C().m(); print type(C());"
)


def run() -> Finding:
    output = run_output(SOURCE)
    holds = output == ["1", "2", "3", "C"]
    claim = (
        f"a super chain three deep counts every level, {output[0]} then "
        f"{output[1]} then {output[2]}, the base class still answering "
        f"{output[0]} after its methods were copied down, and the deepest "
        f"instance reporting its own type {output[3]!r}"
    )
    return Finding(NAME, claim, holds)
