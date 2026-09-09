from __future__ import annotations

import pytest

from ember.bitlib import bit_names
from ember.errors import Arithmetic, TypeMismatch
from ember.interpreter import run_output, run_treewalk_output


def evaluate(expression: str) -> str:
    return run_output(f"print {expression};")[0]


class TestRegistration:
    def test_the_functions_are_named(self):
        assert "countOnes" in bit_names()
        assert "rotateLeft" in bit_names()

    def test_the_names_are_sorted(self):
        assert bit_names() == sorted(bit_names())

    def test_there_are_twenty_five_of_them(self):
        assert len(bit_names()) == 25


class TestCounting:
    @pytest.mark.parametrize(
        "value,expected", [(0, 0), (1, 1), (3, 2), (255, 8), (256, 1), (1023, 10)]
    )
    def test_the_population_count(self, value, expected):
        assert evaluate(f"countOnes({value})") == str(expected)

    @pytest.mark.parametrize("value,expected", [(0, 0), (1, 1), (2, 2), (255, 8), (256, 9)])
    def test_the_bit_length(self, value, expected):
        assert evaluate(f"bitLength({value})") == str(expected)

    def test_the_parity_of_an_even_count_is_zero(self):
        assert evaluate("parity(3)") == "0"

    def test_the_parity_of_an_odd_count_is_one(self):
        assert evaluate("parity(7)") == "1"

    def test_the_hamming_distance_counts_differing_positions(self):
        assert evaluate("hammingDistance(1, 2)") == "2"

    def test_a_number_is_no_distance_from_itself(self):
        assert evaluate("hammingDistance(9, 9)") == "0"

    def test_the_distance_from_zero_is_the_population_count(self):
        assert evaluate("hammingDistance(255, 0)") == evaluate("countOnes(255)")


class TestFindingBits:
    @pytest.mark.parametrize("value,expected", [(1, 0), (2, 1), (8, 3), (255, 7), (256, 8)])
    def test_the_highest_set_bit(self, value, expected):
        assert evaluate(f"highestBit({value})") == str(expected)

    @pytest.mark.parametrize("value,expected", [(1, 0), (2, 1), (12, 2), (8, 3), (255, 0)])
    def test_the_lowest_set_bit(self, value, expected):
        assert evaluate(f"lowestBit({value})") == str(expected)

    def test_zero_has_no_highest_bit(self):
        with pytest.raises(Arithmetic) as caught:
            run_output("print highestBit(0);")
        assert "no bits set" in str(caught.value)

    def test_zero_has_no_lowest_bit(self):
        with pytest.raises(Arithmetic):
            run_output("print lowestBit(0);")


class TestSinglePositions:
    def test_a_set_bit_tests_true(self):
        assert evaluate("testBit(5, 0)") == "true"

    def test_a_clear_bit_tests_false(self):
        assert evaluate("testBit(5, 1)") == "false"

    def test_a_position_past_the_top_tests_false(self):
        assert evaluate("testBit(5, 99)") == "false"

    def test_setting_a_bit_raises_the_value(self):
        assert evaluate("setBit(0, 3)") == "8"

    def test_setting_a_bit_already_set_changes_nothing(self):
        assert evaluate("setBit(8, 3)") == "8"

    def test_clearing_a_bit_lowers_the_value(self):
        assert evaluate("clearBit(15, 0)") == "14"

    def test_clearing_a_bit_already_clear_changes_nothing(self):
        assert evaluate("clearBit(14, 0)") == "14"

    def test_flipping_a_clear_bit_sets_it(self):
        assert evaluate("flipBit(0, 2)") == "4"

    def test_flipping_a_set_bit_clears_it(self):
        assert evaluate("flipBit(4, 2)") == "0"

    def test_flipping_twice_returns_the_original(self):
        assert evaluate("flipBit(flipBit(9, 3), 3)") == "9"

    def test_a_negative_position_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output("print testBit(5, -1);")
        assert "from zero" in str(caught.value)


class TestPowersOfTwo:
    @pytest.mark.parametrize("value", [1, 2, 4, 8, 64, 1024])
    def test_a_power_of_two_is_recognised(self, value):
        assert evaluate(f"isPowerOfTwo({value})") == "true"

    @pytest.mark.parametrize("value", [0, 3, 5, 100, 1023])
    def test_something_else_is_not(self, value):
        assert evaluate(f"isPowerOfTwo({value})") == "false"

    @pytest.mark.parametrize(
        "value,expected", [(0, 1), (1, 1), (2, 2), (3, 4), (100, 128), (1024, 1024)]
    )
    def test_the_next_power_of_two(self, value, expected):
        assert evaluate(f"nextPowerOfTwo({value})") == str(expected)

    def test_a_power_of_two_is_its_own_next(self):
        assert evaluate("nextPowerOfTwo(64)") == "64"


class TestWidths:
    def test_a_mask_is_a_run_of_ones(self):
        assert evaluate("mask(8)") == "255"

    def test_a_mask_of_one_bit_is_one(self):
        assert evaluate("mask(1)") == "1"

    def test_the_low_bits_of_a_value_are_kept(self):
        assert evaluate("lowBits(511, 8)") == "255"

    def test_a_negative_value_reads_as_twos_complement_at_the_width(self):
        # the only reading that makes sense once a width has been named
        assert evaluate("lowBits(-1, 8)") == "255"

    def test_a_negative_one_in_four_bits_is_fifteen(self):
        assert evaluate("lowBits(-1, 4)") == "15"

    def test_a_width_of_zero_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output("print mask(0);")
        assert "at least one bit" in str(caught.value)

    def test_an_absurd_width_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output("print mask(9999);")
        assert "too wide" in str(caught.value)

    def test_the_complement_flips_every_bit_in_the_width(self):
        assert evaluate("complement(0, 8)") == "255"

    def test_the_complement_of_a_full_word_is_zero(self):
        assert evaluate("complement(255, 8)") == "0"

    def test_complementing_twice_returns_the_original(self):
        assert evaluate("complement(complement(9, 8), 8)") == "9"


class TestRotating:
    def test_rotating_left_moves_a_bit_up(self):
        assert evaluate("rotateLeft(1, 1, 8)") == "2"

    def test_rotating_left_off_the_top_wraps_to_the_bottom(self):
        assert evaluate("rotateLeft(128, 1, 8)") == "1"

    def test_rotating_right_moves_a_bit_down(self):
        assert evaluate("rotateRight(2, 1, 8)") == "1"

    def test_rotating_right_off_the_bottom_wraps_to_the_top(self):
        assert evaluate("rotateRight(1, 1, 8)") == "128"

    def test_rotating_by_the_width_changes_nothing(self):
        assert evaluate("rotateLeft(37, 8, 8)") == "37"

    def test_rotating_past_the_width_wraps_round(self):
        assert evaluate("rotateLeft(1, 9, 8)") == "2"

    def test_rotating_by_zero_changes_nothing(self):
        assert evaluate("rotateLeft(37, 0, 8)") == "37"

    def test_left_and_right_undo_each_other(self):
        assert evaluate("rotateRight(rotateLeft(37, 3, 8), 3, 8)") == "37"

    def test_reversing_bits_turns_the_word_around(self):
        assert evaluate("reverseBits(1, 8)") == "128"

    def test_reversing_twice_returns_the_original(self):
        assert evaluate("reverseBits(reverseBits(37, 8), 8)") == "37"

    def test_a_palindrome_reverses_to_itself(self):
        assert evaluate("reverseBits(129, 8)") == "129"


class TestWrittenForms:
    def test_a_number_writes_as_binary(self):
        assert evaluate("toBinary(5)") == "101"

    def test_zero_writes_as_a_single_zero(self):
        assert evaluate("toBinary(0)") == "0"

    def test_a_padded_form_fills_the_width(self):
        assert evaluate("toBinaryWidth(5, 8)") == "00000101"

    def test_a_padded_form_of_a_negative_shows_its_complement(self):
        assert evaluate("toBinaryWidth(-1, 8)") == "11111111"

    def test_binary_reads_back(self):
        assert evaluate('fromBinary("101")') == "5"

    def test_binary_round_trips(self):
        assert evaluate("fromBinary(toBinary(37))") == "37"

    def test_something_that_is_not_binary_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output('print fromBinary("102");')
        assert "ones and zeros" in str(caught.value)

    def test_empty_text_is_refused(self):
        with pytest.raises(Arithmetic):
            run_output('print fromBinary("");')

    def test_a_number_writes_as_hexadecimal(self):
        assert evaluate("toHex(255)") == "ff"

    def test_hexadecimal_reads_back(self):
        assert evaluate('fromHex("ff")') == "255"

    def test_hexadecimal_round_trips(self):
        assert evaluate("fromHex(toHex(48879))") == "48879"

    def test_something_that_is_not_hexadecimal_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output('print fromHex("xyz");')
        assert "hexadecimal" in str(caught.value)

    def test_reading_something_that_is_not_a_string_is_refused(self):
        with pytest.raises(TypeMismatch):
            run_output("print fromBinary(101);")


class TestBitLists:
    def test_the_bits_come_back_highest_first(self):
        assert evaluate("bitsOf(5, 4)") == "[0, 1, 0, 1]"

    def test_the_list_is_as_wide_as_asked_for(self):
        assert evaluate("len(bitsOf(5, 8))") == "8"

    def test_a_list_of_bits_reads_back(self):
        assert evaluate("fromBits([1, 0, 1])") == "5"

    def test_bits_round_trip(self):
        assert evaluate("fromBits(bitsOf(37, 8))") == "37"

    def test_an_empty_list_reads_as_zero(self):
        assert evaluate("fromBits([])") == "0"

    def test_something_other_than_a_bit_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output("print fromBits([1, 2]);")
        assert "ones and zeros" in str(caught.value)

    def test_a_boolean_is_not_a_bit(self):
        with pytest.raises(Arithmetic):
            run_output("print fromBits([true]);")

    def test_something_that_is_not_a_list_is_refused(self):
        with pytest.raises(TypeMismatch):
            run_output("print fromBits(5);")


class TestRefusals:
    @pytest.mark.parametrize(
        "call",
        [
            "countOnes(-1)",
            "bitLength(-1)",
            "highestBit(-1)",
            "testBit(-1, 0)",
            "setBit(-1, 0)",
            "toBinary(-1)",
            "toHex(-1)",
        ],
    )
    def test_a_negative_number_without_a_width_is_refused(self, call):
        # a negative number has no finite binary form until a width is chosen
        with pytest.raises(Arithmetic) as caught:
            run_output(f"print {call};")
        assert "without a chosen width" in str(caught.value)

    def test_the_refusal_points_at_the_alternative(self):
        with pytest.raises(Arithmetic) as caught:
            run_output("print countOnes(-1);")
        assert "takes a width" in str(caught.value)

    @pytest.mark.parametrize(
        "call", ["countOnes(1.5)", "testBit(1.5, 0)", "setBit(1, 1.5)", "mask(1.5)"]
    )
    def test_a_float_is_refused(self, call):
        with pytest.raises(TypeMismatch) as caught:
            run_output(f"print {call};")
        assert "whole" in str(caught.value)

    def test_the_refusal_explains_why_a_fraction_has_no_answer(self):
        with pytest.raises(TypeMismatch) as caught:
            run_output("print countOnes(1.5);")
        assert "not a question with an answer" in str(caught.value)


class TestBothBackendsAgree:
    @pytest.mark.parametrize(
        "expression",
        [
            "countOnes(255)",
            "bitLength(1024)",
            "highestBit(48)",
            "lowestBit(48)",
            "testBit(5, 2)",
            "setBit(1, 5)",
            "clearBit(255, 4)",
            "flipBit(9, 1)",
            "isPowerOfTwo(512)",
            "nextPowerOfTwo(1000)",
            "mask(16)",
            "lowBits(-1, 16)",
            "rotateLeft(37, 3, 8)",
            "rotateRight(37, 3, 8)",
            "complement(37, 8)",
            "reverseBits(37, 8)",
            "toBinary(37)",
            "toBinaryWidth(37, 12)",
            'fromBinary("100101")',
            "toHex(48879)",
            'fromHex("beef")',
            "parity(37)",
            "hammingDistance(37, 42)",
            "bitsOf(37, 8)",
            "fromBits([1, 0, 0, 1, 0, 1])",
        ],
    )
    def test_the_two_backends_agree(self, expression):
        source = f"print {expression};"
        assert run_output(source) == run_treewalk_output(source)
