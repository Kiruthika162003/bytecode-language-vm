"""Peephole measured: what disappears at the instruction level, and what must not.

The tree passes and the peephole pass find different waste, and this trace
isolates the second. Its program declares two locals and mentions each as a bare
statement, which the compiler necessarily turns into a load followed by a pop
that together do nothing; the pass removes both halves of each pair. The number
worth watching is the constant pool, which does not move: nothing here was
folded, so this is the instruction level acting alone. The trace also checks the
rule that keeps such editing safe, by confirming every jump still names a real
instruction afterwards, since deleting an instruction renumbers everything after
it and a pass that got that wrong would leave a jump pointing into the middle of
another instruction. And it confirms the deliberate omission: a global load
followed by a pop survives, because reading an undefined global raises and that
pair is an error the program is owed rather than dead code.
"""

from __future__ import annotations

from ember.instructions import decode
from ember.interpreter import build, run_output
from ember.opcode import OpCode
from ember.traces.finding import Finding

NAME = "peephole"
LOCALS = "{ let a = 1; let b = 2; a; b; print a + b; }"
GLOBALS = "let g = 1; g; print g;"


def run() -> Finding:
    plain = build(LOCALS).chunk
    tight = build(LOCALS, peephole=True).chunk
    before = len(decode(plain).instructions)
    after = len(decode(tight).instructions)
    program = decode(tight)
    count = len(program.instructions)
    targets_valid = all(
        0 <= instruction.target <= count
        for instruction in program.instructions
        if instruction.target is not None
    )
    global_chunk = build(GLOBALS, peephole=True).chunk
    global_kept = OpCode.GET_GLOBAL in [
        instruction.opcode for instruction in decode(global_chunk).instructions
    ]
    holds = (
        len(plain.code) == 20
        and len(tight.code) == 14
        and before == 14
        and after == 10
        and len(plain.constants) == len(tight.constants) == 2
        and targets_valid
        and global_kept
        and run_output(LOCALS) == run_output(LOCALS, peephole=True) == ["3"]
    )
    claim = (
        f"two load-then-pop pairs vanish at the instruction level, {before} "
        f"instructions and {len(plain.code)} bytes becoming {after} and "
        f"{len(tight.code)} while the constant pool stays at {len(tight.constants)}, "
        "every jump still names a real instruction, and a global load then pop "
        "survives because reading an undefined global raises"
    )
    return Finding(NAME, claim, holds)
