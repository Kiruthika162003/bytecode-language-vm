"""Constant folding measured: what an arithmetic expression costs before and after.

The claim folding makes is that work not depending on the program running
can be done once while compiling, and the way to check it is to compile the
same expression twice and compare what came out. The measurement is the
chunk: how many bytes of instructions and how many entries in the constant
pool. An arithmetic print with four literals and four operators compiles to
seventeen bytes and four constants unoptimised; folded, the whole
expression is one constant and its load, five bytes and one constant. The
number worth noticing is the constant pool, because it shows the operators
disappeared rather than merely shrinking: the intermediate values are gone
entirely, not stored more compactly. The trace also runs both versions and
compares their output, since a smaller chunk that computes something else
is not an optimisation, and that check is the one that would fail first if
folding ever got the arithmetic wrong.
"""

from __future__ import annotations

from ember.interpreter import build, run_output
from ember.traces.finding import Finding

NAME = "fold"
SOURCE = "print 1 + 2 * 3 - 4 / 2;"


def run() -> Finding:
    plain = build(SOURCE, optimize=False).chunk
    tight = build(SOURCE, optimize=True).chunk
    plain_output = run_output(SOURCE, optimize=False)
    tight_output = run_output(SOURCE, optimize=True)
    holds = (
        len(plain.code) == 17
        and len(plain.constants) == 4
        and len(tight.code) == 5
        and len(tight.constants) == 1
        and plain_output == tight_output == ["5.0"]
    )
    claim = (
        f"folding an arithmetic print turns {len(plain.code)} bytes and "
        f"{len(plain.constants)} constants into {len(tight.code)} bytes and "
        f"{len(tight.constants)}, the operators vanishing rather than shrinking, "
        f"and both forms still print {plain_output[0]}"
    )
    return Finding(NAME, claim, holds)
