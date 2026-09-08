"""Flexible arity measured: one function accepting a range of call shapes.

Once a function may have defaults and a rest parameter, arity stops being a number
and becomes a range, and the calling convention has to agree with the declaration
about exactly which counts are legal. This trace declares a function with one
required parameter, one defaulted, and a rest, asks the compiled function which
counts it accepts, and calls it at four of them to confirm the answers match what
actually happens. The printed values are built from the argument count, so a
default silently going missing would change the text rather than passing quietly.
The property being measured is that the filling happens before the callee starts:
by the time the body runs every parameter already holds a value, so the body never
tests whether it was passed one, and the rest parameter is an ordinary list even
when nothing was gathered into it.
"""

from __future__ import annotations

from ember.interpreter import build, run_output
from ember.traces.finding import Finding

NAME = "arity-range"
SOURCE = (
    "fn f(a, b = 2, ...rest) { return str(a) + str(b) + str(len(rest)); }"
    " print f(1); print f(1, 9); print f(1, 9, 7); print f(1, 9, 7, 7);"
)


def run() -> Finding:
    function = build(SOURCE)
    declared = next(c for c in function.chunk.constants if hasattr(c, "required"))
    accepted = [declared.accepts(n) for n in range(6)]
    printed = run_output(SOURCE)
    holds = (
        declared.required == 1
        and declared.named == 2
        and declared.arity == 3
        and declared.is_variadic
        and accepted == [False, True, True, True, True, True]
        and declared.describe_arity() == "at least 1"
        and printed == ["120", "190", "191", "192"]
    )
    claim = (
        f"one required parameter, one default, and a rest accepts "
        f"{declared.describe_arity()} arguments, refusing 0 and taking every count "
        f"from {declared.required} upward; called at four counts it prints {printed}, "
        "so the default fills before the body starts and the rest is a list even "
        "when empty"
    )
    return Finding(NAME, claim, holds)
