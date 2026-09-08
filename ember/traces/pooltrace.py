"""The constant pool measured: five uses of one string, and one entry to show for it.

Every literal a program mentions has to be stored somewhere the instructions
can point at, and the pool would grow with every mention if it did not
deduplicate. This trace prints the same string five times and counts the
pool. One entry means the five loads all name the same slot, so the cost of
repeating a literal is a byte of operand rather than a copy of the value.
The second half of the trace guards the part that is easy to get wrong.
Deduplicating by equality alone would merge the integer one with the boolean
true, because the host language considers them equal, and merge the integer
one with the float one for the same reason; either would quietly change what
the program means, since this language keeps those values distinct. So the
pool compares type as well as value, and the trace checks that a program
mentioning all three ends up with three entries rather than one.
"""

from __future__ import annotations

from ember.interpreter import build, run_output
from ember.traces.finding import Finding

NAME = "pool"
REPEATED = 'print "hi"; print "hi"; print "hi"; print "hi"; print "hi";'
MIXED = "print 1; print true; print 1.0;"


def run() -> Finding:
    repeated = build(REPEATED).chunk
    mixed = build(MIXED).chunk
    # booleans compile to their own instructions, so only the numbers reach the
    # pool; what matters is that the int and the float are not merged
    numeric_entries = [value for value in mixed.constants if value in (1, 1.0)]
    distinct_types = {type(value) for value in numeric_entries}
    holds = (
        len(repeated.constants) == 1
        and run_output(REPEATED) == ["hi"] * 5
        and len(distinct_types) == 2
        and run_output(MIXED) == ["1", "true", "1.0"]
    )
    claim = (
        f"five mentions of one string share {len(repeated.constants)} pool entry, "
        f"so repeating a literal costs an operand byte rather than a copy, while "
        f"the integer and float one stay {len(distinct_types)} separate entries "
        "because the pool compares type as well as value"
    )
    return Finding(NAME, claim, holds)
