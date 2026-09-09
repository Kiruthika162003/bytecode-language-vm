from __future__ import annotations

import random
import statistics

import pytest

from ember.errors import Arithmetic, IndexRange, TypeMismatch
from ember.interpreter import run_output, run_treewalk_output
from ember.listlib import list_names
from ember.maplib import map_names
from ember.sortlib import sort_names
from ember.statlib import stat_names
from ember.tablelib import table_names

ROWS = """let rows = [
  {"name": "ada", "team": "one", "score": 91},
  {"name": "grace", "team": "two", "score": 78},
  {"name": "alan", "team": "one", "score": 84},
  {"name": "edsger", "team": "two", "score": 84}
];
"""
GAPPY = """let rows = [
  {"name": "ada", "score": 91},
  {"name": "grace"},
  {"name": "alan", "score": 84}
];
"""


def evaluate(expression: str, table: str = ROWS) -> str:
    return run_output(table + f"print {expression};")[0]


def printed(source: str) -> list[str]:
    return run_output(source)


def rendered(source: str) -> list[str]:
    """One print of a multi-line string is one line of output, so it is split here."""
    return run_output(source)[0].split(chr(10))


class TestRegistration:
    def test_every_function_is_named(self):
        assert "select" in table_names()
        assert "joinOn" in table_names()

    def test_the_names_are_sorted(self):
        assert table_names() == sorted(table_names())

    def test_there_are_twenty_three_of_them(self):
        assert len(table_names()) == 23

    def test_it_claims_no_name_another_library_already_has(self):
        taken = set(list_names()) | set(map_names())
        taken |= set(stat_names()) | set(sort_names())
        assert not set(table_names()) & taken


class TestColumns:
    def test_the_columns_are_the_union_across_rows(self):
        # a row missing a column still leaves the column in the table
        assert evaluate("columns(rows)", GAPPY) == '["name", "score"]'

    def test_the_columns_are_sorted(self):
        assert evaluate("columns(rows)") == '["name", "score", "team"]'

    def test_an_empty_table_has_no_columns(self):
        assert evaluate("columns([])") == "[]"

    def test_a_table_that_is_not_a_list_is_refused(self):
        with pytest.raises(TypeMismatch) as caught:
            run_output('print columns("rows");')
        assert "a list of maps" in str(caught.value)

    def test_a_row_that_is_not_a_map_is_refused_by_position(self):
        with pytest.raises(TypeMismatch) as caught:
            run_output('print columns([{"a": 1}, 7]);')
        assert "row 1" in str(caught.value)


class TestSelectingAndShaping:
    def test_selecting_keeps_only_the_named_columns(self):
        assert evaluate('select(rows, ["name"])') == (
            '[{"name": "ada"}, {"name": "grace"}, {"name": "alan"}, {"name": "edsger"}]'
        )

    def test_selecting_a_column_a_row_lacks_leaves_it_out(self):
        # inventing a value would be worse than a shorter row
        assert evaluate('select(rows, ["score"])', GAPPY) == (
            '[{"score": 91}, {}, {"score": 84}]'
        )

    def test_selecting_nothing_gives_empty_rows(self):
        assert evaluate("select(rows, [])") == "[{}, {}, {}, {}]"

    def test_selecting_does_not_change_the_original(self):
        source = ROWS + 'let kept = select(rows, ["name"]);' + "print columns(rows);"
        assert printed(source)[0] == '["name", "score", "team"]'

    def test_a_column_name_that_is_not_text_is_refused(self):
        with pytest.raises(TypeMismatch):
            run_output(ROWS + "print select(rows, [7]);")

    def test_dropping_a_column_removes_it_everywhere(self):
        assert evaluate('columns(dropColumn(rows, "team"))') == '["name", "score"]'

    def test_dropping_a_column_nothing_has_changes_nothing(self):
        assert evaluate('columns(dropColumn(rows, "nowhere"))') == (
            '["name", "score", "team"]'
        )

    def test_renaming_a_column_keeps_the_values(self):
        assert evaluate('renameColumn(select(rows, ["name"]), "name", "who")') == (
            '[{"who": "ada"}, {"who": "grace"}, {"who": "alan"}, {"who": "edsger"}]'
        )

    def test_renaming_to_an_existing_name_merges_into_it(self):
        assert evaluate('renameColumn([{"a": 1, "b": 2}], "a", "b")') == '{"b": 2}'.join(
            ["[", "]"]
        )

    def test_adding_a_column_gives_every_row_the_same_value(self):
        assert evaluate('addColumn([{"a": 1}, {"a": 2}], "tag", "x")') == (
            '[{"a": 1, "tag": "x"}, {"a": 2, "tag": "x"}]'
        )

    def test_adding_a_column_that_exists_replaces_it(self):
        assert evaluate('addColumn([{"a": 1}], "a", 9)') == '[{"a": 9}]'


class TestFiltering:
    def test_where_equals_keeps_the_matching_rows(self):
        assert evaluate('countBy(whereEquals(rows, "team", "one"), "team")') == (
            '{"one": 2}'
        )

    def test_where_equals_on_a_missing_column_matches_nothing(self):
        # a sentinel nothing in the language can equal, so an absent column never matches
        assert evaluate('whereEquals(rows, "nowhere", nil)') == "[]"

    def test_where_equals_finds_a_nil_that_is_really_there(self):
        assert evaluate('whereEquals([{"a": nil}], "a", nil)') == '[{"a": nil}]'

    def test_where_above_keeps_the_larger_values(self):
        assert evaluate('select(whereAbove(rows, "score", 84), ["name"])') == (
            '[{"name": "ada"}]'
        )

    def test_where_above_excludes_the_boundary(self):
        assert evaluate('whereAbove([{"a": 5}], "a", 5)') == "[]"

    def test_where_above_skips_rows_without_the_column(self):
        assert evaluate('whereAbove(rows, "score", 0)', GAPPY).count("name") == 2

    def test_where_above_refuses_a_non_number_floor(self):
        with pytest.raises(TypeMismatch) as caught:
            run_output(ROWS + 'print whereAbove(rows, "score", "x");')
        assert "compares against a number" in str(caught.value)

    def test_where_above_refuses_text_in_the_column(self):
        with pytest.raises(TypeMismatch) as caught:
            run_output('print whereAbove([{"a": "x"}], "a", 1);')
        assert "row 0 holds a string" in str(caught.value)

    def test_where_present_finds_the_rows_that_have_the_column(self):
        assert evaluate('wherePresent(rows, "score")', GAPPY).count("name") == 2

    def test_where_present_on_a_column_all_rows_have_keeps_them_all(self):
        assert evaluate('wherePresent(rows, "name")', GAPPY).count("name") == 3


class TestOrdering:
    def test_ordering_by_text_sorts_alphabetically(self):
        assert evaluate('select(orderBy(rows, "name"), ["name"])') == (
            '[{"name": "ada"}, {"name": "alan"}, {"name": "edsger"}, {"name": "grace"}]'
        )

    def test_ordering_by_number_sorts_upwards(self):
        assert evaluate('select(orderBy(rows, "score"), ["name"])') == (
            '[{"name": "grace"}, {"name": "alan"}, {"name": "edsger"}, {"name": "ada"}]'
        )

    def test_a_tie_keeps_the_order_the_rows_arrived_in(self):
        # alan comes before edsger in the table and they share a score
        ordered = evaluate('select(orderBy(rows, "score"), ["name"])')
        assert ordered.index("alan") < ordered.index("edsger")

    def test_ordering_downwards_reverses_the_values(self):
        assert evaluate('select(orderByDescending(rows, "score"), ["name"])') == (
            '[{"name": "ada"}, {"name": "alan"}, {"name": "edsger"}, {"name": "grace"}]'
        )

    def test_a_tie_keeps_its_order_downwards_too(self):
        ordered = evaluate('select(orderByDescending(rows, "score"), ["name"])')
        assert ordered.index("alan") < ordered.index("edsger")

    def test_a_row_without_the_column_sorts_last(self):
        assert evaluate('select(orderBy(rows, "score"), ["name"])', GAPPY) == (
            '[{"name": "alan"}, {"name": "ada"}, {"name": "grace"}]'
        )

    def test_a_column_mixing_numbers_and_text_is_refused(self):
        # this raised a host error before the check existed
        with pytest.raises(TypeMismatch) as caught:
            run_output('print orderBy([{"a": 1}, {"a": "x"}], "a");')
        assert "mixes numbers and text" in str(caught.value)

    def test_a_column_holding_a_list_is_refused(self):
        with pytest.raises(TypeMismatch) as caught:
            run_output('print orderBy([{"a": [1]}], "a");')
        assert "only numbers and text have an order" in str(caught.value)

    def test_a_column_holding_a_boolean_is_refused(self):
        with pytest.raises(TypeMismatch):
            run_output('print orderBy([{"a": true}], "a");')

    def test_ordering_an_empty_table_gives_an_empty_table(self):
        assert evaluate('orderBy([], "a")') == "[]"

    def test_the_top_rows_come_off_the_descending_order(self):
        assert evaluate('select(topBy(rows, "score", 2), ["name"])') == (
            '[{"name": "ada"}, {"name": "alan"}]'
        )

    def test_asking_for_more_than_there_are_gives_them_all(self):
        assert evaluate('topBy(rows, "score", 99)').count("name") == 4

    def test_asking_for_none_gives_none(self):
        assert evaluate('topBy(rows, "score", 0)') == "[]"

    def test_a_negative_count_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output(ROWS + 'print topBy(rows, "score", -1);')
        assert "zero or more" in str(caught.value)

    def test_a_fractional_count_is_refused(self):
        with pytest.raises(TypeMismatch):
            run_output(ROWS + 'print topBy(rows, "score", 1.5);')


class TestGrouping:
    def test_grouping_splits_by_the_column(self):
        assert evaluate('countBy(rows, "team")') == '{"one": 2, "two": 2}'

    def test_a_group_holds_the_whole_rows(self):
        source = ROWS + 'let g = groupBy(rows, "team");' + 'print get(g, "one", [])[0];'
        assert printed(source)[0] == '{"name": "ada", "team": "one", "score": 91}'

    def test_the_groups_keep_the_order_the_values_first_appeared(self):
        assert evaluate('keys(countBy(rows, "team"))') == '["one", "two"]'

    def test_grouping_on_a_column_a_row_lacks_is_refused_by_position(self):
        with pytest.raises(IndexRange) as caught:
            run_output(GAPPY + 'print groupBy(rows, "score");')
        assert "row 1 does not have it" in str(caught.value)

    def test_the_refusal_names_the_columns_that_row_does_have(self):
        with pytest.raises(IndexRange) as caught:
            run_output(GAPPY + 'print groupBy(rows, "score");')
        assert "that row has name" in str(caught.value)

    def test_grouping_on_a_list_valued_column_is_refused(self):
        with pytest.raises(TypeMismatch) as caught:
            run_output('print groupBy([{"a": [1]}], "a");')
        assert "a group key must be a single value" in str(caught.value)

    def test_counting_by_a_column_sums_to_the_row_count(self):
        source = ROWS + 'print sum(values(countBy(rows, "team")));'
        assert printed(source)[0] == "4"

    def test_distinct_values_come_out_once_in_first_seen_order(self):
        assert evaluate('distinctValues(rows, "team")') == '["one", "two"]'

    def test_distinct_values_skips_rows_without_the_column(self):
        assert evaluate('distinctValues(rows, "score")', GAPPY) == "[91, 84]"

    def test_distinct_values_of_a_column_nothing_has_is_empty(self):
        assert evaluate('distinctValues(rows, "nowhere")') == "[]"


class TestAggregating:
    def test_summing_adds_the_column(self):
        assert evaluate('sumBy(rows, "score")') == "337"

    def test_summing_a_column_nothing_has_gives_zero(self):
        # nothing to add is zero, unlike a mean over nothing, which has no answer
        assert evaluate('sumBy(rows, "nowhere")') == "0"

    def test_summing_skips_rows_without_the_column(self):
        assert evaluate('sumBy(rows, "score")', GAPPY) == "175"

    def test_summing_refuses_text_in_the_column(self):
        with pytest.raises(TypeMismatch) as caught:
            run_output('print sumBy([{"a": "x"}], "a");')
        assert "needs numbers in the column" in str(caught.value)

    def test_the_mean_is_over_the_rows_that_have_the_column(self):
        # 175 over two rows, not over three, which is the whole point
        assert evaluate('meanBy(rows, "score")', GAPPY) == "87.5"

    def test_a_mean_over_no_rows_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output(ROWS + 'print meanBy(rows, "nowhere");')
        assert "there is no mean" in str(caught.value)

    def test_the_largest_row_comes_back_whole(self):
        assert evaluate('maxBy(rows, "score")') == (
            '{"name": "ada", "team": "one", "score": 91}'
        )

    def test_the_smallest_row_comes_back_whole(self):
        assert evaluate('minBy(rows, "score")') == (
            '{"name": "grace", "team": "two", "score": 78}'
        )

    def test_the_largest_by_text_is_the_last_alphabetically(self):
        assert evaluate('maxBy(rows, "name")')  # smoke, the value is checked below
        assert "grace" in evaluate('maxBy(rows, "name")')

    def test_a_largest_over_no_rows_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output('print maxBy([], "a");')
        assert "there is no largest" in str(caught.value)

    def test_a_smallest_over_no_rows_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output('print minBy([], "a");')
        assert "there is no smallest" in str(caught.value)

    def test_a_largest_over_rows_that_all_lack_the_column_is_refused(self):
        with pytest.raises(Arithmetic):
            run_output(ROWS + 'print maxBy(rows, "nowhere");')


class TestJoining:
    TEAMS = 'let teams = [{"team": "one", "city": "london"}, ' + (
        '{"team": "two", "city": "leiden"}];'
    )

    def test_a_join_brings_the_other_columns_across(self):
        source = ROWS + self.TEAMS + 'print joinOn(rows, teams, "team")[0];'
        assert printed(source)[0] == (
            '{"name": "ada", "team": "one", "score": 91, "city": "london"}'
        )

    def test_a_join_keeps_every_matching_pair(self):
        source = ROWS + self.TEAMS + 'print len(joinOn(rows, teams, "team"));'
        assert printed(source)[0] == "4"

    def test_an_unmatched_left_row_is_dropped_by_the_inner_join(self):
        source = (
            '{"team": "three"}]'.join([ROWS.rstrip(";" + chr(10)) + " + [", ";" + chr(10)])
            + self.TEAMS
            + 'print len(joinOn(rows, teams, "team"));'
        )
        assert printed(source)[0] == "4"

    def test_a_left_join_keeps_the_unmatched_row(self):
        source = (
            'let rows = [{"team": "three", "name": "x"}];'
            + self.TEAMS
            + 'print leftJoinOn(rows, teams, "team");'
        )
        assert printed(source)[0] == '[{"team": "three", "name": "x"}]'

    def test_a_left_join_invents_nothing_for_the_missing_columns(self):
        source = (
            'let rows = [{"team": "three"}];'
            + self.TEAMS
            + 'print columns(leftJoinOn(rows, teams, "team"));'
        )
        assert printed(source)[0] == '["team"]'

    def test_the_right_side_wins_a_collision(self):
        source = (
            'let left = [{"k": 1, "v": "left"}];'
            'let right = [{"k": 1, "v": "right"}];'
            'print joinOn(left, right, "k");'
        )
        assert printed(source)[0] == '[{"k": 1, "v": "right"}]'

    def test_two_matching_right_rows_give_two_result_rows(self):
        source = (
            'let left = [{"k": 1}];'
            'let right = [{"k": 1, "n": 1}, {"k": 1, "n": 2}];'
            'print len(joinOn(left, right, "k"));'
        )
        assert printed(source)[0] == "2"

    def test_a_left_row_without_the_key_is_refused(self):
        with pytest.raises(IndexRange) as caught:
            run_output('print joinOn([{"a": 1}], [{"k": 1}], "k");')
        assert "row 0 does not have it" in str(caught.value)

    def test_a_right_row_without_the_key_is_refused(self):
        with pytest.raises(IndexRange):
            run_output('print joinOn([{"k": 1}], [{"a": 1}], "k");')

    def test_a_join_against_nothing_gives_nothing(self):
        source = ROWS + 'print joinOn(rows, [], "team");'
        assert printed(source)[0] == "[]"


class TestTurningItSideways:
    def test_the_columns_come_out_as_lists(self):
        assert evaluate('rowsToColumns([{"a": 1}, {"a": 2}])') == '{"a": [1, 2]}'

    def test_a_gap_becomes_nil_in_the_column(self):
        # the column has to be as long as the table, so a gap needs a filler here
        assert evaluate('rowsToColumns([{"a": 1}, {}])') == '{"a": [1, nil]}'

    def test_turning_it_back_recovers_the_rows(self):
        assert evaluate('columnsToRows(rowsToColumns([{"a": 1}, {"a": 2}]))') == (
            '[{"a": 1}, {"a": 2}]'
        )

    def test_the_round_trip_keeps_every_column(self):
        assert evaluate("columns(columnsToRows(rowsToColumns(rows)))") == (
            '["name", "score", "team"]'
        )

    def test_columns_of_different_lengths_are_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output('print columnsToRows({"a": [1], "b": [1, 2]});')
        assert "the same count of values" in str(caught.value)

    def test_a_column_that_is_not_a_list_is_refused(self):
        with pytest.raises(TypeMismatch) as caught:
            run_output('print columnsToRows({"a": 1});')
        assert "needs a list for the column" in str(caught.value)

    def test_something_that_is_not_a_map_is_refused(self):
        with pytest.raises(TypeMismatch):
            run_output("print columnsToRows([1]);")

    def test_no_columns_gives_no_rows(self):
        assert evaluate("columnsToRows({})") == "[]"


class TestRendering:
    def test_the_heading_names_the_columns(self):
        source = ROWS + 'print tableText(rows, ["name", "score"]);'
        assert rendered(source)[0] == "name    score"

    def test_a_rule_separates_the_heading(self):
        source = ROWS + 'print tableText(rows, ["name", "score"]);'
        assert rendered(source)[1] == "------  -----"

    def test_every_row_gets_a_line(self):
        source = ROWS + 'print tableText(rows, ["name"]);'
        assert len(rendered(source)) == 6

    def test_a_column_is_as_wide_as_its_widest_value(self):
        source = 'print tableText([{"a": "wide value"}], ["a"]);'
        assert rendered(source)[1] == "-" * len("wide value")

    def test_a_gap_is_left_blank(self):
        source = GAPPY + 'print tableText(rows, ["score"]);'
        assert rendered(source)[3] == ""

    def test_a_boolean_shows_as_the_language_writes_it(self):
        source = 'print tableText([{"a": true}, {"a": false}], ["a"]);'
        assert rendered(source)[2] == "true"
        assert rendered(source)[3] == "false"

    def test_a_whole_float_loses_its_point(self):
        source = 'print tableText([{"a": 3.0}], ["a"]);'
        assert rendered(source)[2] == "3"

    def test_asking_for_no_columns_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output(ROWS + "print tableText(rows, []);")
        assert "at least one column" in str(caught.value)

    def test_the_rendering_is_ascii(self):
        source = ROWS + 'print tableText(rows, ["name", "team", "score"]);'
        assert all(ord(character) < 128 for character in chr(10).join(rendered(source)))

    def test_a_trailing_gap_leaves_no_trailing_spaces(self):
        # a line padded to the last column's width would carry invisible spaces
        source = 'print tableText([{"a": 1, "b": 2}, {"a": 1}], ["a", "b"]);'
        assert rendered(source)[3] == "1"


class TestAgainstTheHost:
    """The host is an independent implementation of every one of these operations."""

    def _table(self, seed: int) -> list[dict[str, object]]:
        source = random.Random(seed)
        return [
            {
                "k": source.choice(["a", "b", "c"]),
                "n": source.randrange(0, 50),
            }
            for _ in range(source.randrange(1, 12))
        ]

    def _literal(self, rows: list[dict[str, object]]) -> str:
        parts = [
            "{" + f'"k": "{row["k"]}", "n": {row["n"]}' + "}" for row in rows
        ]
        return "[" + ", ".join(parts) + "]"

    @pytest.mark.parametrize("seed", range(40))
    def test_the_sum_matches_the_host(self, seed):
        rows = self._table(seed)
        source = f'print sumBy({self._literal(rows)}, "n");'
        assert printed(source)[0] == str(sum(row["n"] for row in rows))

    @pytest.mark.parametrize("seed", range(40))
    def test_the_mean_matches_the_host(self, seed):
        rows = self._table(seed)
        source = f'print meanBy({self._literal(rows)}, "n");'
        expected = statistics.fmean(row["n"] for row in rows)
        assert abs(float(printed(source)[0]) - expected) < 1e-9

    @pytest.mark.parametrize("seed", range(40))
    def test_the_ordering_matches_the_host(self, seed):
        rows = self._table(seed)
        source = f'print orderBy({self._literal(rows)}, "n");'
        expected = self._literal(sorted(rows, key=lambda row: row["n"]))
        assert printed(source)[0].replace(", ", ", ") == expected

    @pytest.mark.parametrize("seed", range(40))
    def test_the_counts_match_the_host(self, seed):
        rows = self._table(seed)
        source = f'print countBy({self._literal(rows)}, "k");'
        counted: dict[str, int] = {}
        for row in rows:
            counted[row["k"]] = counted.get(row["k"], 0) + 1
        expected = "{" + ", ".join(f'"{k}": {v}' for k, v in counted.items()) + "}"
        assert printed(source)[0] == expected

    @pytest.mark.parametrize("seed", range(40))
    def test_the_top_rows_match_the_host(self, seed):
        rows = self._table(seed)
        source = f'print topBy({self._literal(rows)}, "n", 3);'
        expected = self._literal(
            sorted(rows, key=lambda row: row["n"], reverse=True)[:3]
        )
        assert printed(source)[0] == expected

    @pytest.mark.parametrize("seed", range(20))
    def test_the_join_matches_the_host(self, seed):
        left = self._table(seed)
        right = self._table(seed + 500)
        source = (
            f"print len(joinOn({self._literal(left)}, {self._literal(right)}, "
            '"k"));'
        )
        expected = sum(
            1 for one in left for other in right if one["k"] == other["k"]
        )
        assert printed(source)[0] == str(expected)

    @pytest.mark.parametrize("seed", range(20))
    def test_the_left_join_keeps_every_left_row(self, seed):
        left = self._table(seed)
        right = self._table(seed + 500)
        source = (
            f"print len(leftJoinOn({self._literal(left)}, {self._literal(right)}, "
            '"k"));'
        )
        expected = sum(
            max(1, sum(1 for other in right if other["k"] == one["k"])) for one in left
        )
        assert printed(source)[0] == str(expected)


class TestBothBackendsAgree:
    @pytest.mark.parametrize(
        "expression",
        [
            "columns(rows)",
            'select(rows, ["name", "score"])',
            'dropColumn(rows, "team")',
            'renameColumn(rows, "name", "who")',
            'addColumn(rows, "tag", 1)',
            'whereEquals(rows, "team", "one")',
            'whereAbove(rows, "score", 80)',
            'wherePresent(rows, "score")',
            'orderBy(rows, "name")',
            'orderByDescending(rows, "score")',
            'topBy(rows, "score", 2)',
            'countBy(rows, "team")',
            'distinctValues(rows, "team")',
            'sumBy(rows, "score")',
            'meanBy(rows, "score")',
            'maxBy(rows, "score")',
            'minBy(rows, "score")',
            "rowsToColumns(rows)",
            "columnsToRows(rowsToColumns(rows))",
            'tableText(rows, ["name", "score"])',
        ],
    )
    def test_the_two_backends_agree(self, expression):
        source = ROWS + f"print {expression};"
        assert run_output(source) == run_treewalk_output(source)
