from __future__ import annotations

from ember.opcode import OPERAND_BYTES, OpCode, operand_bytes


class TestOpCode:
    def test_every_opcode_has_a_distinct_value(self):
        values = [op.value for op in OpCode]
        assert len(set(values)) == len(values)

    def test_opcodes_fit_in_a_byte(self):
        assert all(0 <= op.value <= 255 for op in OpCode)


class TestOperandWidths:
    def test_every_opcode_has_a_declared_width(self):
        for op in OpCode:
            assert op in OPERAND_BYTES

    def test_jumps_carry_two_operand_bytes(self):
        assert operand_bytes(OpCode.JUMP) == 2
        assert operand_bytes(OpCode.JUMP_IF_FALSE) == 2
        assert operand_bytes(OpCode.LOOP) == 2

    def test_loads_carry_one_operand_byte(self):
        assert operand_bytes(OpCode.CONSTANT) == 1
        assert operand_bytes(OpCode.GET_LOCAL) == 1
        assert operand_bytes(OpCode.CALL) == 1

    def test_bare_operations_carry_none(self):
        assert operand_bytes(OpCode.ADD) == 0
        assert operand_bytes(OpCode.RETURN) == 0
        assert operand_bytes(OpCode.POP) == 0
