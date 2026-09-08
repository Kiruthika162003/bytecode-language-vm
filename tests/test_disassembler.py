from __future__ import annotations

from ember.chunk import Chunk
from ember.disassembler import disassemble, disassemble_instruction
from ember.opcode import OpCode


def _constant_chunk() -> Chunk:
    chunk = Chunk()
    index = chunk.add_constant(42)
    chunk.write_op(OpCode.CONSTANT, 1)
    chunk.write(index, 1)
    chunk.write_op(OpCode.NEGATE, 1)
    chunk.write_op(OpCode.RETURN, 1)
    return chunk


class TestInstruction:
    def test_a_bare_instruction_advances_by_one(self):
        chunk = Chunk()
        chunk.write_op(OpCode.RETURN, 1)
        text, nxt = disassemble_instruction(chunk, 0)
        assert "RETURN" in text
        assert nxt == 1

    def test_a_constant_shows_its_value(self):
        chunk = _constant_chunk()
        text, nxt = disassemble_instruction(chunk, 0)
        assert "CONSTANT" in text
        assert "42" in text
        assert nxt == 2

    def test_a_jump_shows_its_target(self):
        chunk = Chunk()
        chunk.write_op(OpCode.JUMP, 1)
        chunk.write(0x00, 1)
        chunk.write(0x05, 1)
        text, nxt = disassemble_instruction(chunk, 0)
        # a forward jump lands at offset + 3 + distance = 0 + 3 + 5 = 8
        assert "-> 8" in text
        assert nxt == 3

    def test_a_loop_jumps_backward(self):
        chunk = Chunk()
        chunk.write_op(OpCode.LOOP, 1)
        chunk.write(0x00, 1)
        chunk.write(0x02, 1)
        text, _ = disassemble_instruction(chunk, 0)
        # a loop lands at offset + 3 - distance = 0 + 3 - 2 = 1
        assert "-> 1" in text


class TestWholeChunk:
    def test_it_lists_every_instruction(self):
        chunk = _constant_chunk()
        text = disassemble(chunk, "test")
        assert "== test ==" in text
        assert "CONSTANT" in text
        assert "NEGATE" in text
        assert "RETURN" in text

    def test_a_run_on_one_line_is_marked(self):
        chunk = _constant_chunk()
        text = disassemble(chunk)
        # the second instruction shares line 1, shown with the continuation mark
        assert "|" in text
