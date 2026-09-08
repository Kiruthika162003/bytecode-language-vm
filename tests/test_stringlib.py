from __future__ import annotations

import pytest

from ember.errors import IndexRange, TypeMismatch
from ember.interpreter import run, run_output


class TestCaseAndTrim:
    def test_upper_lower_trim(self):
        assert run_output('print upper("abc");') == ["ABC"]
        assert run_output('print lower("ABC");') == ["abc"]
        assert run_output('print trim("  hi  ");') == ["hi"]


class TestSplitJoin:
    def test_split_on_a_separator(self):
        assert run_output('print split("a,b,c", ",");') == ['["a", "b", "c"]']

    def test_split_on_empty_gives_characters(self):
        assert run_output('print split("abc", "");') == ['["a", "b", "c"]']

    def test_join_with_a_separator(self):
        assert run_output('print join(["a", "b", "c"], "-");') == ["a-b-c"]

    def test_join_rejects_non_strings(self):
        with pytest.raises(TypeMismatch):
            run('print join([1, 2], ",");')


class TestSearchAndSlice:
    def test_replace(self):
        assert run_output('print replace("banana", "a", "o");') == ["bonono"]

    def test_starts_and_ends_with(self):
        assert run_output('print starts_with("hello", "he");') == ["true"]
        assert run_output('print ends_with("hello", "lo");') == ["true"]

    def test_index_of_reports_minus_one_when_absent(self):
        assert run_output('print index_of("hello", "z");') == ["-1"]

    def test_substring(self):
        assert run_output('print substring("hello", 1, 4);') == ["ell"]

    def test_substring_out_of_range_is_refused(self):
        with pytest.raises(IndexRange):
            run('print substring("hi", 0, 9);')


class TestCharsAndCodes:
    def test_chars_and_code_round_trip(self):
        assert run_output('print code_at("A", 0);') == ["65"]
        assert run_output("print from_code(66);") == ["B"]

    def test_repeat(self):
        assert run_output('print repeat("ab", 3);') == ["ababab"]


class TestTypeErrors:
    def test_upper_of_a_number_is_refused(self):
        with pytest.raises(TypeMismatch):
            run("print upper(5);")
