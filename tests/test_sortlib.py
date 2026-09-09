from __future__ import annotations

import pytest

from ember.errors import Arithmetic, TypeMismatch
from ember.interpreter import run_output, run_treewalk_output
from ember.sortlib import sort_names


def evaluate(expression: str) -> str:
    return run_output(f"print {expression};")[0]


class TestRegistration:
    def test_the_functions_are_named(self):
        assert "ordered" in sort_names()
        assert "search" in sort_names()

    def test_the_names_are_sorted(self):
        assert sort_names() == sorted(sort_names())

    def test_there_are_fourteen_of_them(self):
        assert len(sort_names()) == 14


class TestOrdering:
    def test_numbers_come_back_ascending(self):
        assert evaluate("ordered([3, 1, 2])") == "[1, 2, 3]"

    def test_strings_come_back_ascending(self):
        assert evaluate('ordered(["c", "a", "b"])') == '["a", "b", "c"]'

    def test_descending_is_the_other_direction(self):
        assert evaluate("orderedDown([1, 3, 2])") == "[3, 2, 1]"

    def test_an_empty_list_orders_to_nothing(self):
        assert evaluate("ordered([])") == "[]"

    def test_one_value_is_already_ordered(self):
        assert evaluate("ordered([5])") == "[5]"

    def test_a_mixture_of_numbers_and_strings_is_refused(self):
        # any order between them would be arbitrary
        with pytest.raises(TypeMismatch) as caught:
            run_output('print ordered([1, "a"]);')
        assert "arbitrary" in str(caught.value)

    def test_the_refusal_names_both_kinds(self):
        with pytest.raises(TypeMismatch) as caught:
            run_output('print ordered([1, "a"]);')
        message = str(caught.value)
        assert "int" in message
        assert "string" in message

    def test_the_refusal_suggests_what_to_do(self):
        with pytest.raises(TypeMismatch) as caught:
            run_output('print ordered([1, "a"]);')
        assert "one kind at a time" in str(caught.value)

    def test_something_other_than_a_list_is_refused(self):
        with pytest.raises(TypeMismatch):
            run_output("print ordered(5);")

    def test_an_ordered_list_is_recognised(self):
        assert evaluate("isOrdered([1, 2, 3])") == "true"

    def test_an_unordered_list_is_recognised(self):
        assert evaluate("isOrdered([3, 1])") == "false"

    def test_equal_neighbours_still_count_as_ordered(self):
        assert evaluate("isOrdered([1, 1, 2])") == "true"

    def test_an_empty_list_is_ordered(self):
        assert evaluate("isOrdered([])") == "true"

    def test_flipping_reverses_without_ordering(self):
        assert evaluate("flipped([3, 1, 2])") == "[2, 1, 3]"

    def test_flipping_twice_returns_the_original(self):
        assert evaluate("flipped(flipped([1, 2, 3]))") == "[1, 2, 3]"


class TestSearching:
    def test_a_present_value_is_found(self):
        assert evaluate("search([1, 3, 5, 7], 5)") == "2"

    def test_the_first_value_is_found(self):
        assert evaluate("search([1, 3, 5], 1)") == "0"

    def test_the_last_value_is_found(self):
        assert evaluate("search([1, 3, 5], 5)") == "2"

    def test_an_absent_value_gives_minus_one(self):
        assert evaluate("search([1, 3, 5], 4)") == "-1"

    def test_searching_nothing_gives_minus_one(self):
        assert evaluate("search([], 1)") == "-1"

    def test_strings_can_be_searched(self):
        assert evaluate('search(["a", "b", "c"], "b")') == "1"

    def test_an_uncomparable_needle_is_refused(self):
        with pytest.raises(TypeMismatch):
            run_output('print search([1, 2, 3], "a");')

    def test_the_insertion_point_of_a_new_value(self):
        assert evaluate("insertionPoint([1, 3, 5], 4)") == "2"

    def test_the_insertion_point_before_everything(self):
        assert evaluate("insertionPoint([1, 3], 0)") == "0"

    def test_the_insertion_point_after_everything(self):
        assert evaluate("insertionPoint([1, 3], 9)") == "2"

    def test_the_insertion_point_of_an_existing_value_goes_before_it(self):
        assert evaluate("insertionPoint([1, 3, 5], 3)") == "1"

    def test_inserting_there_keeps_the_list_ordered(self):
        source = "let a = [1, 3, 5]; let at = insertionPoint(a, 4); print at;"
        assert run_output(source) == ["2"]


class TestCountingAndDistinctness:
    def test_counting_tallies_each_value(self):
        assert evaluate('counted(["a", "b", "a"])') == '{"a": 2, "b": 1}'

    def test_counting_nothing_gives_an_empty_map(self):
        assert evaluate("counted([])") == "{}"

    def test_counting_numbers_works_too(self):
        assert evaluate("counted([1, 1, 2])") == "{1: 2, 2: 1}"

    def test_a_list_cannot_be_counted_as_a_key(self):
        with pytest.raises(TypeMismatch) as caught:
            run_output("print counted([[1]]);")
        assert "map keys" in str(caught.value)

    def test_distinct_keeps_the_first_appearance(self):
        assert evaluate("distinct([2, 1, 2, 3])") == "[2, 1, 3]"

    def test_distinct_of_nothing_is_nothing(self):
        assert evaluate("distinct([])") == "[]"

    def test_distinct_of_all_the_same_leaves_one(self):
        assert evaluate("distinct([4, 4, 4])") == "[4]"

    def test_the_most_common_value_wins(self):
        assert evaluate("mostCommon([1, 2, 2])") == "2"

    def test_a_tie_is_decided_by_arrival(self):
        assert evaluate("mostCommon([2, 1, 1, 2])") == "2"

    def test_the_most_common_of_nothing_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output("print mostCommon([]);")
        assert "empty list" in str(caught.value)


class TestReshaping:
    def test_chunking_splits_into_groups(self):
        assert evaluate("chunked([1, 2, 3, 4, 5], 2)") == "[[1, 2], [3, 4], [5]]"

    def test_a_chunk_size_larger_than_the_list_gives_one_chunk(self):
        assert evaluate("chunked([1, 2], 5)") == "[[1, 2]]"

    def test_chunking_nothing_gives_nothing(self):
        assert evaluate("chunked([], 2)") == "[]"

    def test_a_chunk_size_of_zero_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output("print chunked([1], 0);")
        assert "at least one" in str(caught.value)

    def test_a_chunk_size_that_is_not_whole_is_refused(self):
        with pytest.raises(TypeMismatch):
            run_output("print chunked([1], 1.5);")

    def test_windows_overlap(self):
        assert evaluate("windowed([1, 2, 3], 2)") == "[[1, 2], [2, 3]]"

    def test_a_window_the_size_of_the_list_gives_one(self):
        assert evaluate("windowed([1, 2], 2)") == "[[1, 2]]"

    def test_a_window_wider_than_the_list_gives_none(self):
        # no window of that width fits, which is no windows rather than a refusal
        assert evaluate("windowed([1, 2], 5)") == "[]"

    def test_a_window_size_of_zero_is_refused(self):
        with pytest.raises(Arithmetic):
            run_output("print windowed([1], 0);")

    def test_interleaving_alternates(self):
        assert evaluate("interleaved([1, 3], [2, 4])") == "[1, 2, 3, 4]"

    def test_interleaving_uneven_lists_keeps_the_remainder(self):
        assert evaluate("interleaved([1], [2, 3])") == "[1, 2, 3]"

    def test_interleaving_with_nothing_gives_the_other(self):
        assert evaluate("interleaved([1, 2], [])") == "[1, 2]"

    def test_rotating_moves_the_front_to_the_back(self):
        assert evaluate("rotated([1, 2, 3], 1)") == "[2, 3, 1]"

    def test_rotating_by_the_length_changes_nothing(self):
        assert evaluate("rotated([1, 2, 3], 3)") == "[1, 2, 3]"

    def test_rotating_past_the_length_wraps(self):
        assert evaluate("rotated([1, 2, 3], 4)") == "[2, 3, 1]"

    def test_rotating_backwards_wraps_the_other_way(self):
        assert evaluate("rotated([1, 2, 3], -1)") == "[3, 1, 2]"

    def test_rotating_nothing_gives_nothing(self):
        assert evaluate("rotated([], 2)") == "[]"

    def test_rotating_by_something_that_is_not_whole_is_refused(self):
        with pytest.raises(TypeMismatch):
            run_output("print rotated([1], 1.5);")

    def test_flattening_removes_one_level(self):
        assert evaluate("flattened([[1, 2], [3]])") == "[1, 2, 3]"

    def test_flattening_keeps_the_inner_shape(self):
        # one level only, so a list of lists of lists keeps its inner lists
        assert evaluate("flattened([[[1]], [2]])") == "[[1], 2]"

    def test_flattening_a_flat_list_changes_nothing(self):
        assert evaluate("flattened([1, 2])") == "[1, 2]"

    def test_flattening_nothing_gives_nothing(self):
        assert evaluate("flattened([])") == "[]"


class TestBothBackendsAgree:
    @pytest.mark.parametrize(
        "expression",
        [
            "ordered([3, 1, 2])",
            'orderedDown(["a", "c", "b"])',
            "isOrdered([1, 2, 2])",
            "flipped([1, 2, 3])",
            "search([1, 3, 5, 7, 9], 7)",
            "insertionPoint([1, 3, 5], 2)",
            'counted(["a", "a", "b"])',
            "distinct([1, 2, 1])",
            "mostCommon([3, 3, 1])",
            "chunked([1, 2, 3, 4], 3)",
            "windowed([1, 2, 3, 4], 2)",
            "interleaved([1, 2], [3])",
            "rotated([1, 2, 3, 4], 2)",
            "flattened([[1], [2, 3]])",
        ],
    )
    def test_the_two_backends_agree(self, expression):
        source = f"print {expression};"
        assert run_output(source) == run_treewalk_output(source)
