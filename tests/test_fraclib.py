from __future__ import annotations

import pytest

from ember.errors import Arithmetic, TypeMismatch
from ember.fraclib import fraction_names, normalise
from ember.interpreter import run_output, run_treewalk_output


def evaluate(expression: str) -> str:
    return run_output(f"print {expression};")[0]


def text_of(expression: str) -> str:
    return evaluate(f"fractionToText({expression})")


class TestRegistration:
    def test_the_functions_are_named(self):
        assert "fraction" in fraction_names()
        assert "fractionAdd" in fraction_names()

    def test_the_names_are_sorted(self):
        assert fraction_names() == sorted(fraction_names())

    def test_there_are_nineteen_of_them(self):
        assert len(fraction_names()) == 19


class TestNormalising:
    def test_a_fraction_is_reduced(self):
        assert normalise(6, 4) == [3, 2]

    def test_a_whole_number_has_a_denominator_of_one(self):
        assert normalise(4, 2) == [2, 1]

    def test_zero_is_zero_over_one(self):
        # without this rule there would be several lists meaning zero
        assert normalise(0, 5) == [0, 1]

    def test_the_sign_moves_to_the_numerator(self):
        assert normalise(1, -2) == [-1, 2]

    def test_two_negatives_make_a_positive(self):
        assert normalise(-1, -2) == [1, 2]

    def test_a_negative_numerator_stays_there(self):
        assert normalise(-1, 2) == [-1, 2]

    def test_an_already_reduced_fraction_is_unchanged(self):
        assert normalise(3, 7) == [3, 7]

    def test_a_denominator_of_zero_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            normalise(1, 0)
        assert "divided into no parts" in str(caught.value)

    def test_equal_fractions_are_identical_lists(self):
        # which is what makes the language's own equality work on them
        assert normalise(2, 4) == normalise(1, 2)

    def test_a_program_sees_them_as_equal(self):
        assert evaluate("fraction(2, 4) == fraction(1, 2)") == "true"

    def test_a_fraction_cannot_be_a_map_key(self):
        # the language refuses a list as a key whatever it holds, so normalising does
        # not buy this however convenient it would be
        source = "let m = {}; m[fraction(1, 2)] = " + chr(34) + "half" + chr(34) + ";"
        with pytest.raises(TypeMismatch) as caught:
            run_output(source)
        assert "cannot be a map key" in str(caught.value)

    def test_its_printed_form_can_be_a_key_instead(self):
        source = "let m = {}; m[fractionToText(fraction(1, 2))] = "
        source += chr(34) + "half" + chr(34) + "; print m[fractionToText(fraction(2, 4))];"
        assert run_output(source) == ["half"]


class TestExactness:
    def test_three_thirds_are_exactly_one(self):
        # the demonstration the whole library exists for
        source = "let t = fraction(1, 3); print fractionToText("
        source += "fractionAdd(fractionAdd(t, t), t));"
        assert run_output(source) == ["1"]

    def test_floats_do_not_manage_that(self):
        assert evaluate("0.1 + 0.2 == 0.3") == "false"

    def test_fractions_do(self):
        source = 'let a = fractionFromText("0.1"); let b = fractionFromText("0.2");'
        source += ' print fractionEqual(fractionAdd(a, b), fractionFromText("0.3"));'
        assert run_output(source) == ["true"]

    def test_a_long_chain_stays_exact(self):
        source = "let total = fraction(0, 1);" + chr(10)
        source += "for (let i = 1; i < 11; i = i + 1) {"
        source += " total = fractionAdd(total, fraction(1, 10)); }"
        source += chr(10) + "print fractionToText(total);"
        assert run_output(source) == ["1"]

    def test_a_sum_of_reciprocals_is_exact(self):
        source = "print fractionToText(fractionSum(["
        source += "fraction(1, 2), fraction(1, 3), fraction(1, 6)]));"
        assert run_output(source) == ["1"]


class TestArithmetic:
    def test_adding(self):
        assert text_of("fractionAdd(fraction(1, 2), fraction(1, 3))") == "5/6"

    def test_subtracting(self):
        assert text_of("fractionSubtract(fraction(1, 2), fraction(1, 3))") == "1/6"

    def test_multiplying(self):
        assert text_of("fractionMultiply(fraction(2, 3), fraction(3, 4))") == "1/2"

    def test_dividing(self):
        assert text_of("fractionDivide(fraction(1, 2), fraction(1, 4))") == "2"

    def test_negating(self):
        assert text_of("fractionNegate(fraction(1, 2))") == "-1/2"

    def test_negating_twice_returns_the_original(self):
        assert text_of("fractionNegate(fractionNegate(fraction(1, 2)))") == "1/2"

    def test_the_reciprocal_turns_it_over(self):
        assert text_of("fractionReciprocal(fraction(3, 7))") == "7/3"

    def test_zero_has_no_reciprocal(self):
        with pytest.raises(Arithmetic) as caught:
            run_output("print fractionReciprocal(fraction(0, 1));")
        assert "nothing divides into one" in str(caught.value)

    def test_dividing_by_zero_is_refused(self):
        with pytest.raises(Arithmetic):
            run_output("print fractionDivide(fraction(1, 2), fraction(0, 1));")

    def test_adding_zero_changes_nothing(self):
        assert text_of("fractionAdd(fraction(3, 7), fraction(0, 1))") == "3/7"

    def test_a_positive_power(self):
        assert text_of("fractionPower(fraction(2, 3), 3)") == "8/27"

    def test_a_power_of_zero_is_one(self):
        assert text_of("fractionPower(fraction(2, 3), 0)") == "1"

    def test_a_negative_power_turns_it_over(self):
        assert text_of("fractionPower(fraction(2, 3), -1)") == "3/2"

    def test_zero_to_a_negative_power_is_refused(self):
        with pytest.raises(Arithmetic):
            run_output("print fractionPower(fraction(0, 1), -1);")

    def test_the_mediant_lies_between(self):
        assert text_of("fractionMediant(fraction(0, 1), fraction(1, 1))") == "1/2"

    def test_summing_nothing_gives_zero(self):
        assert text_of("fractionSum([])") == "0"


class TestComparing:
    def test_a_smaller_fraction_compares_below(self):
        assert evaluate("fractionCompare(fraction(1, 3), fraction(1, 2))") == "-1"

    def test_a_larger_fraction_compares_above(self):
        assert evaluate("fractionCompare(fraction(1, 2), fraction(1, 3))") == "1"

    def test_equal_fractions_compare_level(self):
        assert evaluate("fractionCompare(fraction(2, 4), fraction(1, 2))") == "0"

    def test_negatives_compare_correctly(self):
        assert evaluate("fractionCompare(fraction(-1, 2), fraction(1, 2))") == "-1"

    def test_equality_is_offered_directly(self):
        assert evaluate("fractionEqual(fraction(2, 4), fraction(1, 2))") == "true"

    def test_inequality_is_recognised(self):
        assert evaluate("fractionEqual(fraction(1, 3), fraction(1, 2))") == "false"

    def test_less_than_is_offered_directly(self):
        assert evaluate("fractionLess(fraction(1, 3), fraction(1, 2))") == "true"

    def test_a_fraction_is_not_less_than_itself(self):
        assert evaluate("fractionLess(fraction(1, 2), fraction(1, 2))") == "false"

    def test_a_whole_fraction_is_recognised(self):
        assert evaluate("fractionIsWhole(fraction(4, 2))") == "true"

    def test_a_fraction_that_is_not_whole_is_recognised(self):
        assert evaluate("fractionIsWhole(fraction(1, 2))") == "false"


class TestConverting:
    def test_a_fraction_becomes_a_float(self):
        assert evaluate("fractionToFloat(fraction(1, 4))") == "0.25"

    def test_a_whole_number_becomes_a_fraction(self):
        assert text_of("fractionFromWhole(5)") == "5"

    def test_a_whole_fraction_prints_without_a_denominator(self):
        assert text_of("fraction(4, 2)") == "2"

    def test_a_fraction_prints_with_a_slash(self):
        assert text_of("fraction(3, 4)") == "3/4"

    def test_a_negative_fraction_prints_its_sign_in_front(self):
        assert text_of("fraction(1, -2)") == "-1/2"

    def test_a_fraction_reads_from_a_slashed_string(self):
        assert text_of('fractionFromText("3/4")') == "3/4"

    def test_a_fraction_reads_from_a_whole_number_string(self):
        assert text_of('fractionFromText("5")') == "5"

    def test_a_decimal_reads_exactly(self):
        assert text_of('fractionFromText("0.1")') == "1/10"

    def test_a_longer_decimal_reads_exactly(self):
        assert text_of('fractionFromText("1.25")') == "5/4"

    def test_a_negative_decimal_reads_exactly(self):
        assert text_of('fractionFromText("-1.25")') == "-5/4"

    def test_a_decimal_is_reduced(self):
        assert text_of('fractionFromText("0.50")') == "1/2"

    def test_whitespace_around_the_text_is_ignored(self):
        assert text_of('fractionFromText("  3/4  ")') == "3/4"

    def test_text_that_is_not_a_number_is_refused(self):
        with pytest.raises(Arithmetic):
            run_output('print fractionFromText("half");')

    def test_a_malformed_fraction_is_refused(self):
        with pytest.raises(Arithmetic):
            run_output('print fractionFromText("1/2/3");')

    def test_a_malformed_decimal_is_refused(self):
        with pytest.raises(Arithmetic):
            run_output('print fractionFromText("1.a");')

    def test_something_that_is_not_a_string_is_refused(self):
        with pytest.raises(TypeMismatch):
            run_output("print fractionFromText(5);")

    def test_simplifying_reduces_in_place(self):
        assert text_of("fractionSimplify([6, 4])") == "3/2"


class TestRefusingFloats:
    def test_a_float_numerator_is_refused(self):
        # converting a float exactly gives a denominator nobody meant
        with pytest.raises(TypeMismatch) as caught:
            run_output("print fraction(0.5, 1);")
        assert "a denominator nobody meant" in str(caught.value)

    def test_the_refusal_points_at_the_alternative(self):
        with pytest.raises(TypeMismatch) as caught:
            run_output("print fraction(0.5, 1);")
        assert "fractionFromText" in str(caught.value)

    def test_a_float_denominator_is_refused(self):
        with pytest.raises(TypeMismatch):
            run_output("print fraction(1, 2.5);")

    def test_a_string_is_refused_with_its_type(self):
        with pytest.raises(TypeMismatch) as caught:
            run_output('print fraction("1", 2);')
        assert "string" in str(caught.value)

    def test_a_fraction_that_is_not_a_pair_is_refused(self):
        with pytest.raises(TypeMismatch) as caught:
            run_output("print fractionAdd([1], fraction(1, 2));")
        assert "list of two whole numbers" in str(caught.value)

    def test_a_pair_with_a_zero_denominator_is_refused(self):
        with pytest.raises(Arithmetic):
            run_output("print fractionAdd([1, 0], fraction(1, 2));")


class TestBothBackendsAgree:
    @pytest.mark.parametrize(
        "expression",
        [
            "fraction(6, 4)",
            "fractionAdd(fraction(1, 2), fraction(1, 3))",
            "fractionSubtract(fraction(1, 2), fraction(1, 3))",
            "fractionMultiply(fraction(2, 3), fraction(3, 4))",
            "fractionDivide(fraction(1, 2), fraction(1, 4))",
            "fractionNegate(fraction(1, 2))",
            "fractionReciprocal(fraction(3, 7))",
            "fractionCompare(fraction(1, 3), fraction(1, 2))",
            "fractionEqual(fraction(2, 4), fraction(1, 2))",
            "fractionLess(fraction(1, 3), fraction(1, 2))",
            "fractionIsWhole(fraction(4, 2))",
            "fractionToFloat(fraction(1, 8))",
            "fractionToText(fraction(3, 4))",
            'fractionFromText("1.25")',
            "fractionFromWhole(7)",
            "fractionSimplify([6, 4])",
            "fractionMediant(fraction(1, 3), fraction(1, 2))",
            "fractionSum([fraction(1, 2), fraction(1, 3)])",
            "fractionPower(fraction(2, 3), 3)",
        ],
    )
    def test_the_two_backends_agree(self, expression):
        source = f"print {expression};"
        assert run_output(source) == run_treewalk_output(source)
