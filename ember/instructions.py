"""Instructions: decode a chunk into editable records where jumps name targets, not distances.

Rewriting bytecode is dangerous for one specific reason. Every jump stores a
distance in bytes, so deleting or inserting a single instruction silently
changes the meaning of every jump that spans the edit. Any pass that edits
instructions therefore needs a representation in which a jump says where it
goes rather than how far, and that is what this module provides. Decoding
walks a chunk once, records the byte offset each instruction begins at, and
turns every jump's distance into the index of the instruction it lands on;
after that, instructions can be removed, replaced, or reordered freely,
because a target is a reference rather than an arithmetic fact. Encoding runs
the reverse: it computes each instruction's new offset from the sizes ahead of
it, then fills in each jump's distance from the offsets of the two ends. The
sizes are what make this a single pass rather than an iteration to a fixed
point: a jump's operand is always two bytes whatever the distance, so no
instruction's size depends on any offset, and the layout is fully determined
before a single jump is resolved. Two shapes need care. CLOSURE carries a
variable number of operand bytes, two per captured upvalue, so its raw
operands are kept verbatim and its size read from them rather than from a
table. And a jump landing anywhere other than the exact start of an
instruction means the chunk was already malformed, so decoding refuses it
instead of producing records that would encode back to something different.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ember.chunk import Chunk
from ember.errors import Compile
from ember.opcode import OpCode, operand_bytes

FORWARD_JUMPS = (OpCode.JUMP, OpCode.JUMP_IF_FALSE, OpCode.JUMP_IF_TRUE)
BACKWARD_JUMPS = (OpCode.LOOP,)
JUMPS = FORWARD_JUMPS + BACKWARD_JUMPS


@dataclass
class Instruction:
    opcode: OpCode
    line: int
    operands: tuple[int, ...] = ()
    target: int | None = None

    @property
    def is_jump(self) -> bool:
        return self.opcode in JUMPS

    @property
    def size(self) -> int:
        if self.is_jump:
            return 3
        return 1 + len(self.operands)


@dataclass
class Program:
    instructions: list[Instruction] = field(default_factory=list)
    constants: list[object] = field(default_factory=list)

    def targets(self) -> set[int]:
        """Every instruction index some jump can land on."""
        return {
            instruction.target
            for instruction in self.instructions
            if instruction.target is not None
        }


def _closure_size(chunk: Chunk, offset: int) -> int:
    constant_index = chunk.code[offset + 1]
    function = chunk.constants[constant_index]
    return 2 + 2 * getattr(function, "upvalue_count", 0)


def decode(chunk: Chunk) -> Program:
    offsets: dict[int, int] = {}
    raw: list[tuple[int, OpCode, tuple[int, ...], int]] = []
    offset = 0
    while offset < len(chunk.code):
        try:
            opcode = OpCode(chunk.code[offset])
        except ValueError as exc:
            raise Compile(
                f"the byte {chunk.code[offset]} at offset {offset} is not an opcode"
            ) from exc
        offsets[offset] = len(raw)
        if opcode == OpCode.CLOSURE:
            size = _closure_size(chunk, offset)
        else:
            size = 1 + operand_bytes(opcode)
        operands = tuple(chunk.code[offset + 1 : offset + size])
        raw.append((offset, opcode, operands, chunk.line_at(offset)))
        offset += size
    program = Program(constants=list(chunk.constants))
    for index, (start, opcode, operands, line) in enumerate(raw):
        if opcode in JUMPS:
            distance = (operands[0] << 8) | operands[1]
            after = start + 3
            landing = after + distance if opcode in FORWARD_JUMPS else after - distance
            if landing not in offsets:
                raise Compile(
                    f"the jump at offset {start} lands at {landing}, which is not "
                    "the start of an instruction; the chunk is malformed"
                )
            program.instructions.append(
                Instruction(opcode, line, target=offsets[landing])
            )
        else:
            program.instructions.append(Instruction(opcode, line, operands=operands))
        del index
    return program


def encode(program: Program) -> Chunk:
    count = len(program.instructions)
    offsets: list[int] = []
    running = 0
    for instruction in program.instructions:
        offsets.append(running)
        running += instruction.size
    end = running
    chunk = Chunk()
    chunk.constants = list(program.constants)
    for index, instruction in enumerate(program.instructions):
        chunk.write_op(instruction.opcode, instruction.line)
        if not instruction.is_jump:
            for byte in instruction.operands:
                chunk.write(byte, instruction.line)
            continue
        target = instruction.target
        if target is None or not 0 <= target <= count:
            raise Compile(
                f"the jump at index {index} names the target {target}, which is "
                "not an instruction in this program"
            )
        landing = end if target == count else offsets[target]
        after = offsets[index] + 3
        distance = landing - after if instruction.opcode in FORWARD_JUMPS else after - landing
        if distance < 0:
            raise Compile(
                f"the jump at index {index} would need a negative distance of "
                f"{distance}; a forward jump cannot go backwards"
            )
        if distance > 0xFFFF:
            raise Compile(f"a jump of {distance} bytes is too far to encode")
        chunk.write((distance >> 8) & 0xFF, instruction.line)
        chunk.write(distance & 0xFF, instruction.line)
    return chunk


def round_trip(chunk: Chunk) -> Chunk:
    return encode(decode(chunk))
