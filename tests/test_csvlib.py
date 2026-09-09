from __future__ import annotations

import pytest

from ember.csvlib import _to_csv, csv_names, parse_rows, quote_field
from ember.errors import Arithmetic, TypeMismatch
from ember.interpreter import run_output, run_treewalk_output

QUOTE = chr(34)
NEWLINE = chr(10)
RETURN = chr(13)


def evaluate(expression: str) -> str:
    return run_output(f"print {expression};")[0]


class TestRegistration:
    def test_the_functions_are_named(self):
        assert "fromCsv" in csv_names()
        assert "toCsv" in csv_names()

    def test_the_names_are_sorted(self):
        assert csv_names() == sorted(csv_names())

    def test_there_are_nine_of_them(self):
        assert len(csv_names()) == 9


class TestParsingPlainText:
    def test_a_single_row(self):
        assert parse_rows("a,b,c") == [["a", "b", "c"]]

    def test_two_rows(self):
        assert parse_rows("a,b" + NEWLINE + "c,d") == [["a", "b"], ["c", "d"]]

    def test_one_field(self):
        assert parse_rows("a") == [["a"]]

    def test_nothing_gives_no_rows(self):
        assert parse_rows("") == []

    def test_a_trailing_newline_does_not_add_a_row(self):
        assert parse_rows("a,b" + NEWLINE) == [["a", "b"]]

    def test_carriage_returns_are_understood(self):
        assert parse_rows("a,b" + RETURN + NEWLINE + "c,d") == [["a", "b"], ["c", "d"]]

    def test_a_lone_carriage_return_ends_a_row(self):
        assert parse_rows("a" + RETURN + "b") == [["a"], ["b"]]

    def test_rows_of_different_lengths_come_back_as_they_are(self):
        # padding would invent fields that were not in the file
        assert parse_rows("a,b" + NEWLINE + "c") == [["a", "b"], ["c"]]


class TestEmptyFields:
    def test_a_middle_field_can_be_empty(self):
        assert parse_rows("a,,b") == [["a", "", "b"]]

    def test_a_leading_field_can_be_empty(self):
        assert parse_rows(",a") == [["", "a"]]

    def test_a_trailing_field_can_be_empty(self):
        assert parse_rows("a,") == [["a", ""]]

    def test_a_row_of_only_commas_is_all_empty(self):
        assert parse_rows(",,") == [["", "", ""]]

    def test_an_empty_field_is_a_string_not_nil(self):
        # the format cannot tell present and empty from absent
        assert evaluate('type(fromCsv("a,,b")[0][1])') == "string"


class TestQuoting:
    def test_a_quoted_field_loses_its_quotes(self):
        assert parse_rows(QUOTE + "a" + QUOTE) == [["a"]]

    def test_a_comma_inside_quotes_stays_in_the_field(self):
        text = QUOTE + "has,comma" + QUOTE + ",plain"
        assert parse_rows(text) == [["has,comma", "plain"]]

    def test_two_quotes_inside_quotes_mean_one(self):
        text = QUOTE + "has" + QUOTE + QUOTE + "quote" + QUOTE
        assert parse_rows(text) == [["has" + QUOTE + "quote"]]

    def test_a_newline_inside_quotes_stays_in_the_field(self):
        text = QUOTE + "two" + NEWLINE + "lines" + QUOTE + ",plain"
        assert parse_rows(text) == [["two" + NEWLINE + "lines", "plain"]]

    def test_an_empty_quoted_field_is_empty(self):
        assert parse_rows(QUOTE + QUOTE + ",a") == [["", "a"]]

    def test_a_quote_that_never_closes_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            parse_rows(QUOTE + "never closed")
        assert "never closed" in str(caught.value)

    def test_the_refusal_suggests_what_to_look_for(self):
        with pytest.raises(Arithmetic) as caught:
            parse_rows(QUOTE + "open")
        assert "unmatched quote" in str(caught.value)


class TestWhitespace:
    def test_spaces_around_a_field_are_kept(self):
        # trimming would make two spaces indistinguishable from empty
        assert parse_rows("  spaced  ,b") == [["  spaced  ", "b"]]

    def test_a_field_of_only_spaces_is_not_empty(self):
        assert parse_rows("  ,b") == [["  ", "b"]]

    def test_a_tab_is_an_ordinary_character(self):
        assert parse_rows("a" + chr(9) + ",b") == [["a" + chr(9), "b"]]


class TestNothingIsConverted:
    def test_a_number_reads_as_a_string(self):
        # guessing types is where CSV handling goes wrong in practice
        assert evaluate('type(fromCsv("42")[0][0])') == "string"

    def test_leading_zeros_survive(self):
        assert evaluate('fromCsv("007")[0][0]') == "007"

    def test_something_that_looks_like_a_version_survives(self):
        assert evaluate('fromCsv("1.2.3")[0][0]') == "1.2.3"

    def test_a_long_digit_string_keeps_every_digit(self):
        long_number = "9" * 25
        assert evaluate(f'fromCsv("{long_number}")[0][0]') == long_number

    def test_the_word_true_reads_as_a_string(self):
        assert evaluate('type(fromCsv("true")[0][0])') == "string"


class TestQuotingOnTheWayOut:
    def test_a_plain_field_is_not_quoted(self):
        assert quote_field("plain") == "plain"

    def test_a_field_with_a_comma_is_quoted(self):
        assert quote_field("a,b") == QUOTE + "a,b" + QUOTE

    def test_a_field_with_a_quote_is_quoted_and_doubled(self):
        assert quote_field("a" + QUOTE) == QUOTE + "a" + QUOTE + QUOTE + QUOTE

    def test_a_field_with_a_newline_is_quoted(self):
        assert quote_field("a" + NEWLINE) == QUOTE + "a" + NEWLINE + QUOTE

    def test_an_empty_field_is_not_quoted(self):
        assert quote_field("") == ""

    def test_a_field_with_spaces_is_not_quoted(self):
        assert quote_field("  a  ") == "  a  "


class TestWriting:
    def test_a_row_is_joined_with_commas(self):
        assert evaluate('csvFormatLine(["a", "b"])') == "a,b"

    def test_a_document_is_joined_with_newlines(self):
        assert evaluate('toCsv([["a"], ["b"]])') == "a" + NEWLINE + "b"

    def test_an_empty_document_writes_nothing(self):
        assert evaluate("toCsv([])") == ""

    def test_a_field_needing_quotes_gets_them(self):
        expected = QUOTE + "a,b" + QUOTE
        assert evaluate('csvFormatLine(["a,b"])') == expected

    def test_a_number_field_is_refused(self):
        with pytest.raises(TypeMismatch) as caught:
            run_output("print toCsv([[1]]);")
        assert "convert it" in str(caught.value)

    def test_the_refusal_says_the_conversion_should_be_chosen(self):
        with pytest.raises(TypeMismatch) as caught:
            run_output("print toCsv([[1]]);")
        assert "something the program chose" in str(caught.value)

    def test_a_row_that_is_not_a_list_is_refused(self):
        with pytest.raises(TypeMismatch) as caught:
            run_output('print toCsv(["a"]);')
        assert "each row to be a list" in str(caught.value)

    def test_something_that_is_not_a_list_is_refused(self):
        with pytest.raises(TypeMismatch):
            run_output('print toCsv("a,b");')


class TestRoundTripping:
    @pytest.mark.parametrize(
        "field",
        ["plain", "", "  spaced  ", "has,comma", "007", "1.2.3"],
    )
    def test_a_field_survives_a_round_trip(self, field):
        rows = [[field]]
        assert parse_rows(_written(rows)) == rows

    def test_a_lone_empty_field_is_quoted_to_keep_the_round_trip(self):
        # empty text is also how a document with no rows is written, so without this
        # the two documents would be indistinguishable and one of them lost
        assert _written([[""]]) == QUOTE + QUOTE

    def test_no_rows_and_one_empty_field_stay_distinguishable(self):
        assert _written([]) != _written([[""]])

    def test_no_rows_still_writes_as_nothing(self):
        assert _written([]) == ""

    def test_an_empty_field_beside_another_needs_no_quotes(self):
        assert _written([["", "a"]]) == ",a"

    def test_an_awkward_field_survives(self):
        awkward = "has" + QUOTE + "quote" + NEWLINE + "and,comma"
        assert parse_rows(_written([[awkward]])) == [[awkward]]

    def test_a_whole_document_survives(self):
        rows = [["a", "b,c"], ["", "d" + QUOTE]]
        assert parse_rows(_written(rows)) == rows

    def test_a_round_trip_through_a_program_survives(self):
        source = 'print fromCsv(toCsv([["a,b", "c"]]))[0][0];'
        assert run_output(source) == ["a,b"]


def _written(rows: list[list[str]]) -> str:
    return _to_csv([rows])


class TestOneLine:
    def test_a_single_row_is_read(self):
        assert evaluate('csvLine("a,b")') == '["a", "b"]'

    def test_an_empty_line_reads_as_nothing(self):
        assert evaluate('csvLine("")') == "[]"

    def test_two_rows_are_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output('print csvLine("a' + chr(92) + 'nb");')
        assert "reads one row" in str(caught.value)

    def test_the_refusal_points_at_the_alternative(self):
        with pytest.raises(Arithmetic) as caught:
            run_output('print csvLine("a' + chr(92) + 'nb");')
        assert "fromCsv" in str(caught.value)


class TestShape:
    def test_the_widths_are_reported(self):
        assert evaluate('csvWidths([["a", "b"], ["c"]])') == "[2, 1]"

    def test_a_rectangular_document_is_recognised(self):
        assert evaluate('csvRectangular([["a", "b"], ["c", "d"]])') == "true"

    def test_a_ragged_document_is_recognised(self):
        assert evaluate('csvRectangular([["a", "b"], ["c"]])') == "false"

    def test_an_empty_document_is_rectangular(self):
        assert evaluate("csvRectangular([])") == "true"

    def test_padding_squares_the_rows(self):
        assert evaluate('csvPadded([["a", "b"], ["c"]])') == '[["a", "b"], ["c", ""]]'

    def test_padding_a_rectangle_changes_nothing(self):
        assert evaluate('csvPadded([["a"], ["b"]])') == '[["a"], ["b"]]'

    def test_padding_nothing_gives_nothing(self):
        assert evaluate("csvPadded([])") == "[]"

    def test_a_column_is_taken_from_every_row(self):
        assert evaluate('csvColumn([["a", "b"], ["c", "d"]], 1)') == '["b", "d"]'

    def test_the_first_column_is_index_zero(self):
        assert evaluate('csvColumn([["a", "b"]], 0)') == '["a"]'

    def test_a_column_beyond_a_ragged_row_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output('print csvColumn([["a", "b"], ["c"]], 1);')
        assert "not rectangular" in str(caught.value)

    def test_the_refusal_names_the_row(self):
        with pytest.raises(Arithmetic) as caught:
            run_output('print csvColumn([["a", "b"], ["c"]], 1);')
        assert "row 2" in str(caught.value)

    def test_a_negative_column_is_refused(self):
        with pytest.raises(Arithmetic):
            run_output('print csvColumn([["a"]], -1);')


class TestHeaders:
    def test_each_row_becomes_a_map(self):
        source = 'print csvWithHeader([["name", "age"], ["ada", "36"]]);'
        assert run_output(source) == ['[{"name": "ada", "age": "36"}]']

    def test_the_header_row_is_not_a_row_of_data(self):
        source = 'print len(csvWithHeader([["a"], ["1"], ["2"]]));'
        assert run_output(source) == ["2"]

    def test_a_document_with_only_a_header_gives_nothing(self):
        assert evaluate('csvWithHeader([["a", "b"]])') == "[]"

    def test_an_empty_document_gives_nothing(self):
        assert evaluate("csvWithHeader([])") == "[]"

    def test_a_repeated_header_name_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output('print csvWithHeader([["a", "a"], ["1", "2"]]);')
        assert "names a column twice" in str(caught.value)

    def test_a_row_of_the_wrong_length_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output('print csvWithHeader([["a", "b"], ["1"]]);')
        assert "cannot be paired" in str(caught.value)

    def test_the_refusal_names_the_row_and_both_counts(self):
        with pytest.raises(Arithmetic) as caught:
            run_output('print csvWithHeader([["a", "b"], ["1"]]);')
        message = str(caught.value)
        assert "row 2" in message
        assert "1 fields" in message


class TestBothBackendsAgree:
    @pytest.mark.parametrize(
        "expression",
        [
            'fromCsv("a,b' + chr(92) + 'nc,d")',
            'fromCsv("a,,b")',
            'toCsv([["a", "b,c"]])',
            'csvLine("a,b")',
            'csvFormatLine(["a", "b,c"])',
            'csvWidths([["a", "b"], ["c"]])',
            'csvRectangular([["a"], ["b"]])',
            'csvPadded([["a", "b"], ["c"]])',
            'csvColumn([["a", "b"], ["c", "d"]], 0)',
            'csvWithHeader([["n", "v"], ["a", "1"]])',
        ],
    )
    def test_the_two_backends_agree(self, expression):
        source = f"print {expression};"
        assert run_output(source) == run_treewalk_output(source)
