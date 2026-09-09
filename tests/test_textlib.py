from __future__ import annotations

import pytest

from ember.errors import Arithmetic, TypeMismatch
from ember.interpreter import run_output, run_treewalk_output
from ember.textlib import text_names


def evaluate(expression: str) -> str:
    return run_output(f"print {expression};")[0]


class TestRegistration:
    def test_every_function_is_named(self):
        assert "padLeft" in text_names()
        assert "wrap" in text_names()

    def test_the_names_are_sorted(self):
        assert text_names() == sorted(text_names())

    def test_there_are_twenty_of_them(self):
        assert len(text_names()) == 20

    def test_a_chosen_filler_is_its_own_function(self):
        # a native takes a fixed count of arguments, so there is no optional third
        assert "padLeftWith" in text_names()
        assert "padRightWith" in text_names()


class TestPadding:
    def test_padding_left_adds_spaces_in_front(self):
        assert evaluate('padLeft("7", 3)') == "  7"

    def test_padding_right_adds_spaces_behind(self):
        assert evaluate('padRight("7", 3)') == "7  "

    def test_a_chosen_filler_is_used(self):
        assert evaluate('padLeftWith("7", 3, "0")') == "007"

    def test_padding_right_with_a_chosen_filler(self):
        assert evaluate('padRightWith("7", 3, ".")') == "7.."

    def test_a_string_already_wide_enough_is_unchanged(self):
        # losing text silently is worse than a misaligned column
        assert evaluate('padLeft("hello", 3)') == "hello"

    def test_padding_to_its_own_width_changes_nothing(self):
        assert evaluate('padLeft("abc", 3)') == "abc"

    def test_a_filler_of_two_characters_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output('print padLeftWith("7", 3, "ab");')
        assert "single character" in str(caught.value)

    def test_an_empty_filler_is_refused(self):
        with pytest.raises(Arithmetic):
            run_output('print padLeftWith("7", 3, "");')

    def test_a_negative_width_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output('print padLeft("7", -1);')
        assert "zero or more" in str(caught.value)

    def test_a_width_that_is_not_whole_is_refused(self):
        with pytest.raises(TypeMismatch):
            run_output('print padLeft("7", 1.5);')

    def test_padding_something_that_is_not_a_string_is_refused(self):
        with pytest.raises(TypeMismatch):
            run_output("print padLeft(7, 3);")


class TestCentring:
    def test_an_even_gap_splits_evenly(self):
        assert evaluate('centre("ab", 6)') == "  ab  "

    def test_an_odd_gap_puts_the_extra_on_the_right(self):
        assert evaluate('centre("ab", 5)') == " ab  "

    def test_a_string_already_wide_enough_is_unchanged(self):
        assert evaluate('centre("hello", 2)') == "hello"


class TestRepeatingAndReversing:
    def test_repeating_joins_copies(self):
        assert evaluate('repeat("ab", 3)') == "ababab"

    def test_repeating_zero_times_gives_nothing(self):
        assert evaluate('repeat("ab", 0)') == ""

    def test_reversing_turns_it_around(self):
        assert evaluate('reversedText("abc")') == "cba"

    def test_reversing_twice_returns_the_original(self):
        assert evaluate('reversedText(reversedText("hello"))') == "hello"

    def test_reversing_nothing_gives_nothing(self):
        assert evaluate('reversedText("")') == ""


class TestCasing:
    def test_a_title_lifts_every_word(self):
        assert evaluate('title("ada lovelace")') == "Ada Lovelace"

    def test_a_title_lowers_the_rest_of_each_word(self):
        # the mechanical rule, deliberately not the typographic one
        assert evaluate('title("aDA lOVELACE")') == "Ada Lovelace"

    def test_capitalising_touches_only_the_first_letter(self):
        assert evaluate('capitalise("ada lovelace")') == "Ada lovelace"

    def test_capitalising_nothing_gives_nothing(self):
        assert evaluate('capitalise("")') == ""

    def test_swapping_case_flips_each_letter(self):
        assert evaluate('swapCase("AbC")') == "aBc"

    def test_swapping_twice_returns_the_original(self):
        assert evaluate('swapCase(swapCase("HeLLo"))') == "HeLLo"


class TestWrapping:
    def test_words_are_gathered_up_to_the_width(self):
        assert evaluate('wrap("a bb ccc dddd", 5)') == '["a bb", "ccc", "dddd"]'

    def test_a_word_longer_than_the_width_overflows(self):
        # breaking mid-word reads worse than a long line
        assert evaluate('wrap("elephant", 3)') == '["elephant"]'

    def test_a_short_text_stays_on_one_line(self):
        assert evaluate('wrap("a b", 10)') == '["a b"]'

    def test_wrapping_nothing_gives_no_lines(self):
        assert evaluate('wrap("", 5)') == "[]"

    def test_a_width_of_zero_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output('print wrap("a", 0);')
        assert "at least one character" in str(caught.value)

    def test_extra_spaces_are_collapsed(self):
        assert evaluate('wrap("a    b", 10)') == '["a b"]'


class TestIndenting:
    def test_indenting_adds_a_prefix(self):
        assert evaluate('indent("a", 2)') == "  a"

    def test_indenting_by_zero_changes_nothing(self):
        assert evaluate('indent("a", 0)') == "a"

    def test_dedenting_removes_the_common_prefix(self):
        assert evaluate('dedent(indent("ab", 4))') == "ab"

    def test_dedenting_keeps_relative_indentation(self):
        assert evaluate('dedent("  a")') == "a"

    def test_dedenting_blank_text_leaves_it_alone(self):
        assert evaluate('dedent("")') == ""


class TestTruncating:
    def test_a_long_string_gets_an_ellipsis(self):
        assert evaluate('truncate("abcdefgh", 5)') == "ab..."

    def test_a_short_string_is_unchanged(self):
        assert evaluate('truncate("abc", 5)') == "abc"

    def test_a_string_at_the_width_is_unchanged(self):
        assert evaluate('truncate("abcde", 5)') == "abcde"

    def test_too_narrow_for_an_ellipsis_just_cuts(self):
        # the width wins over the marker
        assert evaluate('truncate("abcdef", 2)') == "ab"

    def test_a_width_of_zero_gives_nothing(self):
        assert evaluate('truncate("abc", 0)') == ""


class TestCountingAndLines:
    def test_counting_finds_every_occurrence(self):
        assert evaluate('countOf("banana", "na")') == "2"

    def test_counting_something_absent_gives_zero(self):
        assert evaluate('countOf("banana", "z")') == "0"

    def test_an_empty_needle_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output('print countOf("banana", "");')
        assert "needle is empty" in str(caught.value)

    def test_splitting_into_lines(self):
        assert evaluate('lines("a")') == '["a"]'

    def test_joining_lines_back(self):
        assert evaluate('unlines(["a", "b"])') == "a" + chr(10) + "b"

    def test_lines_and_unlines_are_inverses(self):
        assert evaluate('lines(unlines(["a", "b"]))') == '["a", "b"]'

    def test_joining_something_that_is_not_a_list_is_refused(self):
        with pytest.raises(TypeMismatch):
            run_output('print unlines("a");')

    def test_joining_a_list_of_numbers_is_refused(self):
        with pytest.raises(TypeMismatch):
            run_output("print unlines([1]);")


class TestInspecting:
    def test_whitespace_is_blank(self):
        assert evaluate('isBlank("  ")') == "true"

    def test_nothing_is_blank(self):
        assert evaluate('isBlank("")') == "true"

    def test_a_letter_is_not_blank(self):
        assert evaluate('isBlank(" a ")') == "false"

    def test_squeezing_collapses_runs_of_spaces(self):
        assert evaluate('squeeze(" a   b ")') == "a b"

    def test_squeezing_something_already_tidy_changes_nothing(self):
        assert evaluate('squeeze("a b")') == "a b"

    def test_a_shared_prefix_is_found(self):
        assert evaluate('commonPrefix("format", "forgot")') == "for"

    def test_no_shared_prefix_gives_nothing(self):
        assert evaluate('commonPrefix("abc", "xyz")') == ""

    def test_an_identical_pair_shares_everything(self):
        assert evaluate('commonPrefix("same", "same")') == "same"

    def test_a_prefix_of_the_other_is_the_whole_shorter_one(self):
        assert evaluate('commonPrefix("for", "format")') == "for"


class TestBothBackendsAgree:
    @pytest.mark.parametrize(
        "expression",
        [
            'padLeft("7", 4)',
            'padRightWith("7", 4, "0")',
            'centre("ab", 7)',
            'repeat("xy", 3)',
            'title("grace hopper")',
            'swapCase("AbC")',
            'wrap("one two three four", 9)',
            'truncate("abcdefgh", 6)',
            'countOf("mississippi", "ss")',
            'squeeze("  a  b  ")',
            'commonPrefix("prefix", "prefer")',
        ],
    )
    def test_the_two_backends_agree(self, expression):
        source = f"print {expression};"
        assert run_output(source) == run_treewalk_output(source)
