from __future__ import annotations

import pytest

from ember.chunk import Chunk
from ember.disassembler import disassemble
from ember.errors import Compile
from ember.instructions import Instruction, decode, encode, round_trip
from ember.interpreter import build
from ember.opcode import OpCode

RICH = """
class A { init(x) { this.x = x; } m() { return this.x * 2; } }
class B < A { m() { return super.m() + 1; } }
fn make() { let c = 0; fn inc() { c = c + 1; return c; } return inc; }
let g = make();
for (i in [1, 2, 3]) { if (i == 2) continue; print i; }
let n = 0; while (n < 3) { n = n + 1; if (n == 2) break; }
print B(5).m(); print g();
if (n > 0) print "pos"; else print "neg";
"""


def _all_functions(function):
    yield function
    for constant in function.chunk.constants:
        if hasattr(constant, "chunk"):
            yield from _all_functions(constant)


class TestInstruction:
    def test_a_bare_instruction_is_one_byte(self):
        assert Instruction(OpCode.RETURN, 1).size == 1

    def test_an_operand_adds_to_the_size(self):
        assert Instruction(OpCode.CONSTANT, 1, operands=(0,)).size == 2

    def test_a_jump_is_always_three_bytes(self):
        assert Instruction(OpCode.JUMP, 1, target=0).size == 3
        assert Instruction(OpCode.JUMP, 1, target=9999).size == 3

    def test_a_jump_reports_itself_as_one(self):
        assert Instruction(OpCode.JUMP, 1, target=0).is_jump
        assert not Instruction(OpCode.ADD, 1).is_jump


class TestDecoding:
    def test_it_produces_one_record_per_instruction(self):
        chunk = Chunk()
        chunk.write_op(OpCode.NIL, 1)
        chunk.write_op(OpCode.RETURN, 1)
        program = decode(chunk)
        assert [i.opcode for i in program.instructions] == [OpCode.NIL, OpCode.RETURN]

    def test_a_jump_becomes_an_instruction_index(self):
        function = build('if (1 < 2) print "a"; else print "b";')
        program = decode(function.chunk)
        jumps = [i for i in program.instructions if i.is_jump]
        assert jumps
        for jump in jumps:
            assert jump.target is not None
            assert 0 <= jump.target <= len(program.instructions)

    def test_targets_collects_every_landing_place(self):
        program = decode(build("let n = 0; while (n < 3) n = n + 1;").chunk)
        assert program.targets()

    def test_a_jump_into_the_middle_of_an_instruction_is_refused(self):
        chunk = Chunk()
        chunk.write_op(OpCode.JUMP, 1)
        chunk.write(0x00, 1)
        chunk.write(0x01, 1)  # lands one byte into the CONSTANT that follows
        chunk.write_op(OpCode.CONSTANT, 1)
        chunk.write(0, 1)
        chunk.add_constant(1)
        with pytest.raises(Compile):
            decode(chunk)

    def test_a_byte_that_is_not_an_opcode_is_refused(self):
        chunk = Chunk()
        chunk.write(250, 1)
        with pytest.raises(Compile):
            decode(chunk)


class TestRoundTrip:
    def test_a_rich_program_encodes_back_byte_identically(self):
        function = build(RICH)
        assert round_trip(function.chunk).code == function.chunk.code

    def test_every_nested_chunk_round_trips(self):
        for function in _all_functions(build(RICH)):
            assert round_trip(function.chunk).code == function.chunk.code, function.name

    def test_the_disassembly_survives(self):
        function = build(RICH)
        rebuilt = round_trip(function.chunk)
        assert disassemble(rebuilt, "x") == disassemble(function.chunk, "x")

    def test_line_information_survives(self):
        function = build(RICH)
        rebuilt = round_trip(function.chunk)
        assert [rebuilt.line_at(i) for i in range(len(rebuilt.code))] == [
            function.chunk.line_at(i) for i in range(len(function.chunk.code))
        ]

    def test_constants_survive(self):
        function = build(RICH)
        assert round_trip(function.chunk).constants == function.chunk.constants


class TestEncodingErrors:
    def test_a_target_outside_the_program_is_refused(self):
        program = decode(build("print 1;").chunk)
        program.instructions.append(Instruction(OpCode.JUMP, 1, target=9999))
        with pytest.raises(Compile):
            encode(program)

    def test_a_jump_with_no_target_is_refused(self):
        program = decode(build("print 1;").chunk)
        program.instructions.append(Instruction(OpCode.JUMP, 1))
        with pytest.raises(Compile):
            encode(program)

    def test_a_forward_jump_that_would_go_backwards_is_refused(self):
        program = decode(build("print 1; print 2;").chunk)
        program.instructions[-1] = Instruction(OpCode.JUMP, 1, target=0)
        with pytest.raises(Compile):
            encode(program)
