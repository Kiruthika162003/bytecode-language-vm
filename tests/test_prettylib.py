from __future__ import annotations

import pytest

from ember.errors import Arithmetic, TypeMismatch
from ember.interpreter import run_output, run_treewalk_output
from ember.prettylib import (
    _counts,
    _depth_of,
    _has_cycle,
    _one_line,
    pretty,
    pretty_names,
)
from ember.valueops import stringify

NEWLINE = chr(10)
QUOTE = chr(34)

DEEP = {
    "name": "ada",
    "scores": [1, 2, 3],
    "address": {"street": "a rather long street name", "city": "somewhere"},
    "tags": ["one", "two", "three", "four", "five", "six", "seven"],
}


def evaluate(expression: str) -> str:
    return run_output(f"print {expression};")[0]


class TestRegistration:
    def test_the_functions_are_named(self):
        assert "pretty" in pretty_names()
        assert "valueDepth" in pretty_names()

    def test_the_names_are_sorted(self):
        assert pretty_names() == sorted(pretty_names())

    def test_there_are_eight_of_them(self):
        assert len(pretty_names()) == 8


class TestAgreementWithOrdinaryPrinting:
    @pytest.mark.parametrize(
        "value",
        [
            ["a", "b"],
            {"k": "v"},
            "bare",
            5,
            1.5,
            True,
            None,
            [1, ["a"]],
            {"a": {"b": "c"}},
            [],
            {},
        ],
    )
    def test_the_one_line_form_matches_print(self, value):
        # anything shown differently from print would be misleading
        assert _one_line([value]) == stringify(value)

    def test_a_string_inside_a_list_keeps_its_quotes(self):
        assert _one_line([["a"]]) == "[" + QUOTE + "a" + QUOTE + "]"

    def test_a_string_on_its_own_does_not(self):
        assert _one_line(["a"]) == "a"

    def test_a_small_value_prints_the_same_either_way(self):
        assert pretty([1, 2, 3]) == stringify([1, 2, 3])


class TestWhenItBreaks:
    def test_a_small_value_stays_on_one_line(self):
        assert NEWLINE not in pretty({"a": 1, "b": [1, 2]})

    def test_a_large_value_breaks(self):
        assert NEWLINE in pretty(DEEP)

    def test_a_small_map_inside_a_large_one_stays_flat(self):
        # the rule applied from the inside out
        lines = pretty(DEEP).split(NEWLINE)
        address = next(line for line in lines if "address" in line)
        assert address.count("{") == 1
        assert address.rstrip(",").endswith("}")

    def test_a_narrow_width_breaks_more(self):
        assert len(pretty(DEEP, width=20).split(NEWLINE)) > len(
            pretty(DEEP, width=200).split(NEWLINE)
        )

    def test_a_wide_width_keeps_it_on_one_line(self):
        assert NEWLINE not in pretty(DEEP, width=500)

    def test_the_indent_can_be_chosen(self):
        wide = pretty(DEEP, width=20, step=4)
        assert any(line.startswith("    ") for line in wide.split(NEWLINE))

    def test_a_broken_list_opens_and_closes(self):
        text = pretty([["a" * 40], ["b" * 40]], width=20)
        assert text.startswith("[")
        assert text.rstrip().endswith("]")

    def test_a_broken_map_opens_and_closes(self):
        text = pretty(DEEP, width=20)
        assert text.startswith("{")
        assert text.rstrip().endswith("}")


class TestCommas:
    def test_entries_are_separated_by_commas(self):
        text = pretty(DEEP, width=30)
        assert any(line.rstrip().endswith(",") for line in text.split(NEWLINE))

    def test_the_last_entry_has_no_comma(self):
        # so the result can be pasted back into a program
        lines = [line.rstrip() for line in pretty(DEEP, width=30).split(NEWLINE)]
        closing = next(index for index, line in enumerate(lines) if line == "}")
        assert not lines[closing - 1].endswith(",")

    def test_a_broken_list_ends_without_a_comma(self):
        text = pretty([["a" * 40], ["b" * 40]], width=20)
        lines = [line.rstrip() for line in text.split(NEWLINE)]
        assert not lines[-2].endswith(",")


class TestCycles:
    def test_a_list_holding_itself_prints_a_marker(self):
        looping: list = []
        looping.append(looping)
        assert "repeats" in pretty(looping)

    def test_a_cycle_does_not_recurse_for_ever(self):
        looping: list = []
        looping.append(looping)
        assert len(pretty(looping)) < 100

    def test_a_map_holding_itself_prints_a_marker(self):
        looping: dict = {}
        looping["self"] = looping
        assert "repeats" in pretty(looping)

    def test_a_cycle_is_recognised(self):
        looping: list = []
        looping.append(looping)
        assert _has_cycle([looping])

    def test_a_plain_value_has_no_cycle(self):
        assert not _has_cycle([DEEP])

    def test_a_shared_value_is_not_a_cycle(self):
        shared = [1, 2]
        assert not _has_cycle([[shared, shared]])

    def test_two_lists_referring_to_each_other_are_a_cycle(self):
        first: list = []
        second: list = [first]
        first.append(second)
        assert _has_cycle([first])


class TestMeasuring:
    def test_a_flat_value_has_no_depth(self):
        assert _depth_of([5]) == 0

    def test_a_list_has_a_depth_of_one(self):
        assert _depth_of([[1, 2]]) == 1

    def test_a_nested_list_is_deeper(self):
        assert _depth_of([[[1]]]) == 2

    def test_a_map_of_lists_is_two_deep(self):
        assert _depth_of([{"a": [1]}]) == 2

    def test_a_cycle_does_not_make_the_depth_infinite(self):
        looping: list = []
        looping.append(looping)
        assert _depth_of([looping]) >= 1

    def test_the_counts_cover_every_kind(self):
        found = _counts([DEEP])
        assert found["map"] == 2
        assert found["list"] == 2

    def test_the_counts_include_the_leaves(self):
        assert _counts([[1, 2, 3]])["int"] == 3

    def test_a_shared_collection_is_counted_once(self):
        shared = [1, 2]
        assert _counts([[shared, shared]])["list"] == 2

    def test_a_value_fits_a_generous_width(self):
        source = "fitsWidth([1, 2, 3], 100)"
        assert evaluate(source) == "true"

    def test_a_value_does_not_fit_a_narrow_one(self):
        source = "fitsWidth([1, 2, 3], 3)"
        assert evaluate(source) == "false"


class TestFromPrograms:
    def test_a_program_can_print_prettily(self):
        source = 'print pretty({"a": 1});'
        assert run_output(source) == ['{"a": 1}']

    def test_a_program_can_choose_a_width(self):
        source = "print prettyTo([1, 2, 3], 3);"
        assert NEWLINE in run_output(source)[0]

    def test_a_program_can_get_the_lines(self):
        source = "print len(prettyLines([1, 2, 3]));"
        assert run_output(source) == ["1"]

    def test_a_broken_value_gives_several_lines(self):
        source = "print len(prettyLines([1, 2, 3])) < len(prettyLines("
        source += "[100000000, 200000000, 300000000, 400000000, 500000000,"
        source += " 600000000, 700000000, 800000000, 900000000, 100000000]));"
        assert run_output(source) == ["true"]

    def test_a_program_can_ask_for_one_line(self):
        source = 'print oneLine({"a": [1, 2]});'
        assert run_output(source) == ['{"a": [1, 2]}']

    def test_a_program_can_measure_depth(self):
        assert evaluate("valueDepth([[1]])") == "2"

    def test_a_program_can_count_the_kinds(self):
        found = evaluate("valueCounts([1, 2])")
        assert "int" in found

    def test_a_program_can_ask_about_cycles(self):
        assert evaluate("hasCycle([1, 2])") == "false"

    def test_a_width_of_zero_is_refused(self):
        with pytest.raises(Arithmetic):
            run_output("print prettyTo([1], 0);")

    def test_a_width_that_is_not_whole_is_refused(self):
        with pytest.raises(TypeMismatch):
            run_output("print prettyTo([1], 2.5);")


class TestBothBackendsAgree:
    @pytest.mark.parametrize(
        "expression",
        [
            'pretty({"a": 1, "b": [1, 2]})',
            "prettyTo([1, 2, 3], 5)",
            "prettyLines([1, 2, 3])",
            "fitsWidth([1, 2, 3], 100)",
            'oneLine({"a": [1, 2]})',
            "valueDepth([[1]])",
            "valueCounts([1, 2])",
            "hasCycle([1, 2])",
        ],
    )
    def test_the_two_backends_agree(self, expression):
        source = f"print {expression};"
        assert run_output(source) == run_treewalk_output(source)
