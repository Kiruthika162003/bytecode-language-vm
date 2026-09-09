from __future__ import annotations

import pytest

from ember.errors import Arithmetic, TypeMismatch
from ember.interpreter import run_output, run_treewalk_output
from ember.statlib import compensated_sum, stat_names


def evaluate(expression: str) -> str:
    return run_output(f"print {expression};")[0]


class TestRegistration:
    def test_every_function_is_named(self):
        assert "mean" in stat_names()
        assert "correlation" in stat_names()

    def test_the_names_are_sorted(self):
        assert stat_names() == sorted(stat_names())

    def test_there_are_fourteen_of_them(self):
        assert len(stat_names()) == 14

    @pytest.mark.parametrize("name", ["mean", "median", "mode", "stdev", "percentile"])
    def test_each_one_is_callable_from_a_program(self, name):
        assert name in stat_names()


class TestMean:
    def test_the_mean_of_a_few_numbers(self):
        assert evaluate("mean([1, 2, 3, 4])") == "2.5"

    def test_the_mean_of_one_number_is_that_number(self):
        assert evaluate("mean([7])") == "7.0"

    def test_an_empty_list_is_refused(self):
        # zero is a real answer to a different question
        with pytest.raises(Arithmetic) as caught:
            run_output("print mean([]);")
        assert "empty list" in str(caught.value)

    def test_a_list_of_strings_is_refused(self):
        with pytest.raises(TypeMismatch):
            run_output('print mean(["a"]);')

    def test_something_other_than_a_list_is_refused(self):
        with pytest.raises(TypeMismatch):
            run_output("print mean(5);")

    def test_a_boolean_is_not_a_number(self):
        with pytest.raises(TypeMismatch):
            run_output("print mean([true]);")


class TestMedian:
    def test_an_odd_count_takes_the_middle(self):
        assert evaluate("median([3, 1, 2])") == "2"

    def test_an_even_count_averages_the_two_middles(self):
        assert evaluate("median([1, 2, 3, 4])") == "2.5"

    def test_the_list_need_not_be_sorted(self):
        assert evaluate("median([9, 1, 5])") == "5"

    def test_an_empty_list_is_refused(self):
        with pytest.raises(Arithmetic):
            run_output("print median([]);")


class TestMode:
    def test_the_most_frequent_value_wins(self):
        assert evaluate("mode([1, 2, 2, 3])") == "2"

    def test_a_tie_takes_the_smallest(self):
        # deterministic rather than order dependent
        assert evaluate("mode([5, 5, 2, 2])") == "2"

    def test_all_distinct_values_take_the_smallest(self):
        assert evaluate("mode([3, 1, 2])") == "1"

    def test_an_empty_list_is_refused(self):
        with pytest.raises(Arithmetic):
            run_output("print mode([]);")


class TestVariance:
    def test_the_sample_variance_divides_by_one_less(self):
        # values 2 and 4: the sample variance is 2, the population variance is 1
        assert evaluate("variance([2, 4])") == "2.0"

    def test_the_population_variance_divides_by_the_count(self):
        assert evaluate("pvariance([2, 4])") == "1.0"

    def test_a_single_value_has_no_sample_variance(self):
        with pytest.raises(Arithmetic) as caught:
            run_output("print variance([1]);")
        assert "at least two values" in str(caught.value)

    def test_the_refusal_points_at_the_population_form(self):
        with pytest.raises(Arithmetic) as caught:
            run_output("print variance([1]);")
        assert "pvariance" in str(caught.value)

    def test_a_single_value_has_a_population_variance_of_zero(self):
        assert evaluate("pvariance([1])") == "0.0"

    def test_identical_values_have_no_spread(self):
        assert evaluate("variance([3, 3, 3])") == "0.0"

    def test_the_deviation_is_the_root_of_the_variance(self):
        assert evaluate("stdev([2, 4])") == evaluate("pow(variance([2, 4]), 0.5)")

    def test_the_population_deviation_matches_its_variance(self):
        assert evaluate("pstdev([2, 4])") == "1.0"


class TestSpreadAndPercentiles:
    def test_the_spread_is_the_range(self):
        assert evaluate("spread([1, 9, 4])") == "8"

    def test_the_median_percentile_matches_the_median(self):
        assert evaluate("percentile([1, 2, 3, 4, 5], 50)") == "3.0"

    def test_the_lowest_percentile_is_the_smallest_value(self):
        assert evaluate("percentile([1, 2, 3], 0)") == "1.0"

    def test_the_highest_percentile_is_the_largest_value(self):
        assert evaluate("percentile([1, 2, 3], 100)") == "3.0"

    def test_a_percentile_between_values_interpolates(self):
        assert evaluate("percentile([1, 2], 50)") == "1.5"

    def test_a_single_value_answers_every_percentile(self):
        assert evaluate("percentile([7], 25)") == "7"

    def test_a_fraction_out_of_range_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output("print percentile([1, 2], 150);")
        assert "0 to 100" in str(caught.value)

    def test_a_fraction_that_is_not_a_number_is_refused(self):
        with pytest.raises(TypeMismatch):
            run_output('print percentile([1, 2], "half");')

    def test_the_quartiles_come_back_in_order(self):
        assert evaluate("quartiles([1, 2, 3, 4, 5])") == "[2.0, 3.0, 4.0]"


class TestShapes:
    def test_normalising_maps_onto_zero_to_one(self):
        assert evaluate("normalised([0, 5, 10])") == "[0.0, 0.5, 1.0]"

    def test_identical_values_normalise_to_zero(self):
        # no scale to normalise against, so no division is attempted
        assert evaluate("normalised([4, 4])") == "[0.0, 0.0]"

    def test_a_running_total_grows(self):
        assert evaluate("cumulative([1, 2, 3])") == "[1, 3, 6]"

    def test_an_empty_running_total_is_empty(self):
        assert evaluate("cumulative([])") == "[]"


class TestRelationships:
    def test_a_perfect_line_correlates_at_one(self):
        assert evaluate("correlation([1, 2, 3], [2, 4, 6])") == "1.0"

    def test_an_inverse_line_correlates_at_minus_one(self):
        assert evaluate("correlation([1, 2, 3], [6, 4, 2])") == "-1.0"

    def test_covariance_of_a_rising_pair_is_positive(self):
        assert float(evaluate("covariance([1, 2, 3], [2, 4, 6])")) > 0

    def test_lists_of_different_lengths_are_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output("print covariance([1, 2], [1, 2, 3]);")
        assert "same length" in str(caught.value)

    def test_the_refusal_names_both_lengths(self):
        with pytest.raises(Arithmetic) as caught:
            run_output("print covariance([1, 2], [1, 2, 3]);")
        assert "2 and 3" in str(caught.value)

    def test_a_single_pair_has_no_covariance(self):
        with pytest.raises(Arithmetic):
            run_output("print covariance([1], [2]);")

    def test_a_constant_list_cannot_be_correlated(self):
        with pytest.raises(Arithmetic) as caught:
            run_output("print correlation([1, 1, 1], [1, 2, 3]);")
        assert "never varies" in str(caught.value)


class TestCompensatedSum:
    def test_it_totals_whole_numbers_exactly(self):
        assert compensated_sum([1, 2, 3]) == 6

    def test_an_empty_list_totals_zero(self):
        assert compensated_sum([]) == 0.0

    def test_it_beats_naive_addition_on_many_small_floats(self):
        values = [0.1] * 10
        naive = 0.0
        for value in values:
            naive = naive + value
        assert abs(compensated_sum(values) - 1.0) <= abs(naive - 1.0)

    def test_it_survives_a_large_value_cancelling_out(self):
        # the case that chose Neumaier over Kahan: Kahan compensation assumes the
        # running total is the larger operand and returns zero here, losing the one
        assert compensated_sum([1e16, 1.0, -1e16]) == 1.0

    def test_kahan_compensation_would_have_lost_it(self):
        # kept as a record of what the simpler algorithm actually does
        total = 0.0
        carried = 0.0
        for value in [1e16, 1.0, -1e16]:
            adjusted = value - carried
            raised = total + adjusted
            carried = (raised - total) - adjusted
            total = raised
        assert total == 0.0


class TestBothBackendsAgree:
    @pytest.mark.parametrize(
        "expression",
        [
            "mean([1, 2, 3])",
            "median([1, 2, 3, 4])",
            "mode([1, 1, 2])",
            "variance([2, 4, 6])",
            "stdev([2, 4, 6])",
            "percentile([1, 2, 3, 4], 75)",
            "quartiles([1, 2, 3, 4, 5])",
            "normalised([1, 2, 3])",
            "cumulative([1, 2, 3])",
            "correlation([1, 2, 3], [1, 2, 3])",
        ],
    )
    def test_the_two_backends_agree(self, expression):
        source = f"print {expression};"
        assert run_output(source) == run_treewalk_output(source)
