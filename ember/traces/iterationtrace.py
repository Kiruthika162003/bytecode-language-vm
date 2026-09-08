"""Iteration measured: the collection read once, and a fresh binding every turn.

Two things about an iteration are easy to get wrong in ways that only show up
later, and both are measured here. The first is how often the collection
expression runs. It is evaluated once into a hidden local, so a call in that
position happens a single time no matter how many elements come back; the trace
proves it by iterating over a function that prints as a side effect and counting
that one line, where a per-iteration evaluation would have printed it three times.
The second is what a closure made inside the body captures. The loop variable is
declared in a fresh scope each turn, so three functions created in three
iterations hold three different values; if the variable were reused across turns
they would all report the last one, which is the classic loop-capture bug and the
reason this is worth a measurement rather than an assertion. The trace also
confirms that a map iterates over its keys, which is the choice that lets the body
reach the value while iterating the other way would not.
"""

from __future__ import annotations

from ember.interpreter import run_output, run_treewalk_output
from ember.traces.finding import Finding

NAME = "iteration"
ONCE = 'fn source() { print "evaluated"; return [1, 2, 3]; } for (x in source()) print x;'
CAPTURE = (
    "let fs = []; for (x in [1, 2, 3]) { fn f() { return x; } push(fs, f); }"
    " for (g in fs) print g();"
)
KEYS = 'let m = {"a": 1, "b": 2}; for (k in m) print k + "=" + str(m[k]);'


def run() -> Finding:
    once = run_output(ONCE)
    captured = run_output(CAPTURE)
    keys = run_output(KEYS)
    evaluations = once.count("evaluated")
    agrees = (
        run_treewalk_output(ONCE) == once
        and run_treewalk_output(CAPTURE) == captured
        and run_treewalk_output(KEYS) == keys
    )
    holds = (
        evaluations == 1
        and once == ["evaluated", "1", "2", "3"]
        and captured == ["1", "2", "3"]
        and keys == ["a=1", "b=2"]
        and agrees
    )
    claim = (
        f"the collection expression runs {evaluations} time however many elements it "
        f"yields, three closures made in three iterations report {captured} rather "
        "than the last value three times, and a map yields keys the body can use to "
        "reach its values; both backends agree on all three"
    )
    return Finding(NAME, claim, holds)
