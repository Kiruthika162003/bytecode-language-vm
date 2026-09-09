from __future__ import annotations

import pytest

from ember.errors import Arithmetic, TypeMismatch
from ember.heaplib import heap_names, holds_invariant
from ember.interpreter import run_output, run_treewalk_output


def evaluate(expression: str) -> str:
    return run_output(f"print {expression};")[0]


class TestRegistration:
    def test_the_functions_are_named(self):
        assert "heapify" in heap_names()
        assert "heapPop" in heap_names()

    def test_the_names_are_sorted(self):
        assert heap_names() == sorted(heap_names())

    def test_there_are_thirteen_of_them(self):
        assert len(heap_names()) == 13


class TestTheInvariant:
    def test_an_empty_list_holds_it(self):
        assert holds_invariant([])

    def test_one_value_holds_it(self):
        assert holds_invariant([5])

    def test_an_ordered_list_holds_it(self):
        assert holds_invariant([1, 2, 3, 4, 5])

    def test_a_heap_need_not_be_sorted(self):
        assert holds_invariant([1, 3, 2, 5, 9, 8])

    def test_a_parent_larger_than_a_child_breaks_it(self):
        assert not holds_invariant([5, 1])

    def test_a_deeper_violation_is_caught(self):
        assert not holds_invariant([1, 2, 3, 4, 0])

    def test_a_list_of_mixed_types_does_not_hold_it(self):
        assert not holds_invariant([1, "a"])

    def test_a_program_can_ask(self):
        assert evaluate("isHeap([1, 2, 3])") == "true"
        assert evaluate("isHeap([3, 1])") == "false"


class TestHeapify:
    def test_a_list_becomes_a_heap(self):
        assert evaluate("isHeap(heapify([5, 3, 8, 1, 9, 2]))") == "true"

    def test_the_smallest_reaches_the_front(self):
        assert evaluate("heapPeek(heapify([5, 3, 8, 1]))") == "1"

    def test_an_empty_list_heapifies_to_nothing(self):
        assert evaluate("heapify([])") == "[]"

    def test_one_value_is_already_a_heap(self):
        assert evaluate("heapify([7])") == "[7]"

    def test_heapifying_keeps_every_value(self):
        assert evaluate("ordered(heapify([5, 3, 8, 1]))") == "[1, 3, 5, 8]"

    def test_heapifying_twice_changes_nothing_further(self):
        assert evaluate("heapify(heapify([5, 3, 8, 1]))") == evaluate("heapify([5, 3, 8, 1])")

    def test_strings_can_be_heaped(self):
        assert evaluate('heapPeek(heapify(["c", "a", "b"]))') == "a"

    def test_a_mixture_of_types_is_refused(self):
        with pytest.raises(TypeMismatch) as caught:
            run_output('print heapify([1, "a"]);')
        assert "cannot order" in str(caught.value)

    def test_something_that_is_not_a_list_is_refused(self):
        with pytest.raises(TypeMismatch):
            run_output("print heapify(5);")


class TestPushingAndPopping:
    def test_pushing_keeps_the_invariant(self):
        assert evaluate("isHeap(heapPush(heapify([2, 4, 6]), 1))") == "true"

    def test_a_smaller_value_becomes_the_front(self):
        assert evaluate("heapPeek(heapPush(heapify([2, 4, 6]), 1))") == "1"

    def test_a_larger_value_does_not(self):
        assert evaluate("heapPeek(heapPush(heapify([2, 4, 6]), 9))") == "2"

    def test_pushing_onto_nothing_gives_one_value(self):
        assert evaluate("heapPush([], 3)") == "[3]"

    def test_popping_removes_the_smallest(self):
        assert evaluate("heapPeek(heapPop(heapify([3, 1, 2])))") == "2"

    def test_popping_keeps_the_invariant(self):
        assert evaluate("isHeap(heapPop(heapify([5, 3, 8, 1, 9, 2])))") == "true"

    def test_popping_shortens_the_heap(self):
        assert evaluate("heapSize(heapPop(heapify([1, 2, 3])))") == "2"

    def test_popping_the_last_value_leaves_nothing(self):
        assert evaluate("heapPop([1])") == "[]"

    def test_popping_nothing_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output("print heapPop([]);")
        assert "empty" in str(caught.value)

    def test_peeking_at_nothing_is_refused(self):
        with pytest.raises(Arithmetic):
            run_output("print heapPeek([]);")

    def test_replacing_swaps_the_smallest_for_a_new_value(self):
        assert evaluate("heapPeek(heapReplace(heapify([1, 2, 3]), 9))") == "2"

    def test_replacing_keeps_the_size(self):
        assert evaluate("heapSize(heapReplace(heapify([1, 2, 3]), 9))") == "3"

    def test_replacing_keeps_the_invariant(self):
        assert evaluate("isHeap(heapReplace(heapify([1, 2, 3, 4, 5]), 9))") == "true"

    def test_replacing_in_nothing_is_refused(self):
        with pytest.raises(Arithmetic):
            run_output("print heapReplace([], 1);")


class TestNothingIsModified:
    def test_pushing_leaves_the_original_alone(self):
        # assignment shares a list, so a mutating push would change every binding
        source = "let h = heapify([2, 4]); let g = heapPush(h, 1); print h;"
        assert run_output(source) == ["[2, 4]"]

    def test_popping_leaves_the_original_alone(self):
        source = "let h = heapify([2, 4]); let g = heapPop(h); print h;"
        assert run_output(source) == ["[2, 4]"]

    def test_heapifying_leaves_the_original_alone(self):
        source = "let a = [5, 1]; let h = heapify(a); print a;"
        assert run_output(source) == ["[5, 1]"]

    def test_replacing_leaves_the_original_alone(self):
        source = "let h = heapify([1, 2]); let g = heapReplace(h, 9); print h;"
        assert run_output(source) == ["[1, 2]"]


class TestRefusingABrokenHeap:
    def test_pushing_onto_a_broken_heap_is_refused(self):
        # a wrong answer would be worse than a refusal
        with pytest.raises(Arithmetic) as caught:
            run_output("print heapPush([5, 1], 3);")
        assert "not a heap" in str(caught.value)

    def test_the_refusal_says_what_to_do(self):
        with pytest.raises(Arithmetic) as caught:
            run_output("print heapPush([5, 1], 3);")
        assert "heapify first" in str(caught.value)

    def test_popping_a_broken_heap_is_refused(self):
        with pytest.raises(Arithmetic):
            run_output("print heapPop([5, 1]);")

    def test_peeking_at_a_broken_heap_is_refused(self):
        with pytest.raises(Arithmetic):
            run_output("print heapPeek([5, 1]);")

    def test_merging_a_broken_heap_is_refused(self):
        with pytest.raises(Arithmetic):
            run_output("print heapMerge([5, 1], [2]);")

    def test_heapify_accepts_a_broken_heap_because_that_is_its_job(self):
        assert evaluate("isHeap(heapify([5, 1]))") == "true"

    def test_asking_whether_a_list_is_a_heap_is_never_refused(self):
        assert evaluate("isHeap([5, 1])") == "false"


class TestDrawingInOrder:
    def test_a_heap_empties_in_order(self):
        assert evaluate("heapSorted([5, 3, 8, 1, 9, 2])") == "[1, 2, 3, 5, 8, 9]"

    def test_an_already_ordered_list_stays_ordered(self):
        assert evaluate("heapSorted([1, 2, 3])") == "[1, 2, 3]"

    def test_a_reversed_list_comes_back_ordered(self):
        assert evaluate("heapSorted([3, 2, 1])") == "[1, 2, 3]"

    def test_nothing_sorts_to_nothing(self):
        assert evaluate("heapSorted([])") == "[]"

    def test_repeated_values_are_all_kept(self):
        assert evaluate("heapSorted([2, 1, 2])") == "[1, 2, 2]"

    def test_strings_come_back_ordered(self):
        assert evaluate('heapSorted(["c", "a", "b"])') == '["a", "b", "c"]'

    def test_the_result_matches_the_ordering_library(self):
        assert evaluate("heapSorted([5, 3, 8, 1])") == evaluate("ordered([5, 3, 8, 1])")


class TestExtremes:
    def test_the_smallest_few_come_back_in_order(self):
        assert evaluate("smallest([5, 3, 8, 1, 9], 2)") == "[1, 3]"

    def test_the_largest_few_come_back_largest_first(self):
        assert evaluate("largest([5, 3, 8, 1, 9], 2)") == "[9, 8]"

    def test_asking_for_none_gives_nothing(self):
        assert evaluate("smallest([1, 2], 0)") == "[]"

    def test_asking_for_more_than_there_is_gives_everything(self):
        assert evaluate("smallest([2, 1], 9)") == "[1, 2]"

    def test_the_largest_of_everything_is_the_reverse_order(self):
        assert evaluate("largest([1, 2, 3], 3)") == "[3, 2, 1]"

    def test_a_negative_count_is_refused(self):
        with pytest.raises(Arithmetic):
            run_output("print smallest([1], -1);")

    def test_a_count_that_is_not_whole_is_refused(self):
        with pytest.raises(TypeMismatch):
            run_output("print largest([1], 1.5);")


class TestMergingAndMeasuring:
    def test_merging_gives_a_heap(self):
        assert evaluate("isHeap(heapMerge(heapify([1, 4]), heapify([2, 3])))") == "true"

    def test_merging_keeps_every_value(self):
        merged = "heapSorted(heapMerge(heapify([1, 4]), heapify([2, 3])))"
        assert evaluate(merged) == "[1, 2, 3, 4]"

    def test_merging_with_nothing_gives_the_other(self):
        assert evaluate("heapSorted(heapMerge(heapify([1, 2]), []))") == "[1, 2]"

    def test_the_size_is_the_length(self):
        assert evaluate("heapSize([1, 2, 3])") == "3"

    def test_an_empty_heap_is_empty(self):
        assert evaluate("heapEmpty([])") == "true"

    def test_a_heap_with_a_value_is_not(self):
        assert evaluate("heapEmpty([1])") == "false"

    def test_the_depth_of_nothing_is_zero(self):
        assert evaluate("heapDepth([])") == "0"

    def test_one_value_is_one_level(self):
        assert evaluate("heapDepth([1])") == "1"

    def test_three_values_are_two_levels(self):
        assert evaluate("heapDepth([1, 2, 3])") == "2"

    def test_four_values_need_a_third_level(self):
        assert evaluate("heapDepth([1, 2, 3, 4])") == "3"

    def test_seven_values_still_fit_three_levels(self):
        assert evaluate("heapDepth([1, 2, 3, 4, 5, 6, 7])") == "3"


class TestOrderingByAKey:
    def test_a_pair_orders_by_its_first_element(self):
        # the documented way to order by something other than the natural order
        source = "print heapSorted([[3, " + chr(34) + "c" + chr(34) + "], [1, "
        source += chr(34) + "a" + chr(34) + "], [2, " + chr(34) + "b" + chr(34) + "]]);"
        assert run_output(source) == ['[[1, "a"], [2, "b"], [3, "c"]]']

    def test_the_smallest_pair_is_found_by_its_key(self):
        source = "print heapPeek(heapify([[3, " + chr(34) + "c" + chr(34) + "], [1, "
        source += chr(34) + "a" + chr(34) + "]]));"
        assert run_output(source) == ['[1, "a"]']


class TestBothBackendsAgree:
    @pytest.mark.parametrize(
        "expression",
        [
            "heapify([5, 3, 8, 1, 9, 2])",
            "heapPush(heapify([2, 4]), 1)",
            "heapPop(heapify([3, 1, 2]))",
            "heapPeek(heapify([5, 1]))",
            "heapReplace(heapify([1, 2, 3]), 9)",
            "isHeap([1, 2, 3])",
            "heapSorted([5, 3, 8, 1])",
            "smallest([5, 3, 8, 1, 9], 3)",
            "largest([5, 3, 8, 1, 9], 3)",
            "heapMerge(heapify([1, 4]), heapify([2, 3]))",
            "heapSize([1, 2])",
            "heapEmpty([])",
            "heapDepth([1, 2, 3, 4, 5])",
        ],
    )
    def test_the_two_backends_agree(self, expression):
        source = f"print {expression};"
        assert run_output(source) == run_treewalk_output(source)
