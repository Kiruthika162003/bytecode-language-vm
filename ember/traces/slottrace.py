"""Locals measured: the same three reads as slot indices instead of name lookups.

The reason a compiler bothers to assign stack slots to locals is that a slot
is an array index while a global is a name looked up in a dictionary on every
access. This trace compiles the same three reads twice, once where the
variable is a global and once where a surrounding block makes it a local, and
compares what the two chunks contain. The witness is the constant pool: the
global form has to store the variable's name as a string so the machine can
look it up at run time, while the local form stores no name at all, because
the name was resolved away while compiling and only a slot number remains.
The instructions differ to match, one form reaching for GET_GLOBAL and the
other for GET_LOCAL. What this trace deliberately does not claim is a speed
figure. Timing would depend on the host interpreter running this machine and
would tell the reader more about Python than about the design, so the claim
stays with what can be counted exactly: names stored, and which instruction
was chosen.
"""

from __future__ import annotations

from ember.disassembler import disassemble
from ember.interpreter import build
from ember.traces.finding import Finding

NAME = "slot"
GLOBAL_FORM = "let x = 1; print x; print x; print x;"
LOCAL_FORM = "{ let x = 1; print x; print x; print x; }"


def run() -> Finding:
    as_global = build(GLOBAL_FORM).chunk
    as_local = build(LOCAL_FORM).chunk
    global_text = disassemble(as_global)
    local_text = disassemble(as_local)
    names_stored_globally = sum(1 for value in as_global.constants if value == "x")
    names_stored_locally = sum(1 for value in as_local.constants if value == "x")
    holds = (
        names_stored_globally == 1
        and names_stored_locally == 0
        and "GET_GLOBAL" in global_text
        and "GET_LOCAL" in local_text
        and "GET_GLOBAL" not in local_text
    )
    claim = (
        f"making a variable local removes its name from the chunk entirely, "
        f"{names_stored_globally} stored name becoming {names_stored_locally}, "
        "and every read compiles to GET_LOCAL with a slot index where the "
        "global form needed GET_GLOBAL and a run-time lookup"
    )
    return Finding(NAME, claim, holds)
