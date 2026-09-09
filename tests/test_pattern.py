from __future__ import annotations

import re

import pytest

from ember.errors import Arithmetic
from ember.pattern import (
    Match,
    compile_pattern,
    find_all,
    matches_whole,
    replace_all,
    search,
    split_on,
)

BACKSLASH = chr(92)
DIGIT = BACKSLASH + "d"
WORD = BACKSLASH + "w"
SPACE = BACKSLASH + "s"


def span_of(pattern: str, subject: str) -> tuple[int, int] | None:
    found = search(compile_pattern(pattern), subject)
    return (found.start, found.end) if found else None


AGREEMENT = [
    ("abc", "xabcy"),
    ("abc", "xyz"),
    ("a.c", "abc"),
    ("a.c", "ac"),
    ("a*", "aaa"),
    ("a*", "bbb"),
    ("a+", "aaa"),
    ("a+", "bbb"),
    ("ab?c", "ac"),
    ("ab?c", "abc"),
    ("[abc]+", "xbcay"),
    ("[a-z]+", "AbcD"),
    ("[^a-z]+", "abcDEF"),
    ("[a-zA-Z]+", "1aB2"),
    ("^abc$", "abc"),
    ("^abc$", "xabc"),
    ("^a", "ba"),
    ("a$", "ab"),
    ("a|b", "b"),
    ("cat|dog", "hotdog"),
    ("(ab)+", "abab"),
    ("(a|b)+", "abba"),
    ("a{2}", "aaa"),
    ("a{2,}", "aaaa"),
    ("a{2,3}", "aaaa"),
    ("a{0,1}", "b"),
    (DIGIT + "+", "abc123"),
    (WORD + "+", " ab_1 "),
    (SPACE + "+", "a  b"),
    ("a*?b", "aaab"),
    ("a+?", "aaa"),
    ("(a)(b)", "ab"),
    (DIGIT + "{3}-" + DIGIT + "{4}", "call 555-1234 now"),
    ("colou?r", "color"),
    ("colou?r", "colour"),
    ("[0-9]+[.][0-9]+", "pi is 3.14"),
    (".*", "anything"),
    ("x*y", "y"),
]


class TestAgreementWithTheHost:
    @pytest.mark.parametrize("pattern,subject", AGREEMENT)
    def test_the_match_lands_where_the_host_says(self, pattern, subject):
        # the host engine is an independent implementation of the same syntax
        theirs = re.search(pattern, subject)
        assert span_of(pattern, subject) == (theirs.span() if theirs else None)

    @pytest.mark.parametrize("pattern,subject", AGREEMENT)
    def test_the_matched_text_agrees(self, pattern, subject):
        theirs = re.search(pattern, subject)
        mine = search(compile_pattern(pattern), subject)
        assert (mine.text if mine else None) == (theirs.group(0) if theirs else None)

    @pytest.mark.parametrize(
        "pattern,subject",
        [("(a+)(b+)", "xaabbby"), ("(a)(b)?", "a"), ("(x)|(y)", "y")],
    )
    def test_the_captures_agree(self, pattern, subject):
        theirs = re.search(pattern, subject)
        mine = search(compile_pattern(pattern), subject)
        assert mine is not None
        assert mine.groups == theirs.groups()


class TestLiteralsAndAny:
    def test_a_literal_matches_itself(self):
        assert span_of("abc", "abc") == (0, 3)

    def test_a_literal_is_found_inside(self):
        assert span_of("bc", "abcd") == (1, 3)

    def test_a_literal_that_is_absent_finds_nothing(self):
        assert span_of("z", "abc") is None

    def test_a_dot_matches_any_character(self):
        assert span_of("a.c", "a!c") == (0, 3)

    def test_a_dot_needs_a_character(self):
        assert span_of("a.c", "ac") is None

    def test_an_empty_pattern_matches_at_the_start(self):
        assert span_of("", "abc") == (0, 0)


class TestQuantifiers:
    def test_none_or_more_can_match_nothing(self):
        assert span_of("a*", "bbb") == (0, 0)

    def test_none_or_more_is_greedy(self):
        assert span_of("a*", "aaab") == (0, 3)

    def test_one_or_more_needs_one(self):
        assert span_of("a+", "bbb") is None

    def test_optional_can_be_absent(self):
        assert span_of("ab?c", "ac") == (0, 2)

    def test_a_bounded_count_takes_exactly_that_many(self):
        assert span_of("a{2}", "aaa") == (0, 2)

    def test_an_open_upper_bound_takes_everything(self):
        assert span_of("a{2,}", "aaaa") == (0, 4)

    def test_a_closed_upper_bound_stops_there(self):
        assert span_of("a{2,3}", "aaaa") == (0, 3)

    def test_a_lower_bound_that_is_not_met_finds_nothing(self):
        assert span_of("a{3}", "aa") is None

    def test_a_lazy_quantifier_takes_as_little_as_it_can(self):
        found = search(compile_pattern("a+?"), "aaa")
        assert found is not None
        assert found.text == "a"

    def test_a_greedy_quantifier_takes_as_much_as_it_can(self):
        found = search(compile_pattern("a+"), "aaa")
        assert found is not None
        assert found.text == "aaa"

    def test_a_quantifier_on_a_group_repeats_the_group(self):
        assert span_of("(ab)+", "ababab") == (0, 6)

    def test_a_repeated_empty_match_does_not_loop_forever(self):
        # a term matching nothing would repeat for ever without the guard
        assert span_of("(a*)*b", "b") == (0, 1)


class TestClasses:
    def test_a_class_matches_any_member(self):
        assert span_of("[xyz]", "aya") == (1, 2)

    def test_a_range_matches_between_its_ends(self):
        assert span_of("[a-c]+", "xabcz") == (1, 4)

    def test_a_negated_class_matches_anything_else(self):
        assert span_of("[^a-z]+", "abcDEF") == (3, 6)

    def test_a_dash_at_the_end_is_a_literal(self):
        found = search(compile_pattern("[a-]+"), "xa-y")
        assert found is not None
        assert found.text == "a-"

    def test_a_closing_bracket_first_is_a_literal(self):
        assert span_of("[]]", "a]b") == (1, 2)

    def test_an_escape_inside_a_class_works(self):
        assert span_of("[" + DIGIT + "]+", "ab12") == (2, 4)

    def test_a_backwards_range_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            compile_pattern("[z-a]")
        assert "counts up" in str(caught.value)

    def test_a_class_that_never_closes_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            compile_pattern("[abc")
        assert "never closed" in str(caught.value)

    def test_a_negated_escape_inside_a_class_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            compile_pattern("[" + BACKSLASH + "D]")
        assert "two things at once" in str(caught.value)


class TestAnchors:
    def test_a_start_anchor_holds_only_at_the_start(self):
        assert span_of("^a", "ba") is None

    def test_a_start_anchor_matches_at_the_start(self):
        assert span_of("^a", "ab") == (0, 1)

    def test_an_end_anchor_holds_only_at_the_end(self):
        assert span_of("a$", "ab") is None

    def test_an_end_anchor_matches_at_the_end(self):
        assert span_of("a$", "ba") == (1, 2)

    def test_both_anchors_demand_the_whole_subject(self):
        assert span_of("^abc$", "abcd") is None


class TestEscapes:
    def test_a_digit_escape_matches_digits(self):
        assert span_of(DIGIT + "+", "ab123") == (2, 5)

    def test_a_negated_digit_escape_matches_anything_else(self):
        assert span_of(BACKSLASH + "D+", "12ab") == (2, 4)

    def test_a_word_escape_matches_word_characters(self):
        assert span_of(WORD + "+", " ab_1 ") == (1, 5)

    def test_a_negated_word_escape_matches_anything_else(self):
        assert span_of(BACKSLASH + "W+", "ab!! cd") == (2, 5)

    def test_a_space_escape_matches_whitespace(self):
        assert span_of(SPACE + "+", "a  b") == (1, 3)

    def test_a_newline_escape_matches_a_newline(self):
        assert span_of(BACKSLASH + "n", "a" + chr(10) + "b") == (1, 2)

    def test_a_tab_escape_matches_a_tab(self):
        assert span_of(BACKSLASH + "t", "a" + chr(9)) == (1, 2)

    def test_an_escaped_special_character_is_a_literal(self):
        assert span_of(BACKSLASH + ".", "a.b") == (1, 2)

    def test_an_escaped_star_is_a_literal(self):
        assert span_of("a" + BACKSLASH + "*", "a*") == (0, 2)

    def test_a_pattern_ending_in_a_backslash_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            compile_pattern("a" + BACKSLASH)
        assert "incomplete escape" in str(caught.value)


class TestGroupsAndAlternation:
    def test_alternation_takes_either_branch(self):
        assert span_of("cat|dog", "hotdog") == (3, 6)

    def test_the_first_branch_that_matches_wins(self):
        found = search(compile_pattern("a|ab"), "ab")
        assert found is not None
        assert found.text == "a"

    def test_a_group_captures_what_it_matched(self):
        found = search(compile_pattern("(a+)"), "xaay")
        assert found is not None
        assert found.groups == ("aa",)

    def test_two_groups_capture_separately(self):
        found = search(compile_pattern("(a+)(b+)"), "aabbb")
        assert found is not None
        assert found.groups == ("aa", "bbb")

    def test_a_group_that_matched_nothing_captures_nil(self):
        # different from capturing an empty string, which a program needs to tell apart
        found = search(compile_pattern("(a)(b)?"), "a")
        assert found is not None
        assert found.groups == ("a", None)

    def test_a_group_that_matched_an_empty_string_captures_it(self):
        found = search(compile_pattern("(a*)b"), "b")
        assert found is not None
        assert found.groups == ("",)

    def test_the_group_count_is_reported(self):
        assert compile_pattern("(a)(b)(c)").groups == 3

    def test_a_pattern_with_no_groups_counts_none(self):
        assert compile_pattern("abc").groups == 0

    def test_nested_groups_are_numbered_outermost_first(self):
        found = search(compile_pattern("((a)b)"), "ab")
        assert found is not None
        assert found.groups == ("ab", "a")

    def test_a_group_that_never_closes_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            compile_pattern("(abc")
        assert "never closed" in str(caught.value)

    def test_an_unmatched_closing_bracket_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            compile_pattern("a)")
        assert "unmatched" in str(caught.value)


class TestRefusedSyntax:
    def test_a_backreference_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            compile_pattern("(a)" + BACKSLASH + "1")
        assert "no backreferences" in str(caught.value)

    def test_the_refusal_explains_why(self):
        with pytest.raises(Arithmetic) as caught:
            compile_pattern("(a)" + BACKSLASH + "1")
        assert "not a regular language" in str(caught.value)

    def test_a_lookahead_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            compile_pattern("(?=a)")
        assert "no lookahead" in str(caught.value)

    def test_a_non_capturing_group_is_refused_too(self):
        # it shares the syntax, so it is refused rather than read as something else
        with pytest.raises(Arithmetic):
            compile_pattern("(?:a)")

    def test_a_quantifier_with_nothing_before_it_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            compile_pattern("*a")
        assert "nothing before it" in str(caught.value)

    def test_a_repetition_with_no_count_is_refused(self):
        with pytest.raises(Arithmetic):
            compile_pattern("a{")

    def test_a_backwards_repetition_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            compile_pattern("a{3,1}")
        assert "counts up" in str(caught.value)


class TestTheStepLimit:
    def test_a_catastrophic_pattern_refuses_rather_than_hanging(self):
        # the failure that takes services down, turned into something catchable
        with pytest.raises(Arithmetic) as caught:
            search(compile_pattern("(a+)+b"), "a" * 24 + "!")
        assert "backtracks too much" in str(caught.value)

    def test_the_refusal_names_the_limit(self):
        with pytest.raises(Arithmetic) as caught:
            search(compile_pattern("(a+)+b"), "a" * 24 + "!")
        assert "200000 steps" in str(caught.value)

    def test_the_refusal_says_why_that_is_better(self):
        with pytest.raises(Arithmetic) as caught:
            search(compile_pattern("(a+)+b"), "a" * 24 + "!")
        assert "better than a hang" in str(caught.value)

    def test_a_short_subject_still_completes(self):
        assert search(compile_pattern("(a+)+b"), "aaab") is not None

    def test_an_ordinary_pattern_is_nowhere_near_the_limit(self):
        # this used to exhaust the host stack, which is why a repeat of a single
        # character term counts its run instead of recursing per character
        assert search(compile_pattern(WORD + "+"), "a" * 5000) is not None

    def test_a_long_dot_repeat_reaches_the_end(self):
        found = search(compile_pattern(".*"), "a" * 5000)
        assert found is not None
        assert found.end == 5000

    def test_a_long_class_repeat_reaches_the_end(self):
        found = search(compile_pattern("[a-z]+"), "a" * 5000)
        assert found is not None
        assert found.end == 5000

    def test_running_out_of_stack_refuses_in_this_language(self):
        # a program cannot catch what it has no name for
        with pytest.raises(Arithmetic) as caught:
            search(compile_pattern("(a)*b"), "a" * 4000 + "!")
        assert "ran out of stack" in str(caught.value)

    def test_the_stack_refusal_suggests_what_to_do(self):
        with pytest.raises(Arithmetic) as caught:
            search(compile_pattern("(a)*b"), "a" * 4000 + "!")
        assert "simplify the pattern" in str(caught.value)

    def test_a_greedy_simple_repeat_still_takes_the_most(self):
        found = search(compile_pattern("a+"), "aaa")
        assert found is not None
        assert found.text == "aaa"

    def test_a_lazy_simple_repeat_still_takes_the_least(self):
        found = search(compile_pattern("a+?"), "aaa")
        assert found is not None
        assert found.text == "a"

    def test_a_bounded_simple_repeat_still_respects_its_bounds(self):
        found = search(compile_pattern("a{2,3}"), "aaaaa")
        assert found is not None
        assert found.text == "aaa"

    def test_a_simple_repeat_still_backtracks_when_it_must(self):
        # the counting path has to give back characters for what follows to match
        found = search(compile_pattern("a+b"), "aaab")
        assert found is not None
        assert found.text == "aaab"


class TestFindingAll:
    def test_every_match_is_found(self):
        found = find_all(compile_pattern(DIGIT + "+"), "a1b22c333")
        assert [one.text for one in found] == ["1", "22", "333"]

    def test_matches_do_not_overlap(self):
        found = find_all(compile_pattern("aa"), "aaaa")
        assert [(one.start, one.end) for one in found] == [(0, 2), (2, 4)]

    def test_nothing_found_gives_an_empty_list(self):
        assert find_all(compile_pattern("z"), "abc") == []

    def test_a_pattern_matching_empty_still_terminates(self):
        found = find_all(compile_pattern("a*"), "ab")
        assert len(found) <= 3

    def test_the_positions_are_recorded(self):
        found = find_all(compile_pattern("b"), "abcb")
        assert [one.start for one in found] == [1, 3]


class TestReplacingAndSplitting:
    def test_every_match_is_replaced(self):
        assert replace_all(compile_pattern(DIGIT + "+"), "a1b22c", "#") == "a#b#c"

    def test_nothing_to_replace_leaves_the_subject_alone(self):
        assert replace_all(compile_pattern("z"), "abc", "#") == "abc"

    def test_a_replacement_can_be_empty(self):
        assert replace_all(compile_pattern(DIGIT), "a1b2", "") == "ab"

    def test_splitting_divides_on_every_match(self):
        assert split_on(compile_pattern(","), "a,b,c") == ["a", "b", "c"]

    def test_splitting_on_something_absent_gives_one_piece(self):
        assert split_on(compile_pattern(";"), "a,b") == ["a,b"]

    def test_splitting_can_produce_empty_pieces(self):
        assert split_on(compile_pattern(","), "a,,b") == ["a", "", "b"]

    def test_splitting_on_a_pattern_works(self):
        assert split_on(compile_pattern(SPACE + "+"), "a  b c") == ["a", "b", "c"]


class TestWholeMatches:
    def test_a_pattern_covering_everything_matches_whole(self):
        assert matches_whole(compile_pattern("[a-z]+"), "abc")

    def test_a_pattern_covering_part_does_not(self):
        assert not matches_whole(compile_pattern("[a-z]+"), "ab1")

    def test_a_pattern_matching_nothing_does_not(self):
        assert not matches_whole(compile_pattern("z"), "abc")

    def test_an_empty_pattern_matches_an_empty_subject_whole(self):
        assert matches_whole(compile_pattern(""), "")


class TestMatchRecords:
    def test_a_match_knows_its_length(self):
        assert Match(start=2, end=5, text="abc").length == 3

    def test_group_zero_is_the_whole_match(self):
        assert Match(start=0, end=1, text="a").group(0) == "a"

    def test_a_group_can_be_asked_for_by_number(self):
        found = Match(start=0, end=2, text="ab", groups=("a", "b"))
        assert found.group(2) == "b"

    def test_a_group_that_does_not_exist_is_nil(self):
        assert Match(start=0, end=1, text="a").group(9) is None
