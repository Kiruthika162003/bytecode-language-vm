from __future__ import annotations

import pytest

from ember.errors import Arithmetic, TypeMismatch
from ember.interpreter import run_output, run_treewalk_output
from ember.jsonlib import decode_text, encode_value, json_names

BACKSLASH = chr(92)
QUOTE = chr(34)


def evaluate(expression: str) -> str:
    return run_output(f"print {expression};")[0]


class TestRegistration:
    def test_the_three_functions_are_named(self):
        assert json_names() == ["fromJson", "isJson", "toJson"]


class TestEncodingScalars:
    def test_nil_becomes_null(self):
        assert encode_value(None) == "null"

    def test_booleans_keep_their_words(self):
        assert encode_value(True) == "true"
        assert encode_value(False) == "false"

    def test_an_integer_has_no_point(self):
        assert encode_value(7) == "7"

    def test_a_whole_float_keeps_its_point(self):
        # what was written comes back the same, which is what makes round trips stable
        assert encode_value(1.0) == "1.0"

    def test_a_negative_number_keeps_its_sign(self):
        assert encode_value(-3) == "-3"

    def test_a_string_is_quoted(self):
        assert encode_value("hi") == QUOTE + "hi" + QUOTE

    def test_a_quote_inside_a_string_is_escaped(self):
        assert encode_value(QUOTE) == QUOTE + BACKSLASH + QUOTE + QUOTE

    def test_a_backslash_is_escaped(self):
        assert encode_value(BACKSLASH) == QUOTE + BACKSLASH + BACKSLASH + QUOTE

    def test_a_newline_becomes_its_escape(self):
        assert encode_value(chr(10)) == QUOTE + BACKSLASH + "n" + QUOTE

    def test_a_tab_becomes_its_escape(self):
        assert encode_value(chr(9)) == QUOTE + BACKSLASH + "t" + QUOTE

    def test_an_unprintable_character_becomes_a_unicode_escape(self):
        assert encode_value(chr(1)) == QUOTE + BACKSLASH + "u0001" + QUOTE


class TestEncodingCollections:
    def test_an_empty_list(self):
        assert encode_value([]) == "[]"

    def test_a_list_of_numbers(self):
        assert encode_value([1, 2]) == "[1,2]"

    def test_an_empty_map(self):
        assert encode_value({}) == "{}"

    def test_a_map_with_one_entry(self):
        assert encode_value({"a": 1}) == QUOTE.join(["{", "a", ":1}"])

    def test_nesting_is_followed(self):
        assert encode_value({"a": [1, {}]}).endswith("[1,{}]}")

    def test_a_map_with_a_number_key_is_refused(self):
        # a numeric key quietly stringified would lose information on the way back
        with pytest.raises(TypeMismatch) as caught:
            encode_value({1: "a"})
        assert "string keys" in str(caught.value)

    def test_the_refusal_names_the_offending_type(self):
        # the language calls a whole number an int, keeping it apart from a float
        with pytest.raises(TypeMismatch) as caught:
            encode_value({1: "a"})
        assert "type int" in str(caught.value)


class TestEncodingRefusals:
    def test_a_function_cannot_be_written(self):
        with pytest.raises(TypeMismatch) as caught:
            run_output("fn f() { return 1; } print toJson(f);")
        assert "no representation" in str(caught.value)

    def test_the_refusal_lists_what_json_does_hold(self):
        with pytest.raises(TypeMismatch) as caught:
            run_output("fn f() { return 1; } print toJson(f);")
        assert "numbers" in str(caught.value)

    def test_a_class_instance_cannot_be_written(self):
        with pytest.raises(TypeMismatch):
            run_output("class C { } print toJson(C());")

    def test_a_value_that_refers_to_itself_is_refused_by_depth(self):
        looping: list = []
        looping.append(looping)
        with pytest.raises(Arithmetic) as caught:
            encode_value(looping)
        assert "refers to itself" in str(caught.value)


class TestDecodingScalars:
    def test_null_becomes_nil(self):
        assert decode_text("null") is None

    def test_true_and_false(self):
        assert decode_text("true") is True
        assert decode_text("false") is False

    def test_a_number_without_a_point_is_an_integer(self):
        assert decode_text("1") == 1
        assert isinstance(decode_text("1"), int)

    def test_a_number_with_a_point_is_a_float(self):
        # faithful to the text rather than to what the value is worth
        assert isinstance(decode_text("1.0"), float)

    def test_a_number_with_an_exponent_is_a_float(self):
        assert isinstance(decode_text("1e3"), float)

    def test_a_negative_exponent_is_read(self):
        assert decode_text("1e-2") == 0.01

    def test_a_negative_number_is_read(self):
        assert decode_text("-4") == -4

    def test_a_string_loses_its_quotes(self):
        assert decode_text(QUOTE + "hi" + QUOTE) == "hi"

    def test_an_escape_is_understood(self):
        assert decode_text(QUOTE + BACKSLASH + "n" + QUOTE) == chr(10)

    def test_a_unicode_escape_is_understood(self):
        assert decode_text(QUOTE + BACKSLASH + "u0041" + QUOTE) == "A"

    def test_whitespace_around_a_value_is_skipped(self):
        assert decode_text("  1  ") == 1


class TestDecodingCollections:
    def test_an_empty_list(self):
        assert decode_text("[]") == []

    def test_a_list_of_mixed_values(self):
        assert decode_text('[1, "a", null]') == [1, "a", None]

    def test_an_empty_map(self):
        assert decode_text("{}") == {}

    def test_a_map_with_entries(self):
        assert decode_text('{"a": 1, "b": 2}') == {"a": 1, "b": 2}

    def test_nesting_is_followed(self):
        assert decode_text('{"a": [1, {"b": 2}]}') == {"a": [1, {"b": 2}]}


class TestStrictness:
    @pytest.mark.parametrize(
        "text",
        ['{"a":1,}', "[1,]", "{a:1}", "", "[1", "{", "tru", "1 2", "nul", "-", "[,]"],
    )
    def test_a_malformed_document_is_refused(self, text):
        # a lenient parser accepts what other tools reject, moving the problem
        with pytest.raises((Arithmetic, TypeMismatch)):
            decode_text(text)

    def test_a_trailing_comma_in_a_list_is_named(self):
        with pytest.raises(Arithmetic) as caught:
            decode_text("[1,]")
        assert "trailing comma" in str(caught.value)

    def test_a_trailing_comma_in_a_map_is_named(self):
        with pytest.raises(Arithmetic) as caught:
            decode_text('{"a":1,}')
        assert "trailing comma" in str(caught.value)

    def test_an_unquoted_key_is_named(self):
        with pytest.raises(Arithmetic) as caught:
            decode_text("{a:1}")
        assert "unquoted key" in str(caught.value)

    def test_text_after_the_value_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            decode_text("1 2")
        assert "after the value ended" in str(caught.value)

    def test_the_position_is_reported(self):
        with pytest.raises(Arithmetic) as caught:
            decode_text("[1,]")
        assert "position" in str(caught.value)

    def test_an_unknown_escape_is_refused(self):
        with pytest.raises(Arithmetic):
            decode_text(QUOTE + BACKSLASH + "q" + QUOTE)

    def test_a_short_unicode_escape_is_refused(self):
        with pytest.raises(Arithmetic):
            decode_text(QUOTE + BACKSLASH + "u01" + QUOTE)

    def test_a_string_that_never_closes_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            decode_text(QUOTE + "abc")
        assert "inside a string" in str(caught.value)

    def test_too_deep_a_document_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            decode_text("[" * 200 + "]" * 200)
        assert "levels of nesting" in str(caught.value)


class TestRoundTripping:
    @pytest.mark.parametrize(
        "value",
        [None, True, False, 0, -3, 1, 1.0, 2.5, "", "hi", [], [1, "a", None], {}, {"a": [1]}],
    )
    def test_a_value_survives_a_round_trip_with_its_type(self, value):
        returned = decode_text(encode_value(value))
        assert returned == value
        assert type(returned) is type(value)

    def test_an_integer_does_not_become_a_float(self):
        assert isinstance(decode_text(encode_value(1)), int)

    def test_a_whole_float_does_not_become_an_integer(self):
        assert isinstance(decode_text(encode_value(1.0)), float)

    def test_an_awkward_string_survives(self):
        awkward = QUOTE + BACKSLASH + chr(10) + chr(9)
        assert decode_text(encode_value(awkward)) == awkward


class TestFromPrograms:
    def test_a_program_can_write_json(self):
        assert evaluate('toJson([1, 2])') == "[1,2]"

    def test_a_program_can_read_json(self):
        assert evaluate('fromJson("[1, 2]")') == "[1, 2]"

    def test_a_program_can_test_json(self):
        assert evaluate('isJson("[1]")') == "true"

    def test_malformed_json_is_not_json(self):
        assert evaluate('isJson("[1,]")') == "false"

    def test_reading_something_that_is_not_a_string_is_refused(self):
        with pytest.raises(TypeMismatch):
            run_output("print fromJson(5);")

    def test_testing_something_that_is_not_a_string_is_refused(self):
        with pytest.raises(TypeMismatch):
            run_output("print isJson(5);")

    def test_a_map_survives_a_round_trip_through_a_program(self):
        source = 'let m = {"a": 1}; print fromJson(toJson(m))["a"];'
        assert run_output(source) == ["1"]


class TestBothBackendsAgree:
    @pytest.mark.parametrize(
        "expression",
        [
            "toJson([1, 1.0, true, nil])",
            'toJson({"a": [1, 2]})',
            'fromJson("[1, 2.5]")',
            'fromJson("{\\"a\\": 1}")["a"]',
            'isJson("{}")',
            'isJson("nope")',
        ],
    )
    def test_the_two_backends_agree(self, expression):
        source = f"print {expression};"
        assert run_output(source) == run_treewalk_output(source)
