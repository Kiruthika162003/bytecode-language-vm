from __future__ import annotations

import itertools
import random

import pytest

from ember.difflib import (
    DELETE,
    INSERT,
    KEEP,
    Difference,
    Operation,
    applied,
    diff_names,
    difference,
    edit_distance,
    longest_common,
    similarity,
)
from ember.errors import Arithmetic, TypeMismatch
from ember.interpreter import run_output, run_treewalk_output

QUOTE = chr(34)


def evaluate(expression: str) -> str:
    return run_output(f"print {expression};")[0]


def brute_length(left: list[str], right: list[str]) -> int:
    """The longest common subsequence by exhaustive search, usable only when small."""

    def is_subsequence(small: list[str], big: list[str]) -> bool:
        walker = iter(big)
        return all(any(one == other for other in walker) for one in small)

    for size in range(len(left), -1, -1):
        for combination in itertools.combinations(left, size):
            if is_subsequence(list(combination), right):
                return size
    return 0


class TestAgainstAnExhaustiveSearch:
    def test_three_hundred_random_pairs_match(self):
        # the host's sequence matcher solves a different problem, so it is not the
        # oracle here: it finds contiguous blocks rather than a subsequence
        chooser = random.Random(7)
        for _ in range(300):
            left = [chooser.choice("abc") for _ in range(chooser.randrange(0, 8))]
            right = [chooser.choice("abc") for _ in range(chooser.randrange(0, 8))]
            assert len(longest_common(left, right)) == brute_length(left, right)

    def test_the_case_the_host_gets_shorter(self):
        left, right = list("abcabba"), list("cbabac")
        assert len(longest_common(left, right)) == 4
        assert brute_length(left, right) == 4

    @pytest.mark.parametrize(
        "left,right,expected",
        [
            ("abc", "abc", 3),
            ("abc", "", 0),
            ("", "abc", 0),
            ("abc", "cba", 1),
            ("kitten", "sitting", 4),
            ("aaa", "aa", 2),
        ],
    )
    def test_known_lengths(self, left, right, expected):
        assert len(longest_common(list(left), list(right))) == expected


class TestTheDifference:
    def test_identical_sequences_keep_everything(self):
        found = difference([1, 2, 3], [1, 2, 3])
        assert found.kept == 3
        assert found.identical

    def test_an_inserted_element_is_reported(self):
        found = difference([1, 3], [1, 2, 3])
        assert found.inserted == 1
        assert found.deleted == 0

    def test_a_deleted_element_is_reported(self):
        found = difference([1, 2, 3], [1, 3])
        assert found.deleted == 1
        assert found.inserted == 0

    def test_a_replacement_is_a_deletion_and_an_insertion(self):
        found = difference([1, 2], [1, 9])
        assert found.deleted == 1
        assert found.inserted == 1

    def test_a_deletion_comes_before_an_insertion(self):
        # the conventional order, which affects only how the result reads
        found = difference([1, 2], [1, 9])
        kinds = [one.kind for one in found.operations]
        assert kinds.index(DELETE) < kinds.index(INSERT)

    def test_everything_deleted_when_the_second_is_empty(self):
        found = difference([1, 2, 3], [])
        assert found.deleted == 3
        assert found.kept == 0

    def test_everything_inserted_when_the_first_is_empty(self):
        found = difference([], [1, 2, 3])
        assert found.inserted == 3

    def test_two_empty_sequences_are_identical(self):
        assert difference([], []).identical

    def test_the_shared_elements_can_be_asked_for(self):
        assert difference([1, 2, 3], [1, 3]).shared() == [1, 3]

    def test_the_changed_operations_can_be_asked_for(self):
        found = difference([1, 2, 3], [1, 3])
        assert len(found.changed_only()) == 1

    def test_the_summary_names_the_counts(self):
        rendered = difference([1, 2], [1, 9]).summary()
        assert "1 kept" in rendered
        assert "1 inserted" in rendered
        assert "1 deleted" in rendered


class TestApplying:
    @pytest.mark.parametrize(
        "left,right",
        [
            ([1, 2, 3], [1, 3]),
            ([1, 3], [1, 2, 3]),
            ([], [1]),
            ([1], []),
            ([1, 2, 3], [3, 2, 1]),
            (list("kitten"), list("sitting")),
        ],
    )
    def test_a_difference_rebuilds_the_second_sequence(self, left, right):
        assert applied(left, difference(left, right)) == right

    def test_applying_a_difference_from_elsewhere_is_refused(self):
        found = difference([1, 2], [1, 3])
        with pytest.raises(Arithmetic) as caught:
            applied([9, 9], found)
        assert "does not describe this sequence" in str(caught.value)

    def test_deleting_something_absent_is_refused(self):
        made = Difference(operations=[Operation(DELETE, 9)])
        with pytest.raises(Arithmetic) as caught:
            applied([1], made)
        assert "not there" in str(caught.value)

    def test_a_difference_that_covers_too_little_is_refused(self):
        made = Difference(operations=[Operation(KEEP, 1)])
        with pytest.raises(Arithmetic) as caught:
            applied([1, 2], made)
        assert "accounts for 1 of the 2" in str(caught.value)

    def test_a_difference_of_only_insertions_needs_an_empty_source(self):
        made = Difference(operations=[Operation(INSERT, 1)])
        assert applied([], made) == [1]


class TestRatios:
    def test_identical_sequences_score_one(self):
        assert similarity([1, 2, 3], [1, 2, 3]) == 1.0

    def test_disjoint_sequences_score_zero(self):
        assert similarity([1, 2], [3, 4]) == 0.0

    def test_two_empty_sequences_score_one(self):
        assert similarity([], []) == 1.0

    def test_a_partial_match_scores_between(self):
        assert 0.0 < similarity([1, 2, 3], [1, 2, 9]) < 1.0

    def test_the_ratio_is_twice_the_shared_over_the_total(self):
        # named because a ratio over the longer input is also common
        found = difference([1, 2, 3], [1, 2])
        assert found.ratio(3, 2) == pytest.approx(2 * 2 / 5)

    def test_the_distance_counts_both_directions(self):
        assert edit_distance([1, 2, 3], [1, 9, 3]) == 2

    def test_identical_sequences_are_no_distance_apart(self):
        assert edit_distance([1, 2], [1, 2]) == 0

    def test_the_distance_to_nothing_is_the_length(self):
        assert edit_distance([1, 2, 3], []) == 3


class TestRendering:
    def test_a_kept_element_is_unmarked(self):
        assert Operation(KEEP, "x").render() == "  x"

    def test_an_insertion_is_marked_with_a_plus(self):
        assert Operation(INSERT, "x").render() == "+ x"

    def test_a_deletion_is_marked_with_a_minus(self):
        assert Operation(DELETE, "x").render() == "- x"

    def test_a_difference_renders_a_line_per_operation(self):
        found = difference([1, 2], [1, 9])
        assert len(found.render()) == len(found.operations)


class TestTheSizeLimit:
    def test_a_large_comparison_is_refused(self):
        # the cost is the product of the lengths, so it refuses rather than consuming
        left = list(range(3000))
        right = list(range(3000))
        with pytest.raises(Arithmetic) as caught:
            difference(left, right)
        assert "past the limit" in str(caught.value)

    def test_the_refusal_names_both_lengths(self):
        with pytest.raises(Arithmetic) as caught:
            difference(list(range(3000)), list(range(3000)))
        assert "3000 against 3000" in str(caught.value)

    def test_a_comparison_inside_the_limit_is_allowed(self):
        assert difference(list(range(500)), list(range(500))).identical


class TestFromPrograms:
    def test_the_functions_are_named(self):
        assert "diff" in diff_names()
        assert "similarity" in diff_names()

    def test_the_names_are_sorted(self):
        assert diff_names() == sorted(diff_names())

    def test_there_are_seven_of_them(self):
        assert len(diff_names()) == 7

    def test_a_program_can_find_the_shared_elements(self):
        assert evaluate("shared([1, 2, 3], [1, 3])") == "[1, 3]"

    def test_a_program_can_ask_for_a_difference(self):
        found = evaluate("diff([1, 2], [1, 9])")
        assert QUOTE + "delete" + QUOTE in found
        assert QUOTE + "insert" + QUOTE in found

    def test_each_step_is_a_kind_and_a_value(self):
        source = "let d = diff([1, 2], [1, 9]); print d[1][0]; print d[1][1];"
        assert run_output(source) == ["delete", "2"]

    def test_a_program_can_apply_a_difference(self):
        source = "let a = [1, 2, 3]; let b = [1, 3, 4]; print applyDiff(a, diff(a, b));"
        assert run_output(source) == ["[1, 3, 4]"]

    def test_a_program_can_ask_for_a_ratio(self):
        assert evaluate("similarity([1, 2, 3], [1, 2, 3])") == "1.0"

    def test_a_program_can_ask_for_a_distance(self):
        assert evaluate("editDistance([1, 2, 3], [1, 9, 3])") == "2"

    def test_a_program_can_ask_whether_anything_changed(self):
        assert evaluate("unchanged([1, 2], [1, 2])") == "true"
        assert evaluate("unchanged([1, 2], [1, 3])") == "false"

    def test_a_program_can_render_a_difference(self):
        left = "[" + QUOTE + "x" + QUOTE + "]"
        right = "[" + QUOTE + "y" + QUOTE + "]"
        found = evaluate(f"diffLines({left}, {right})")
        assert "- x" in found
        assert "+ y" in found

    def test_something_that_is_not_a_list_is_refused(self):
        with pytest.raises(TypeMismatch):
            run_output("print diff(1, [1]);")

    def test_a_malformed_step_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output("print applyDiff([1], [[1]]);")
        assert "list of two values" in str(caught.value)

    def test_an_unknown_kind_is_refused(self):
        source = "print applyDiff([1], [[" + QUOTE + "muddle" + QUOTE + ", 1]]);"
        with pytest.raises(Arithmetic) as caught:
            run_output(source)
        assert "not one of keep, insert or delete" in str(caught.value)


class TestBothBackendsAgree:
    @pytest.mark.parametrize(
        "expression",
        [
            "shared([1, 2, 3], [1, 3])",
            "diff([1, 2, 3], [1, 9, 3])",
            "similarity([1, 2, 3], [1, 2])",
            "editDistance([1, 2, 3], [3, 2, 1])",
            "unchanged([1, 2], [1, 2])",
            "applyDiff([1, 2], diff([1, 2], [2, 3]))",
        ],
    )
    def test_the_two_backends_agree(self, expression):
        source = f"print {expression};"
        assert run_output(source) == run_treewalk_output(source)
