"""The formatter measured: two properties that make a printer trustworthy.

A formatter is easy to write and easy to write wrongly, because most of its
mistakes produce output that still looks like code. Two properties catch almost
all of them, and this trace checks both on a program squeezed onto one line.
Idempotence catches a printer that adds or drops a token each pass: formatting
the formatted text must change nothing, and a printer that kept adding a bracket
or losing a space would fail on the second round. Meaning preservation catches
the worse class of bug, where the output parses but computes something else; the
trace parses the formatted text, runs it, and demands the same output as the
original. That second check is the one that caught a real fault while this
formatter was being written, when a redundant group reported itself as a primary
and a sum multiplied by something lost its brackets, quietly changing the value.
The trace also reports how many lines the one-line input became, which is the
only thing here that is a matter of taste rather than correctness.
"""

from __future__ import annotations

from ember.formatter import format_program
from ember.interpreter import run_output
from ember.parser import parse
from ember.scanner import scan
from ember.traces.finding import Finding

NAME = "format"
SOURCE = (
    'let x=1+2*3;if(x>3){print "big";}else{print "small";}'
    "fn add(a,b){return a+b;}print add(1,2);print (1+2)*3;"
)


def run() -> Finding:
    once = format_program(parse(scan(SOURCE)))
    twice = format_program(parse(scan(once)))
    idempotent = once == twice
    preserved = run_output(SOURCE) == run_output(once)
    kept_parentheses = "(1 + 2) * 3" in once
    holds = idempotent and preserved and kept_parentheses
    claim = (
        f"one line of source becomes {len(once.splitlines())} formatted lines, "
        f"formatting the result again changes nothing, and both forms print "
        f"{run_output(once)}; the parentheses in a sum multiplied by something "
        "survive, which is the case that once silently changed the value"
    )
    return Finding(NAME, claim, holds)
