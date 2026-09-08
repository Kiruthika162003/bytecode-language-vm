"""The chunk: one unit of compiled code, its constants, and where each byte came from.

A chunk is what the compiler produces and the machine consumes: a flat
array of bytes holding opcodes and their inline operands, a pool of the
literal values those instructions refer to, and a line table tying each
byte back to its source. Splitting the literals out into a pool rather
than embedding them in the byte stream is the central idea. A number or
string cannot fit in a byte, so instead the compiler adds the value to
the pool once and emits a one-byte index into it, and repeated uses of
the same literal can share a single pool entry. This module offers the
narrow interface the compiler needs: write a byte and note its line, add
a constant and get back its index, and patch a byte already written,
which the compiler uses to fill in a jump distance it did not know when
it emitted the jump. The one limit it enforces is the format's: the pool
is addressed by a single byte, so the two-hundred-fifty-seventh distinct
constant in a chunk cannot be indexed, and rather than let the compiler
emit an index that silently wraps, adding that constant raises a compile
error naming the limit. Reading a two-byte operand back out is provided
too, so the machine and the disassembler decode jumps the same way the
compiler encoded them, keeping the encoding in exactly one place.
"""

from __future__ import annotations

from typing import Any

from ember.errors import Compile
from ember.linetable import LineTable
from ember.opcode import OpCode

_MAX_CONSTANTS = 256
_BYTE_MASK = 0xFF


class Chunk:
    def __init__(self) -> None:
        self.code: list[int] = []
        self.constants: list[Any] = []
        self._lines = LineTable()

    def __len__(self) -> int:
        return len(self.code)

    def write(self, byte: int, line: int) -> int:
        if not 0 <= byte <= _BYTE_MASK:
            raise Compile(
                f"the value {byte} does not fit in a byte; only 0 to 255 can "
                "be written to a chunk"
            )
        offset = len(self.code)
        self.code.append(byte)
        self._lines.record(line)
        return offset

    def write_op(self, opcode: OpCode, line: int) -> int:
        return self.write(int(opcode), line)

    def add_constant(self, value: Any) -> int:
        for index, existing in enumerate(self.constants):
            if type(existing) is type(value) and existing == value:
                return index
        if len(self.constants) >= _MAX_CONSTANTS:
            raise Compile(
                f"a chunk cannot hold more than {_MAX_CONSTANTS} constants; "
                "this function has too many distinct literals and must be split"
            )
        self.constants.append(value)
        return len(self.constants) - 1

    def patch(self, offset: int, byte: int) -> None:
        if not 0 <= offset < len(self.code):
            raise Compile(
                f"cannot patch offset {offset}; it is outside the {len(self.code)} "
                "bytes written so far"
            )
        if not 0 <= byte <= _BYTE_MASK:
            raise Compile(f"the patch value {byte} does not fit in a byte")
        self.code[offset] = byte

    def read_short(self, offset: int) -> int:
        high = self.code[offset]
        low = self.code[offset + 1]
        return (high << 8) | low

    def line_at(self, offset: int) -> int:
        return self._lines.line_at(offset)
