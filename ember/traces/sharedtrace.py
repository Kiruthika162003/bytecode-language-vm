"""Shared capture measured: two closures over one variable, and the count they agree on.

The subtle requirement in closure capture is not that a variable survives its
frame but that two functions capturing the same variable see the same one. If
each received its own copy, a program could increment through one and read
through the other and get nothing back. This trace declares a local, closes
two functions over it, one that increments and one that reads, calls the
incrementer three times and then the reader. The reader answers three, which
it could only do if both closures were holding a single shared upvalue rather
than two copies of the value at capture time. The trace also confirms the two
closures really are separate function objects, since a claim about sharing
between two closures means nothing if there is only one closure.
"""

from __future__ import annotations

from ember.interpreter import run as execute
from ember.traces.finding import Finding

NAME = "shared"
SOURCE = (
    "fn pair() { let n = 0;"
    " fn up() { n = n + 1; return n; }"
    " fn get() { return n; }"
    " up(); up(); up(); return get(); }"
    " print pair();"
)
PROBE = (
    "fn pair() { let n = 0;"
    " fn up() { n = n + 1; return n; }"
    " fn get() { return n; }"
    " up(); return [up, get]; }"
    " let both = pair();"
)


def run() -> Finding:
    machine = execute(SOURCE)
    probe = execute(PROBE)
    pair = probe.globals["both"]
    incrementer, reader = pair[0], pair[1]
    same_upvalue = incrementer.upvalues[0] is reader.upvalues[0]
    distinct_closures = incrementer is not reader
    holds = machine.output == ["3"] and same_upvalue and distinct_closures
    claim = (
        f"a reader closure sees {machine.output[0]} after a sibling incremented "
        "three times, which is only possible because the two distinct closures "
        "hold one shared upvalue rather than a copy of the value each"
    )
    return Finding(NAME, claim, holds)
