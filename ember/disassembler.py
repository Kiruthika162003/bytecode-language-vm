"""The disassembler: turn a chunk of bytecode back into text a person can read.

Bytecode is written to be executed, not read, so when the compiler
produces something surprising the fastest way to see what it did is to
render the bytes back into named instructions. This module is that
renderer. It walks a chunk one instruction at a time, using the same
operand-width table the machine uses so that it steps over each
instruction by exactly its true size, and formats each as its offset,
its opcode name, and its operand shown in the most useful form. That last
part is where a disassembler earns its keep: a constant load shows not
just the pool index but the value at that index, and a jump shows not
just the raw distance but the absolute offset it lands on, so the reader
sees the destination without doing the arithmetic. It also prints the
source line beside each instruction, collapsing a run of instructions
from one line into a marker so the eye is drawn to where the line
changes. The honest limitation is that this is a linear disassembler: it
decodes from a known starting point straight through, which is correct
for this format because every byte is either an opcode or an operand of
the opcode before it, with no data interleaved. A format that mixed data
into the code stream would defeat a linear pass and need the code to be
traced from its entry points, a complication this simple, uniform
encoding is designed to avoid.
"""

from __future__ import annotations

from ember.chunk import Chunk
from ember.opcode import OpCode, operand_bytes

_CONSTANT_OPS = {
    OpCode.CONSTANT,
    OpCode.DEFINE_GLOBAL,
    OpCode.DEFINE_GLOBAL_CONST,
    OpCode.GET_GLOBAL,
    OpCode.SET_GLOBAL,
}
_JUMP_FORWARD = {OpCode.JUMP, OpCode.JUMP_IF_FALSE, OpCode.JUMP_IF_TRUE}


def disassemble_instruction(chunk: Chunk, offset: int) -> tuple[str, int]:
    byte = chunk.code[offset]
    try:
        opcode = OpCode(byte)
    except ValueError:
        return f"{offset:04d}    ?? unknown byte {byte}", offset + 1
    line = chunk.line_at(offset)
    same_line = offset > 0 and chunk.line_at(offset - 1) == line
    line_text = "   |" if same_line else f"{line:4d}"
    width = operand_bytes(opcode)
    head = f"{offset:04d} {line_text} {opcode.name}"
    if width == 0:
        return head, offset + 1
    if width == 1:
        arg = chunk.code[offset + 1]
        if opcode in _CONSTANT_OPS:
            value = chunk.constants[arg]
            return f"{head} {arg} ({value!r})", offset + 2
        return f"{head} {arg}", offset + 2
    distance = chunk.read_short(offset + 1)
    if opcode == OpCode.LOOP:
        target = offset + 3 - distance
    elif opcode in _JUMP_FORWARD:
        target = offset + 3 + distance
    else:
        target = distance
    return f"{head} {distance} -> {target}", offset + 3


def disassemble(chunk: Chunk, name: str = "chunk") -> str:
    lines = [f"== {name} =="]
    offset = 0
    while offset < len(chunk):
        text, offset = disassemble_instruction(chunk, offset)
        lines.append(text)
    return "\n".join(lines)
