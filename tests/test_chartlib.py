from __future__ import annotations

import pytest

from ember.chartlib import chart_names
from ember.errors import Arithmetic, TypeMismatch
from ember.interpreter import run_output, run_treewalk_output

QUOTE = chr(34)


def quoted(text: str) -> str:
    return QUOTE + text + QUOTE


def evaluate(expression: str) -> str:
    return run_output(f"print {expression};")[0]


def lines_of(expression: str) -> list[str]:
    return run_output(f"for (line in {expression}) print line;")


class TestRegistration:
    def test_the_functions_are_named(self):
        assert "barChart" in chart_names()
        assert "sparkline" in chart_names()

    def test_the_names_are_sorted(self):
        assert chart_names() == sorted(chart_names())

    def test_there_are_eight_of_them(self):
        assert len(chart_names()) == 8


class TestEverythingIsAscii:
    def test_a_bar_chart_prints_as_ascii(self):
        # a chart that cannot be printed where it is used is not a chart
        for line in lines_of("barChart([1, 5, 3], 10)"):
            assert all(ord(character) < 128 for character in line)

    def test_a_sparkline_is_ascii(self):
        drawn = evaluate("sparkline([1, 5, 2, 8])")
        assert all(ord(character) < 128 for character in drawn)

    def test_a_table_is_ascii(self):
        for line in lines_of(f"table([[{quoted('a')}, {quoted('b')}]])"):
            assert all(ord(character) < 128 for character in line)

    def test_an_axis_is_ascii(self):
        assert all(ord(character) < 128 for character in evaluate("axis(20, 0, 100)"))


class TestBarCharts:
    def test_the_largest_value_fills_the_width(self):
        drawn = lines_of("barChart([5, 10], 10)")
        assert len(drawn[1]) == 10

    def test_the_others_are_proportional(self):
        drawn = lines_of("barChart([5, 10], 10)")
        assert len(drawn[0]) == 5

    def test_a_zero_draws_nothing(self):
        drawn = lines_of("barChart([0, 10], 10)")
        assert drawn[0] == ""

    def test_a_small_value_still_draws_something(self):
        # so a reader can never mistake something small for nothing at all
        drawn = lines_of("barChart([1, 1000], 10)")
        assert len(drawn[0]) == 1

    def test_the_baseline_is_zero_not_the_smallest(self):
        # starting at the smallest exaggerates differences
        drawn = lines_of("barChart([98, 100], 10)")
        assert len(drawn[0]) >= 9

    def test_an_empty_list_draws_nothing(self):
        assert lines_of("barChart([], 10)") == []

    def test_all_zeros_draw_nothing(self):
        drawn = lines_of("barChart([0, 0], 10)")
        assert drawn == ["", ""]

    def test_a_negative_value_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output("print barChart([1, -1], 10);")
        assert "negative value" in str(caught.value)

    def test_the_refusal_says_what_to_do_instead(self):
        with pytest.raises(Arithmetic) as caught:
            run_output("print barChart([-1], 10);")
        assert "say which you meant" in str(caught.value)

    def test_a_width_of_zero_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output("print barChart([1], 0);")
        assert "at least one" in str(caught.value)

    def test_a_width_that_is_not_whole_is_refused(self):
        with pytest.raises(TypeMismatch):
            run_output("print barChart([1], 2.5);")

    def test_a_list_of_strings_is_refused(self):
        with pytest.raises(TypeMismatch) as caught:
            run_output(f"print barChart([{quoted('a')}], 10);")
        assert "needs numbers" in str(caught.value)

    def test_floats_are_charted(self):
        drawn = lines_of("barChart([0.5, 1.0], 10)")
        assert len(drawn[0]) == 5


class TestLabelledBars:
    def test_the_labels_are_aligned(self):
        labels = f"[{quoted('alpha')}, {quoted('b')}]"
        drawn = lines_of(f"labelledBars({labels}, [10, 5], 10)")
        assert drawn[0].startswith("alpha  ")
        assert drawn[1].startswith("b      ")

    def test_the_value_appears_after_the_bar(self):
        labels = f"[{quoted('a')}]"
        drawn = lines_of(f"labelledBars({labels}, [7], 10)")
        assert drawn[0].endswith(" 7")

    def test_a_mismatched_count_is_refused(self):
        labels = f"[{quoted('a')}]"
        with pytest.raises(Arithmetic) as caught:
            run_output(f"print labelledBars({labels}, [1, 2], 10);")
        assert "one label for each value" in str(caught.value)

    def test_the_refusal_names_both_counts(self):
        labels = f"[{quoted('a')}]"
        with pytest.raises(Arithmetic) as caught:
            run_output(f"print labelledBars({labels}, [1, 2], 10);")
        assert "1 labels and 2 values" in str(caught.value)

    def test_numbers_can_be_labels(self):
        drawn = lines_of("labelledBars([1, 2], [3, 4], 10)")
        assert drawn[0].startswith("1")


class TestHistograms:
    def test_the_counts_add_up(self):
        assert evaluate("histogram([1, 2, 2, 3, 8, 9], 4)") == "[3, 1, 0, 2]"

    def test_there_is_one_count_per_bucket(self):
        assert len(evaluate("histogram([1, 2, 3], 5)")[1:-1].split(", ")) == 5

    def test_every_value_lands_somewhere(self):
        printed = evaluate("histogram([1, 5, 9, 3, 7], 3)")
        assert sum(int(piece) for piece in printed[1:-1].split(", ")) == 5

    def test_the_largest_value_lands_in_the_last_bucket(self):
        printed = evaluate("histogram([1, 10], 2)")
        assert printed.endswith("1]")

    def test_identical_values_all_land_in_the_first_bucket(self):
        # rather than a division by a span of zero being attempted
        assert evaluate("histogram([4, 4, 4], 3)") == "[3, 0, 0]"

    def test_an_empty_list_gives_empty_buckets(self):
        assert evaluate("histogram([], 3)") == "[0, 0, 0]"

    def test_negative_values_are_accepted(self):
        # a bucket is a range, and a range can be negative
        printed = evaluate("histogram([-5, 0, 5], 3)")
        assert sum(int(piece) for piece in printed[1:-1].split(", ")) == 3

    def test_a_bucket_count_of_zero_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output("print histogram([1], 0);")
        assert "at least one bucket" in str(caught.value)

    def test_a_bucket_count_that_is_not_whole_is_refused(self):
        with pytest.raises(TypeMismatch):
            run_output("print histogram([1], 2.5);")

    def test_the_drawn_form_has_a_line_per_bucket(self):
        assert len(lines_of("histogramLines([1, 2, 8], 3, 10)")) == 3


class TestSparklines:
    def test_a_sparkline_has_one_character_per_value(self):
        assert len(evaluate("sparkline([1, 2, 3, 4])")) == 4

    def test_the_lowest_and_highest_differ(self):
        drawn = evaluate("sparkline([1, 9])")
        assert drawn[0] != drawn[1]

    def test_a_rising_sequence_rises(self):
        drawn = evaluate("sparkline([1, 2, 3, 4, 5, 6, 7, 8])")
        assert drawn[0] != drawn[-1]

    def test_identical_values_draw_flat(self):
        assert len(set(evaluate("sparkline([4, 4, 4])"))) == 1

    def test_an_empty_list_draws_nothing(self):
        assert run_output("print sparkline([]);") == [""]

    def test_one_value_draws_one_character(self):
        assert len(evaluate("sparkline([7])")) == 1

    def test_negative_values_are_accepted(self):
        assert len(evaluate("sparkline([-5, 0, 5])")) == 3


class TestTables:
    def test_every_column_is_as_wide_as_its_widest_entry(self):
        rows = f"[[{quoted('name')}, {quoted('n')}], [{quoted('ada')}, {quoted('36')}]]"
        drawn = lines_of(f"table({rows})")
        assert drawn[0] == "name  n"
        assert drawn[1] == "ada   36"

    def test_numbers_are_shown_as_the_language_shows_them(self):
        drawn = lines_of("table([[1, 2.5]])")
        assert "2.5" in drawn[0]

    def test_a_short_row_is_padded(self):
        rows = f"[[{quoted('a')}, {quoted('b')}], [{quoted('c')}]]"
        drawn = lines_of(f"table({rows})")
        assert drawn[1] == "c"

    def test_an_empty_table_draws_nothing(self):
        assert lines_of("table([])") == []

    def test_a_row_that_is_not_a_list_is_refused(self):
        with pytest.raises(TypeMismatch) as caught:
            run_output(f"print table([{quoted('a')}]);")
        assert "each row to be a list" in str(caught.value)

    def test_something_that_is_not_a_list_is_refused(self):
        with pytest.raises(TypeMismatch):
            run_output("print table(5);")

    def test_trailing_spaces_are_trimmed(self):
        rows = f"[[{quoted('aa')}, {quoted('b')}], [{quoted('c')}, {quoted('d')}]]"
        for line in lines_of(f"table({rows})"):
            assert line == line.rstrip()


class TestAxes:
    def test_the_ends_are_marked(self):
        drawn = evaluate("axis(20, 0, 100)")
        assert drawn.startswith("0")
        assert drawn.endswith("100")

    def test_the_axis_is_the_width_asked_for(self):
        assert len(evaluate("axis(20, 0, 100)")) == 20

    def test_a_width_too_small_still_shows_both_ends(self):
        drawn = evaluate("axis(3, 100, 200)")
        assert "100" in drawn
        assert "200" in drawn

    def test_a_width_of_zero_is_refused(self):
        with pytest.raises(Arithmetic):
            run_output("print axis(0, 0, 1);")


class TestPercentageBars:
    def test_a_hundred_fills_the_width(self):
        drawn = lines_of("percentageBars([100], 10)")
        assert len(drawn[0]) == 10

    def test_a_half_fills_half(self):
        drawn = lines_of("percentageBars([50], 10)")
        assert len(drawn[0]) == 5

    def test_two_charts_drawn_separately_can_be_compared(self):
        # which is exactly what a chart scaled to its own largest cannot offer
        one = lines_of("percentageBars([50], 10)")[0]
        other = lines_of("percentageBars([50, 100], 10)")[0]
        assert one == other

    def test_a_small_percentage_still_draws(self):
        drawn = lines_of("percentageBars([1], 10)")
        assert len(drawn[0]) == 1

    def test_a_negative_percentage_is_refused(self):
        with pytest.raises(Arithmetic):
            run_output("print percentageBars([-1], 10);")


class TestBothBackendsAgree:
    @pytest.mark.parametrize(
        "expression",
        [
            "barChart([1, 5, 3], 10)",
            f"labelledBars([{quoted('a')}, {quoted('bb')}], [1, 2], 8)",
            "histogram([1, 2, 8, 9], 4)",
            "histogramLines([1, 2, 8], 3, 10)",
            "sparkline([1, 5, 2, 8])",
            f"table([[{quoted('a')}, {quoted('bb')}], [{quoted('ccc')}, {quoted('d')}]])",
            "axis(20, 0, 100)",
            "percentageBars([25, 50], 8)",
        ],
    )
    def test_the_two_backends_agree(self, expression):
        source = f"print {expression};"
        assert run_output(source) == run_treewalk_output(source)
