from __future__ import annotations

import pytest

from ember.chunk import Chunk
from ember.errors import Compile
from ember.opcode import OpCode


class TestWriting:
    def test_writing_returns_the_offset(self):
        chunk = Chunk()
        assert chunk.write_op(OpCode.NIL, 1) == 0
        assert chunk.write_op(OpCode.POP, 1) == 1
        assert len(chunk) == 2

    def test_a_written_line_is_recoverable(self):
        chunk = Chunk()
        chunk.write_op(OpCode.NIL, 7)
        assert chunk.line_at(0) == 7

    def test_a_value_outside_a_byte_is_refused(self):
        chunk = Chunk()
        with pytest.raises(Compile):
            chunk.write(300, 1)


class TestConstants:
    def test_adding_a_constant_returns_its_index(self):
        chunk = Chunk()
        assert chunk.add_constant(42) == 0
        assert chunk.add_constant("hi") == 1

    def test_an_equal_constant_is_deduplicated(self):
        chunk = Chunk()
        first = chunk.add_constant(3.5)
        second = chunk.add_constant(3.5)
        assert first == second
        assert len(chunk.constants) == 1

    def test_true_and_one_are_not_merged(self):
        # 1 == True in Python, but the pool keeps distinct types apart
        chunk = Chunk()
        a = chunk.add_constant(1)
        b = chunk.add_constant(True)
        assert a != b

    def test_overflowing_the_pool_is_refused(self):
        chunk = Chunk()
        for value in range(256):
            chunk.add_constant(value)
        with pytest.raises(Compile):
            chunk.add_constant(256)


class TestPatchingAndShorts:
    def test_a_two_byte_operand_round_trips(self):
        chunk = Chunk()
        chunk.write(0x00, 1)
        chunk.write(0x00, 1)
        chunk.patch(0, 0x12)
        chunk.patch(1, 0x34)
        assert chunk.read_short(0) == 0x1234

    def test_patching_out_of_range_is_refused(self):
        chunk = Chunk()
        chunk.write(0, 1)
        with pytest.raises(Compile):
            chunk.patch(9, 0)
