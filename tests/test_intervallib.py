from __future__ import annotations

import random

import pytest

from ember.errors import Arithmetic, TypeMismatch
from ember.interpreter import run_output, run_treewalk_output
from ember.intervallib import (
    _add,
    _divide,
    _multiply,
    _subtract,
    interval_names,
)


def evaluate(expression: str) -> str:
    return run_output(f"print {expression};")[0]


class TestRegistration:
    def test_the_functions_are_named(self):
        assert "intervalAdd" in interval_names()
        assert "definitelyLess" in interval_names()

    def test_the_names_are_sorted(self):
        assert interval_names() == sorted(interval_names())

    def test_there_are_twenty_two_of_them(self):
        assert len(interval_names()) == 22


class TestSampling:
    def test_every_sampled_result_lies_inside_the_interval(self):
        # the property the arithmetic exists to guarantee
        chooser = random.Random(5)
        for _ in range(200):
            left = sorted([chooser.uniform(-10, 10), chooser.uniform(-10, 10)])
            right = sorted([chooser.uniform(-10, 10), chooser.uniform(-10, 10)])
            for maker, combine in (
                (_add, lambda a, b: a + b),
                (_subtract, lambda a, b: a - b),
                (_multiply, lambda a, b: a * b),
            ):
                low, high = maker([left, right])
                for one in (left[0], left[1], sum(left) / 2):
                    for other in (right[0], right[1], sum(right) / 2):
                        value = combine(one, other)
                        assert low - 1e-9 <= value <= high + 1e-9

    def test_division_results_lie_inside_too(self):
        chooser = random.Random(6)
        for _ in range(200):
            left = sorted([chooser.uniform(-10, 10), chooser.uniform(-10, 10)])
            right = sorted([chooser.uniform(1, 10), chooser.uniform(1, 10)])
            low, high = _divide([left, right])
            for one in (left[0], left[1]):
                for other in (right[0], right[1]):
                    assert low - 1e-9 <= one / other <= high + 1e-9


class TestMaking:
    def test_an_interval_holds_its_ends(self):
        assert evaluate("interval(1, 5)") == "[1, 5]"

    def test_a_backwards_interval_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output("print interval(5, 1);")
        assert "runs upwards" in str(caught.value)

    def test_an_exact_value_is_an_interval_of_no_width(self):
        assert evaluate("exactly(3)") == "[3, 3]"

    def test_a_bare_number_is_accepted_as_an_interval(self):
        # an exact quantity is a special case rather than a separate thing
        assert evaluate("intervalAdd(3, 4)") == "[7, 7]"

    def test_a_tolerance_makes_an_interval_around_a_middle(self):
        assert evaluate("within(10, 1)") == "[9, 11]"

    def test_a_tolerance_of_zero_is_exact(self):
        assert evaluate("within(10, 0)") == "[10, 10]"

    def test_a_negative_tolerance_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output("print within(10, -1);")
        assert "cannot be negative" in str(caught.value)

    def test_a_backwards_list_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output("print intervalWidth([5, 1]);")
        assert "swap them" in str(caught.value)

    def test_a_list_of_the_wrong_length_is_refused(self):
        with pytest.raises(TypeMismatch):
            run_output("print intervalWidth([1, 2, 3]);")

    def test_a_string_is_refused(self):
        with pytest.raises(TypeMismatch):
            run_output('print intervalWidth("wide");')


class TestArithmetic:
    def test_adding_widens_by_both_widths(self):
        # each quantity known to within one gives a result known to within two
        assert evaluate("intervalAdd(within(10, 1), within(20, 1))") == "[28, 32]"

    def test_subtracting_also_widens(self):
        assert evaluate("intervalSubtract(within(10, 1), within(5, 1))") == "[3, 7]"

    def test_subtracting_pairs_opposite_ends(self):
        assert evaluate("intervalSubtract([1, 2], [3, 4])") == "[-3, -1]"

    def test_multiplying_positives_is_the_obvious_answer(self):
        assert evaluate("intervalMultiply([2, 3], [4, 5])") == "[8, 15]"

    def test_multiplying_across_zero_needs_all_four_products(self):
        # taking low times low and high times high would give four to one
        assert evaluate("intervalMultiply([-2, 1], [-2, 1])") == "[-2, 4]"

    def test_multiplying_a_negative_by_a_positive(self):
        assert evaluate("intervalMultiply([-3, -2], [2, 4])") == "[-12, -4]"

    def test_multiplying_by_zero_gives_zero(self):
        assert evaluate("intervalMultiply([-3, 5], 0)") == "[0, 0]"

    def test_dividing_positives(self):
        assert evaluate("intervalDivide([4, 8], [2, 4])") == "[1.0, 4.0]"

    def test_dividing_by_a_range_containing_zero_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output("print intervalDivide([1, 2], [-1, 1]);")
        assert "contains zero" in str(caught.value)

    def test_the_refusal_says_what_to_do(self):
        with pytest.raises(Arithmetic) as caught:
            run_output("print intervalDivide([1, 2], [-1, 1]);")
        assert "split it" in str(caught.value)

    def test_dividing_by_exactly_zero_is_refused(self):
        with pytest.raises(Arithmetic):
            run_output("print intervalDivide([1, 2], 0);")

    def test_negating_swaps_the_ends(self):
        assert evaluate("intervalNegate([1, 5])") == "[-5, -1]"

    def test_negating_twice_returns_the_original(self):
        assert evaluate("intervalNegate(intervalNegate([1, 5]))") == "[1, 5]"

    def test_a_power_multiplies_repeatedly(self):
        assert evaluate("intervalPower([2, 3], 2)") == "[4, 9]"

    def test_a_power_of_one_is_the_interval(self):
        assert evaluate("intervalPower([2, 3], 1)") == "[2, 3]"

    def test_a_power_of_zero_is_one(self):
        assert evaluate("intervalPower([2, 3], 0)") == "[1, 1]"

    def test_a_squared_interval_across_zero_reaches_zero(self):
        assert evaluate("intervalPower([-2, 1], 2)") == "[-2, 4]"

    def test_a_negative_power_is_refused(self):
        with pytest.raises(Arithmetic):
            run_output("print intervalPower([1, 2], -1);")


class TestMeasuring:
    def test_the_width_is_the_span(self):
        assert evaluate("intervalWidth([1, 5])") == "4"

    def test_an_exact_interval_has_no_width(self):
        assert evaluate("intervalWidth(exactly(3))") == "0"

    def test_the_middle_is_halfway(self):
        assert evaluate("intervalMiddle([1, 5])") == "3.0"

    def test_an_exact_interval_is_recognised(self):
        assert evaluate("intervalExact(exactly(3))") == "true"

    def test_a_wide_interval_is_not_exact(self):
        assert evaluate("intervalExact([1, 2])") == "false"


class TestRelationships:
    def test_an_interval_contains_a_value_inside_it(self):
        assert evaluate("intervalContains([1, 5], 3)") == "true"

    def test_an_interval_contains_its_ends(self):
        assert evaluate("intervalContains([1, 5], 1)") == "true"
        assert evaluate("intervalContains([1, 5], 5)") == "true"

    def test_an_interval_does_not_contain_a_value_outside(self):
        assert evaluate("intervalContains([1, 5], 9)") == "false"

    def test_overlapping_intervals_overlap(self):
        assert evaluate("intervalOverlaps([1, 5], [3, 9])") == "true"

    def test_touching_intervals_overlap(self):
        assert evaluate("intervalOverlaps([1, 5], [5, 9])") == "true"

    def test_disjoint_intervals_do_not(self):
        assert evaluate("intervalOverlaps([1, 2], [5, 9])") == "false"

    def test_an_interval_encloses_one_inside_it(self):
        assert evaluate("intervalEncloses([1, 9], [3, 5])") == "true"

    def test_an_interval_encloses_itself(self):
        assert evaluate("intervalEncloses([1, 9], [1, 9])") == "true"

    def test_a_partly_overlapping_interval_is_not_enclosed(self):
        assert evaluate("intervalEncloses([1, 5], [3, 9])") == "false"

    def test_the_intersection_is_what_both_cover(self):
        assert evaluate("intervalIntersection([1, 5], [3, 9])") == "[3, 5]"

    def test_the_intersection_of_disjoint_intervals_is_nil(self):
        # nil rather than an interval running backwards
        assert evaluate("intervalIntersection([1, 2], [5, 9])") == "nil"

    def test_the_intersection_of_touching_intervals_is_a_point(self):
        assert evaluate("intervalIntersection([1, 5], [5, 9])") == "[5, 5]"

    def test_the_union_covers_both(self):
        assert evaluate("intervalUnion([1, 2], [5, 9])") == "[1, 9]"

    def test_the_union_of_overlapping_intervals(self):
        assert evaluate("intervalUnion([1, 5], [3, 9])") == "[1, 9]"

    def test_two_identical_intervals_are_the_same(self):
        assert evaluate("sameInterval([1, 5], [1, 5])") == "true"

    def test_two_different_intervals_are_not(self):
        assert evaluate("sameInterval([1, 5], [1, 6])") == "false"


class TestComparison:
    def test_a_wholly_lower_interval_is_definitely_less(self):
        assert evaluate("definitelyLess([1, 2], [5, 9])") == "true"

    def test_a_wholly_higher_interval_is_definitely_greater(self):
        assert evaluate("definitelyGreater([5, 9], [1, 2])") == "true"

    def test_overlapping_intervals_are_neither(self):
        # the honest answer, and the reason intervals cannot be sorted
        assert evaluate("definitelyLess([1, 5], [3, 9])") == "false"
        assert evaluate("definitelyGreater([1, 5], [3, 9])") == "false"

    def test_touching_intervals_are_neither(self):
        assert evaluate("definitelyLess([1, 5], [5, 9])") == "false"

    def test_the_comparison_is_known_for_disjoint_intervals(self):
        assert evaluate("comparisonKnown([1, 2], [5, 9])") == "true"

    def test_the_comparison_is_unknown_for_overlapping_ones(self):
        assert evaluate("comparisonKnown([1, 5], [3, 9])") == "false"

    def test_an_interval_is_not_definitely_less_than_itself(self):
        assert evaluate("definitelyLess([1, 5], [1, 5])") == "false"

    def test_exact_values_compare_normally(self):
        assert evaluate("definitelyLess(exactly(1), exactly(2))") == "true"


class TestRendering:
    def test_a_wide_interval_reads_as_a_range(self):
        assert evaluate("intervalToText([1, 5])") == "1 to 5"

    def test_an_exact_interval_says_so(self):
        assert evaluate("intervalToText(exactly(3))") == "exactly 3"

    def test_a_bare_number_reads_as_exact(self):
        assert evaluate("intervalToText(7)") == "exactly 7"


class TestARealisticChain:
    def test_uncertainty_grows_through_a_calculation(self):
        # two lengths each known to within a tenth, multiplied for an area
        source = "let width = within(10, 0.1); let height = within(20, 0.2);"
        source += " let area = intervalMultiply(width, height);"
        source += " print intervalWidth(area) > 0; print intervalContains(area, 200);"
        assert run_output(source) == ["true", "true"]

    def test_a_chain_of_operations_stays_bounded(self):
        source = "let a = within(5, 0.5); let b = within(3, 0.5);"
        source += " let result = intervalDivide(intervalAdd(a, b), within(2, 0.1));"
        source += " print intervalContains(result, 4);"
        assert run_output(source) == ["true"]


class TestBothBackendsAgree:
    @pytest.mark.parametrize(
        "expression",
        [
            "interval(1, 5)",
            "exactly(3)",
            "within(10, 1)",
            "intervalAdd([1, 2], [3, 4])",
            "intervalSubtract([1, 2], [3, 4])",
            "intervalMultiply([-2, 1], [-2, 1])",
            "intervalDivide([4, 8], [2, 4])",
            "intervalNegate([1, 5])",
            "intervalPower([2, 3], 3)",
            "intervalWidth([1, 5])",
            "intervalMiddle([1, 5])",
            "intervalExact([3, 3])",
            "intervalContains([1, 5], 3)",
            "intervalOverlaps([1, 5], [3, 9])",
            "intervalEncloses([1, 9], [3, 5])",
            "intervalIntersection([1, 5], [3, 9])",
            "intervalIntersection([1, 2], [5, 9])",
            "intervalUnion([1, 2], [5, 9])",
            "definitelyLess([1, 2], [5, 9])",
            "definitelyGreater([5, 9], [1, 2])",
            "comparisonKnown([1, 5], [3, 9])",
            "sameInterval([1, 5], [1, 5])",
            "intervalToText([1, 5])",
        ],
    )
    def test_the_two_backends_agree(self, expression):
        source = f"print {expression};"
        assert run_output(source) == run_treewalk_output(source)
