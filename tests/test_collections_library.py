from __future__ import annotations

import pytest

from ember.errors import IndexRange, TypeMismatch
from ember.interpreter import run, run_output, run_treewalk_output
from ember.maplib import map_names
from ember.setlib import set_names

SHARED = [
    'let m = {"a": 1, "b": 2}; print has(m, "a"); print has(m, "z"); print get(m, "z", 0);',
    'let m = {"a": 1}; print remove(m, "a"); print m;',
    'print merge({"a": 1, "b": 2}, {"b": 9, "c": 3});',
    'print entries({"a": 1, "b": 2}); print from_entries([["a", 1], ["b", 2]]);',
    'print invert({"a": 1, "b": 2}); print is_empty({}); print is_empty({"a": 1});',
    "print union([1, 2], [2, 3]); print intersect([1, 2, 3], [2, 3, 4]);",
    "print difference([1, 2, 3], [2]); print symmetric_difference([1, 2], [2, 3]);",
    "print as_set([1, 1, 2, 2, 3]); print is_subset([1, 2], [1, 2, 3]);",
    'print pad_left("7", 3, "0"); print pad_right("ab", 4, ".");',
    'print words("  a b   c "); print reverse_text("abc"); print is_blank("   ");',
    "print take([1, 2, 3, 4], 2); print drop([1, 2, 3, 4], 2); print take([1], 9);",
    "print flatten([[1, 2], [3], 4]); print chunk([1, 2, 3, 4, 5], 2);",
    'print zip([1, 2, 3], ["a", "b"]); print repeat_list([1, 2], 3);',
    "let a = [1, 2, 3]; print insert(a, 1, 9); print remove_at(a, 0); print a;",
]


class TestMapLibrary:
    def test_has_asks_without_fetching(self):
        source = 'let m = {"a": 1}; print has(m, "a"); print has(m, "z");'
        assert run_output(source) == ["true", "false"]

    def test_get_turns_a_missing_key_into_an_answer(self):
        # indexing raises for an absent key; get is the version that does not
        source = 'let m = {"a": 1}; print get(m, "z", 0); print get(m, "a", 0);'
        assert run_output(source) == ["0", "1"]

    def test_remove_returns_the_value_and_takes_it_out(self):
        assert run_output('let m = {"a": 1}; print remove(m, "a"); print m;') == ["1", "{}"]

    def test_removing_an_absent_key_is_refused(self):
        with pytest.raises(IndexRange):
            run('let m = {}; remove(m, "a");')

    def test_merge_lets_the_second_win_a_collision(self):
        source = 'print merge({"a": 1, "b": 2}, {"b": 9});'
        assert run_output(source) == ['{"a": 1, "b": 9}']

    def test_merge_leaves_both_inputs_alone(self):
        source = 'let a = {"x": 1}; let b = {"y": 2}; merge(a, b); print a; print b;'
        assert run_output(source) == ['{"x": 1}', '{"y": 2}']

    def test_entries_and_from_entries_round_trip(self):
        source = 'let m = {"a": 1, "b": 2}; print from_entries(entries(m));'
        assert run_output(source) == ['{"a": 1, "b": 2}']

    def test_invert_swaps_keys_and_values(self):
        assert run_output('print invert({"a": 1});') == ['{1: "a"}']

    def test_a_malformed_entry_is_refused(self):
        with pytest.raises(TypeMismatch):
            run("from_entries([[1]]);")

    def test_a_list_cannot_be_a_key(self):
        with pytest.raises(TypeMismatch):
            run('has({"a": 1}, [1]);')

    def test_every_name_is_installed(self):
        machine = run("print 1;")
        for name in map_names():
            assert name in machine.globals, name


class TestSetLibrary:
    def test_union_keeps_each_element_once(self):
        assert run_output("print union([1, 2], [2, 3]);") == ["[1, 2, 3]"]

    def test_intersection_keeps_what_both_have(self):
        assert run_output("print intersect([1, 2, 3], [2, 3, 4]);") == ["[2, 3]"]

    def test_difference_keeps_what_only_the_first_has(self):
        assert run_output("print difference([1, 2, 3], [2]);") == ["[1, 3]"]

    def test_symmetric_difference_keeps_what_exactly_one_has(self):
        assert run_output("print symmetric_difference([1, 2], [2, 3]);") == ["[1, 3]"]

    def test_as_set_drops_duplicates_keeping_order(self):
        assert run_output("print as_set([3, 1, 3, 2, 1]);") == ["[3, 1, 2]"]

    def test_containment_questions(self):
        source = (
            "print is_subset([1, 2], [1, 2, 3]); print is_subset([1, 4], [1, 2]);"
            " print is_superset([1, 2, 3], [1]); print is_disjoint([1], [2]);"
        )
        assert run_output(source) == ["true", "false", "true", "true"]

    def test_the_empty_set_is_a_subset_of_anything(self):
        assert run_output("print is_subset([], [1, 2]);") == ["true"]

    def test_the_operations_leave_their_inputs_alone(self):
        source = "let a = [1, 2]; let b = [2, 3]; union(a, b); print a; print b;"
        assert run_output(source) == ["[1, 2]", "[2, 3]"]

    def test_equality_compares_order_too(self):
        # these are lists, not unordered collections, which is the honest caveat
        source = "print [1, 2] == [2, 1]; print is_subset([1, 2], [2, 1]);"
        assert run_output(source) == ["false", "true"]

    def test_every_name_is_installed(self):
        machine = run("print 1;")
        for name in set_names():
            assert name in machine.globals, name


class TestStringAdditions:
    def test_padding_widens_to_the_requested_width(self):
        assert run_output('print pad_left("7", 3, "0");') == ["007"]
        assert run_output('print pad_right("ab", 4, ".");') == ["ab.."]

    def test_padding_never_cuts_a_longer_string(self):
        assert run_output('print pad_left("toolong", 2, "0");') == ["toolong"]

    def test_padding_needs_a_single_character(self):
        with pytest.raises(IndexRange):
            run('pad_left("a", 5, "xy");')

    def test_words_collapses_runs_of_space(self):
        assert run_output('print words("  a b   c ");') == ['["a", "b", "c"]']

    def test_lines_splits_on_newlines(self):
        assert run_output('print len(lines("a' + chr(92) + 'nb"));') == ["2"]

    def test_reverse_and_blank_and_counting(self):
        source = (
            'print reverse_text("abc"); print is_blank("   "); print is_blank("x");'
            ' print count_of("banana", "a"); print last_index_of("abcabc", "b");'
        )
        assert run_output(source) == ["cba", "true", "false", "3", "4"]

    def test_counting_an_empty_needle_is_refused(self):
        with pytest.raises(IndexRange):
            run('count_of("abc", "");')


class TestListAdditions:
    def test_take_and_drop(self):
        assert run_output("print take([1, 2, 3, 4], 2); print drop([1, 2, 3, 4], 2);") == [
            "[1, 2]",
            "[3, 4]",
        ]

    def test_taking_more_than_there_is_yields_everything(self):
        assert run_output("print take([1], 9); print drop([1], 9);") == ["[1]", "[]"]

    def test_flatten_removes_one_level_only(self):
        assert run_output("print flatten([[1, 2], [3], 4]);") == ["[1, 2, 3, 4]"]
        assert run_output("print flatten([[[1]]]);") == ["[[1]]"]

    def test_chunk_splits_into_runs_with_a_short_last_one(self):
        assert run_output("print chunk([1, 2, 3, 4, 5], 2);") == ["[[1, 2], [3, 4], [5]]"]

    def test_a_zero_chunk_size_is_refused(self):
        with pytest.raises(IndexRange):
            run("chunk([1], 0);")

    def test_zip_stops_at_the_shorter(self):
        assert run_output('print zip([1, 2, 3], ["a", "b"]);') == ['[[1, "a"], [2, "b"]]']

    def test_repeat_list(self):
        assert run_output("print repeat_list([1, 2], 3);") == ["[1, 2, 1, 2, 1, 2]"]
        assert run_output("print repeat_list([1], 0);") == ["[]"]

    def test_insert_and_remove_at_change_the_list(self):
        source = "let a = [1, 2, 3]; insert(a, 1, 9); print a; print remove_at(a, 0); print a;"
        assert run_output(source) == ["[1, 9, 2, 3]", "1", "[9, 2, 3]"]

    def test_inserting_at_the_length_appends(self):
        assert run_output("let a = [1]; insert(a, 1, 2); print a;") == ["[1, 2]"]

    def test_inserting_past_the_end_is_refused(self):
        with pytest.raises(IndexRange):
            run("insert([1], 5, 2);")

    def test_the_original_count_still_counts_occurrences(self):
        # a helper added here once shadowed this native, which the test now pins
        assert run_output("print count([1, 1, 2], 1);") == ["2"]

    def test_copy_and_emptiness(self):
        source = "let a = [1]; let b = copy_list(a); push(b, 2); print a; print b;"
        assert run_output(source) == ["[1]", "[1, 2]"]
        assert run_output("print is_empty_list([]);") == ["true"]


class TestBothBackendsAgree:
    @pytest.mark.parametrize("source", SHARED)
    def test_agreement(self, source: str):
        assert run_output(source) == run_treewalk_output(source)
