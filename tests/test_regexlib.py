from __future__ import annotations

import pytest

from ember.errors import Arithmetic, TypeMismatch
from ember.interpreter import run_output, run_treewalk_output
from ember.regexlib import regex_names

BACKSLASH = chr(92)
QUOTE = chr(34)
# a pattern written inside an Ember string needs its backslash doubled
DIGIT = BACKSLASH + BACKSLASH + "d"
WORD = BACKSLASH + BACKSLASH + "w"


def quoted(text: str) -> str:
    return QUOTE + text + QUOTE


def evaluate(expression: str) -> str:
    return run_output(f"print {expression};")[0]


class TestRegistration:
    def test_the_functions_are_named(self):
        assert "matches" in regex_names()
        assert "replaced" in regex_names()

    def test_the_names_are_sorted(self):
        assert regex_names() == sorted(regex_names())

    def test_there_are_eleven_of_them(self):
        assert len(regex_names()) == 11

    def test_every_function_takes_the_pattern_first(self):
        # consistency so a call never has to be looked up
        assert evaluate(f"matches({quoted('[a-z]+')}, {quoted('abc')})") == "true"


class TestWholeAndPartial:
    def test_a_pattern_covering_everything_matches(self):
        assert evaluate(f"matches({quoted('[a-z]+')}, {quoted('abc')})") == "true"

    def test_a_pattern_covering_part_does_not_match_whole(self):
        assert evaluate(f"matches({quoted('[a-z]+')}, {quoted('ab1')})") == "false"

    def test_a_pattern_found_inside_is_reported(self):
        assert evaluate(f"foundIn({quoted(DIGIT + '+')}, {quoted('abc123')})") == "true"

    def test_a_pattern_absent_is_reported(self):
        assert evaluate(f"foundIn({quoted(DIGIT)}, {quoted('abc')})") == "false"


class TestMatchShape:
    def test_a_match_comes_back_as_a_list(self):
        found = evaluate(f"firstMatch({quoted(DIGIT + '+')}, {quoted('ab123c')})")
        assert found == '["123", 2, 5, []]'

    def test_the_shape_holds_text_start_end_and_groups(self):
        source = f"let m = firstMatch({quoted(DIGIT + '+')}, {quoted('ab123c')});"
        source += " print m[0]; print m[1]; print m[2]; print m[3];"
        assert run_output(source) == ["123", "2", "5", "[]"]

    def test_no_match_comes_back_as_nil(self):
        assert evaluate(f"firstMatch({quoted(DIGIT)}, {quoted('abc')})") == "nil"

    def test_groups_appear_in_the_fourth_place(self):
        pattern = quoted("(" + DIGIT + "+)-(" + DIGIT + "+)")
        found = evaluate(f"firstMatch({pattern}, {quoted('call 555-1234')})")
        assert found == '["555-1234", 5, 13, ["555", "1234"]]'

    def test_every_match_can_be_asked_for(self):
        found = evaluate(f"allMatches({quoted(WORD + '+')}, {quoted('ab cd')})")
        assert found == '[["ab", 0, 2, []], ["cd", 3, 5, []]]'

    def test_the_matched_text_alone_can_be_asked_for(self):
        found = evaluate(f"matchedText({quoted(DIGIT + '+')}, {quoted('a1b22c333')})")
        assert found == '["1", "22", "333"]'

    def test_the_count_can_be_asked_for(self):
        assert evaluate(f"countMatches({quoted(DIGIT + '+')}, {quoted('a1b22c333')})") == "3"

    def test_nothing_found_counts_zero(self):
        assert evaluate(f"countMatches({quoted(DIGIT)}, {quoted('abc')})") == "0"


class TestGroups:
    def test_the_captures_of_the_first_match_can_be_asked_for(self):
        pattern = quoted("(a+)(b+)")
        assert evaluate(f"groupsOf({pattern}, {quoted('xaabbby')})") == '["aa", "bbb"]'

    def test_a_group_that_matched_nothing_is_nil(self):
        # different from matching an empty string, which a program needs to tell apart
        assert evaluate(f"groupsOf({quoted('(a)(b)?')}, {quoted('a')})") == '["a", nil]'

    def test_a_group_that_matched_an_empty_string_is_that_string(self):
        assert evaluate(f"groupsOf({quoted('(a*)b')}, {quoted('b')})") == '[""]'

    def test_no_match_gives_nil_rather_than_an_empty_list(self):
        assert evaluate(f"groupsOf({quoted('(a)')}, {quoted('z')})") == "nil"

    def test_the_group_count_is_reported(self):
        assert evaluate(f"groupCount({quoted('(a)(b)(c)')})") == "3"

    def test_a_pattern_with_no_groups_counts_none(self):
        assert evaluate(f"groupCount({quoted('abc')})") == "0"


class TestReplacingAndSplitting:
    def test_every_match_is_replaced(self):
        source = f"replaced({quoted(DIGIT + '+')}, {quoted('a1b22c')}, {quoted('#')})"
        assert evaluate(source) == "a#b#c"

    def test_nothing_to_replace_leaves_the_subject_alone(self):
        source = f"replaced({quoted('z')}, {quoted('abc')}, {quoted('#')})"
        assert evaluate(source) == "abc"

    def test_a_replacement_can_be_empty(self):
        source = f"replaced({quoted(DIGIT)}, {quoted('a1b2')}, {quoted('')})"
        assert evaluate(source) == "ab"

    def test_splitting_divides_on_every_match(self):
        assert evaluate(f"splitBy({quoted(',')}, {quoted('a,b,c')})") == '["a", "b", "c"]'

    def test_splitting_on_a_pattern_works(self):
        pattern = quoted(BACKSLASH + BACKSLASH + "s+")
        assert evaluate(f"splitBy({pattern}, {quoted('a  b c')})") == '["a", "b", "c"]'

    def test_splitting_on_something_absent_gives_one_piece(self):
        assert evaluate(f"splitBy({quoted(';')}, {quoted('a,b')})") == '["a,b"]'


class TestValidity:
    def test_a_good_pattern_is_valid(self):
        assert evaluate(f"isValidPattern({quoted('[a-z]+')})") == "true"

    def test_an_unclosed_class_is_not(self):
        assert evaluate(f"isValidPattern({quoted('[a-z')})") == "false"

    def test_an_unclosed_group_is_not(self):
        assert evaluate(f"isValidPattern({quoted('(abc')})") == "false"

    def test_a_backwards_range_is_not(self):
        assert evaluate(f"isValidPattern({quoted('[z-a]')})") == "false"

    def test_a_lookahead_is_not_valid_here(self):
        assert evaluate(f"isValidPattern({quoted('(?=a)')})") == "false"

    def test_a_backreference_is_not_valid_here(self):
        pattern = quoted("(a)" + BACKSLASH + BACKSLASH + "1")
        assert evaluate(f"isValidPattern({pattern})") == "false"


class TestRefusals:
    def test_a_bad_pattern_refuses_when_matching(self):
        with pytest.raises(Arithmetic) as caught:
            run_output(f"print matches({quoted('[a-z')}, {quoted('abc')});")
        assert "never closed" in str(caught.value)

    def test_a_pattern_that_is_not_a_string_is_refused(self):
        with pytest.raises(TypeMismatch) as caught:
            run_output(f"print matches(5, {quoted('abc')});")
        assert "for the pattern" in str(caught.value)

    def test_a_subject_that_is_not_a_string_is_refused(self):
        with pytest.raises(TypeMismatch) as caught:
            run_output(f"print matches({quoted('a')}, 5);")
        assert "for the subject" in str(caught.value)

    def test_a_replacement_that_is_not_a_string_is_refused(self):
        with pytest.raises(TypeMismatch) as caught:
            run_output(f"print replaced({quoted('a')}, {quoted('a')}, 5);")
        assert "for the replacement" in str(caught.value)

    def test_a_catastrophic_pattern_refuses_rather_than_hanging(self):
        long_subject = "a" * 24 + "!"
        with pytest.raises(Arithmetic) as caught:
            run_output(f"print foundIn({quoted('(a+)+b')}, {quoted(long_subject)});")
        assert "backtracks too much" in str(caught.value)

    def test_a_program_can_catch_that_refusal(self):
        long_subject = "a" * 24 + "!"
        source = "try { print foundIn(" + quoted("(a+)+b") + ", " + quoted(long_subject)
        source += "); } catch (e) { print " + quoted("refused") + "; }"
        assert run_output(source) == ["refused"]


class TestRealisticPatterns:
    def test_a_telephone_number_is_matched(self):
        pattern = quoted("^" + DIGIT + "{3}-" + DIGIT + "{4}$")
        assert evaluate(f"matches({pattern}, {quoted('555-1234')})") == "true"

    def test_a_malformed_telephone_number_is_not(self):
        pattern = quoted("^" + DIGIT + "{3}-" + DIGIT + "{4}$")
        assert evaluate(f"matches({pattern}, {quoted('55-1234')})") == "false"

    def test_an_identifier_is_matched(self):
        pattern = quoted("^[a-zA-Z_][a-zA-Z0-9_]*$")
        assert evaluate(f"matches({pattern}, {quoted('some_name1')})") == "true"

    def test_a_leading_digit_is_not_an_identifier(self):
        pattern = quoted("^[a-zA-Z_][a-zA-Z0-9_]*$")
        assert evaluate(f"matches({pattern}, {quoted('1name')})") == "false"

    def test_words_can_be_counted(self):
        pattern = quoted(WORD + "+")
        assert evaluate(f"countMatches({pattern}, {quoted('one two three')})") == "3"

    def test_a_decimal_number_is_matched(self):
        pattern = quoted("^" + DIGIT + "+[.]" + DIGIT + "+$")
        assert evaluate(f"matches({pattern}, {quoted('3.14')})") == "true"


class TestBothBackendsAgree:
    @pytest.mark.parametrize(
        "expression",
        [
            f"matches({quoted('[a-z]+')}, {quoted('abc')})",
            f"foundIn({quoted(DIGIT + '+')}, {quoted('ab12')})",
            f"firstMatch({quoted('(a+)(b+)')}, {quoted('xaabb')})",
            f"allMatches({quoted(WORD + '+')}, {quoted('ab cd')})",
            f"matchedText({quoted(DIGIT + '+')}, {quoted('a1b22')})",
            f"countMatches({quoted(DIGIT)}, {quoted('a1b2')})",
            f"replaced({quoted(DIGIT)}, {quoted('a1b2')}, {quoted('#')})",
            f"splitBy({quoted(',')}, {quoted('a,b,c')})",
            f"groupsOf({quoted('(a)(b)?')}, {quoted('a')})",
            f"groupCount({quoted('(a)(b)')})",
            f"isValidPattern({quoted('[a-z')})",
        ],
    )
    def test_the_two_backends_agree(self, expression):
        source = f"print {expression};"
        assert run_output(source) == run_treewalk_output(source)
