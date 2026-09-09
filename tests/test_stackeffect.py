from __future__ import annotations

import pytest

from ember.opcode import OPERAND_BYTES, OpCode
from ember.stackeffect import OPERAND_DRIVEN, TERMINAL, effect_of, is_covered, uncovered


class TestCompleteness:
    def test_every_opcode_has_an_effect(self):
        assert uncovered() == []

    def test_coverage_agrees_with_the_opcode_table(self):
        # the two tables list the same instructions, so neither can drift alone
        assert all(is_covered(opcode) for opcode in OPERAND_BYTES)

    def test_an_operand_driven_opcode_counts_as_covered(self):
        for opcode in OPERAND_DRIVEN:
            assert is_covered(opcode)


class TestPushers:
    @pytest.mark.parametrize(
        "opcode",
        [
            OpCode.CONSTANT,
            OpCode.NIL,
            OpCode.TRUE,
            OpCode.FALSE,
            OpCode.GET_GLOBAL,
            OpCode.GET_LOCAL,
            OpCode.GET_UPVALUE,
            OpCode.CLOSURE,
            OpCode.CLASS,
        ],
    )
    def test_it_leaves_one_more_value(self, opcode):
        assert effect_of(opcode) == 1


class TestPoppers:
    @pytest.mark.parametrize(
        "opcode",
        [OpCode.POP, OpCode.PRINT, OpCode.RETURN, OpCode.THROW, OpCode.CLOSE_UPVALUE],
    )
    def test_it_takes_one_value(self, opcode):
        assert effect_of(opcode) == -1

    def test_setting_an_index_takes_two_beyond_the_value(self):
        # the collection and the key go, the assigned value stays as the expression
        assert effect_of(OpCode.INDEX_SET) == -2


class TestBinaryOperators:
    @pytest.mark.parametrize(
        "opcode",
        [
            OpCode.ADD,
            OpCode.SUBTRACT,
            OpCode.MULTIPLY,
            OpCode.DIVIDE,
            OpCode.MODULO,
            OpCode.EQUAL,
            OpCode.NOT_EQUAL,
            OpCode.LESS,
            OpCode.LESS_EQUAL,
            OpCode.GREATER,
            OpCode.GREATER_EQUAL,
            OpCode.BIT_AND,
            OpCode.BIT_OR,
            OpCode.BIT_XOR,
            OpCode.SHIFT_LEFT,
            OpCode.SHIFT_RIGHT,
        ],
    )
    def test_two_go_in_and_one_comes_out(self, opcode):
        assert effect_of(opcode) == -1

    @pytest.mark.parametrize("opcode", [OpCode.NEGATE, OpCode.NOT, OpCode.BIT_NOT])
    def test_a_unary_operator_replaces_its_operand(self, opcode):
        assert effect_of(opcode) == 0


class TestStoresLeaveTheirValue:
    @pytest.mark.parametrize(
        "opcode", [OpCode.SET_GLOBAL, OpCode.SET_LOCAL, OpCode.SET_UPVALUE]
    )
    def test_a_store_is_an_expression(self, opcode):
        assert effect_of(opcode) == 0

    @pytest.mark.parametrize(
        "opcode", [OpCode.DEFINE_GLOBAL, OpCode.DEFINE_GLOBAL_CONST]
    )
    def test_a_definition_is_a_statement_and_consumes(self, opcode):
        assert effect_of(opcode) == -1


class TestJumpsPeek:
    @pytest.mark.parametrize(
        "opcode", [OpCode.JUMP_IF_FALSE, OpCode.JUMP_IF_TRUE, OpCode.JUMP, OpCode.LOOP]
    )
    def test_a_jump_moves_nothing(self, opcode):
        assert effect_of(opcode) == 0


class TestOperandDriven:
    @pytest.mark.parametrize("count", [0, 1, 2, 5, 17])
    def test_a_call_consumes_its_arguments(self, count):
        # the callee and count arguments come off, one result goes on
        assert effect_of(OpCode.CALL, count) == -count

    @pytest.mark.parametrize("count", [0, 1, 4])
    def test_a_list_gathers_its_elements(self, count):
        assert effect_of(OpCode.BUILD_LIST, count) == 1 - count

    @pytest.mark.parametrize("count", [0, 1, 3])
    def test_a_map_gathers_two_per_entry(self, count):
        assert effect_of(OpCode.BUILD_MAP, count) == 1 - 2 * count

    def test_building_an_empty_list_still_pushes_it(self):
        assert effect_of(OpCode.BUILD_LIST, 0) == 1


class TestTerminals:
    def test_the_terminals_are_the_ones_that_do_not_fall_through(self):
        assert set(TERMINAL) == {OpCode.RETURN, OpCode.THROW, OpCode.JUMP, OpCode.LOOP}

    def test_a_conditional_jump_is_not_terminal(self):
        # it falls through when the test does not send it away
        assert OpCode.JUMP_IF_FALSE not in TERMINAL


class TestHandlers:
    def test_pushing_a_handler_moves_nothing_on_the_value_stack(self):
        # the handler lives on its own stack, which is why this is zero
        assert effect_of(OpCode.PUSH_HANDLER) == 0

    def test_popping_a_handler_moves_nothing_either(self):
        assert effect_of(OpCode.POP_HANDLER) == 0


class TestProperties:
    def test_reading_a_property_replaces_the_instance(self):
        assert effect_of(OpCode.GET_PROPERTY) == 0

    def test_writing_a_property_leaves_the_value(self):
        assert effect_of(OpCode.SET_PROPERTY) == -1

    def test_a_method_is_absorbed_by_its_class(self):
        assert effect_of(OpCode.METHOD) == -1

    def test_inheriting_consumes_the_superclass(self):
        assert effect_of(OpCode.INHERIT) == -1
