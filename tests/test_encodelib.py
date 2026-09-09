from __future__ import annotations

import base64
import urllib.parse

import pytest

from ember.encodelib import decode_base64, encode_base64, encode_names
from ember.errors import Arithmetic, TypeMismatch
from ember.interpreter import run_output, run_treewalk_output

QUOTE = chr(34)
ACCENTED = "caf" + chr(233)
WIDE = chr(20320) + chr(22909)


def quoted(text: str) -> str:
    return QUOTE + text + QUOTE


def evaluate(expression: str) -> str:
    return run_output(f"print {expression};")[0]


SUBJECTS = [
    "",
    "a",
    "ab",
    "abc",
    "abcd",
    "hello world",
    ACCENTED,
    WIDE,
    "a+b/c=d",
    "~-._",
    "100%",
]


class TestRegistration:
    def test_the_functions_are_named(self):
        assert "toBase64" in encode_names()
        assert "urlEncoded" in encode_names()

    def test_the_names_are_sorted(self):
        assert encode_names() == sorted(encode_names())

    def test_there_are_sixteen_of_them(self):
        assert len(encode_names()) == 16


class TestAgreementWithTheHost:
    @pytest.mark.parametrize("text", SUBJECTS)
    def test_base64_matches_the_host(self, text):
        # the host's encoder is an independent implementation of the same standard
        assert encode_base64(text) == base64.b64encode(text.encode()).decode()

    @pytest.mark.parametrize("text", SUBJECTS)
    def test_percent_encoding_matches_the_host(self, text):
        theirs = urllib.parse.quote(text, safe="-._~")
        assert evaluate(f"urlEncoded({quoted(text)})") == theirs

    @pytest.mark.parametrize("text", SUBJECTS)
    def test_hexadecimal_matches_the_host(self, text):
        assert evaluate(f"toHexText({quoted(text)})") == text.encode().hex()


class TestBase64:
    def test_three_bytes_become_four_characters(self):
        assert encode_base64("abc") == "YWJj"

    def test_one_byte_pads_with_two_equals(self):
        assert encode_base64("a") == "YQ=="

    def test_two_bytes_pad_with_one_equals(self):
        assert encode_base64("ab") == "YWI="

    def test_nothing_encodes_to_nothing(self):
        assert encode_base64("") == ""

    def test_the_length_is_always_a_multiple_of_four(self):
        for text in SUBJECTS:
            assert len(encode_base64(text)) % 4 == 0

    @pytest.mark.parametrize("text", SUBJECTS)
    def test_a_round_trip_returns_the_original(self, text):
        assert decode_base64(encode_base64(text)) == text

    def test_text_outside_ascii_survives(self):
        assert decode_base64(encode_base64(ACCENTED)) == ACCENTED

    def test_wide_characters_survive(self):
        assert decode_base64(encode_base64(WIDE)) == WIDE

    def test_text_of_the_wrong_length_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            decode_base64("YWJ")
        assert "groups of four" in str(caught.value)

    def test_the_refusal_explains_why_padding_is_required(self):
        with pytest.raises(Arithmetic) as caught:
            decode_base64("YWJ")
        assert "last byte is ambiguous" in str(caught.value)

    def test_padding_in_the_middle_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            decode_base64("Y=JjYWJj")
        assert "only appear at the very end" in str(caught.value)

    def test_a_character_outside_the_alphabet_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            decode_base64("YW!j")
        assert "not in the base64 alphabet" in str(caught.value)

    def test_bytes_that_are_not_text_are_refused(self):
        with pytest.raises(Arithmetic) as caught:
            decode_base64("//8=")
        assert "not text this language can hold" in str(caught.value)


class TestUrlSafeBase64:
    def test_the_url_safe_alphabet_avoids_plus_and_slash(self):
        awkward = chr(251) + chr(255)
        encoded = evaluate(f"toBase64Url({quoted(awkward)})")
        assert "+" not in encoded
        assert "/" not in encoded

    @pytest.mark.parametrize("text", SUBJECTS)
    def test_a_url_safe_round_trip_returns_the_original(self, text):
        source = f"fromBase64Url(toBase64Url({quoted(text)}))"
        assert evaluate(source) == text

    def test_the_two_alphabets_are_not_interchangeable(self):
        # the variant is a separate function rather than a flag nobody remembers
        assert "toBase64Url" in encode_names()
        assert "fromBase64Url" in encode_names()


class TestHexadecimal:
    def test_a_byte_becomes_two_digits(self):
        assert evaluate(f"toHexText({quoted('a')})") == "61"

    def test_nothing_encodes_to_nothing(self):
        assert evaluate(f"toHexText({quoted('')})") == ""

    @pytest.mark.parametrize("text", SUBJECTS)
    def test_a_round_trip_returns_the_original(self, text):
        assert evaluate(f"fromHexText(toHexText({quoted(text)}))") == text

    def test_uppercase_digits_are_accepted(self):
        assert evaluate(f"fromHexText({quoted('6162')})") == "ab"

    def test_an_odd_length_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output(f"print fromHexText({quoted('616')});")
        assert "comes in pairs" in str(caught.value)

    def test_a_character_that_is_not_a_digit_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output(f"print fromHexText({quoted('6z')});")
        assert "not a pair of hexadecimal digits" in str(caught.value)


class TestPercentEncoding:
    def test_an_unreserved_character_stays_literal(self):
        assert evaluate(f"urlEncoded({quoted('aZ0-._~')})") == "aZ0-._~"

    def test_a_space_becomes_its_percent_form(self):
        # the plus convention belongs to form submission, not to addresses
        assert evaluate(f"urlEncoded({quoted('a b')})") == "a%20b"

    def test_a_slash_is_encoded(self):
        assert evaluate(f"urlEncoded({quoted('a/b')})") == "a%2Fb"

    def test_a_percent_is_encoded(self):
        assert evaluate(f"urlEncoded({quoted('100%')})") == "100%25"

    def test_text_outside_ascii_becomes_several_escapes(self):
        assert evaluate(f"urlEncoded({quoted(ACCENTED)})") == "caf%C3%A9"

    @pytest.mark.parametrize("text", SUBJECTS)
    def test_a_round_trip_returns_the_original(self, text):
        assert evaluate(f"urlDecoded(urlEncoded({quoted(text)}))") == text

    def test_lowercase_escapes_are_accepted_on_the_way_back(self):
        assert evaluate(f"urlDecoded({quoted('a%2fb')})") == "a/b"

    def test_an_incomplete_escape_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output(f"print urlDecoded({quoted('a%2')});")
        assert "incomplete" in str(caught.value)

    def test_a_bad_escape_is_refused(self):
        with pytest.raises(Arithmetic):
            run_output(f"print urlDecoded({quoted('a%zz')});")

    def test_a_plus_stays_a_plus_in_an_address(self):
        assert evaluate(f"urlDecoded({quoted('a+b')})") == "a+b"


class TestFormEncoding:
    def test_a_space_becomes_a_plus(self):
        assert evaluate(f"formEncoded({quoted('a b')})") == "a+b"

    def test_a_plus_is_still_escaped(self):
        assert evaluate(f"formEncoded({quoted('a+b')})") == "a%2Bb"

    def test_a_round_trip_returns_the_original(self):
        assert evaluate(f"formDecoded(formEncoded({quoted('a b+c')})) ") == "a b+c"

    def test_the_two_conventions_differ_on_a_space(self):
        # the distinction that produces wrong data most often
        assert evaluate(f"formEncoded({quoted('a b')})") != evaluate(
            f"urlEncoded({quoted('a b')})"
        )

    @pytest.mark.parametrize("text", SUBJECTS)
    def test_a_form_round_trip_returns_the_original(self, text):
        assert evaluate(f"formDecoded(formEncoded({quoted(text)}))") == text


class TestCodePoints:
    def test_a_character_becomes_its_code_point(self):
        assert evaluate(f"codePoint({quoted('a')})") == "97"

    def test_a_code_point_becomes_a_character(self):
        assert evaluate("fromCodePoint(97)") == "a"

    def test_a_round_trip_returns_the_character(self):
        assert evaluate(f"fromCodePoint(codePoint({quoted('Z')}))") == "Z"

    def test_a_wide_character_has_a_large_code_point(self):
        assert int(evaluate(f"codePoint({quoted(chr(20320))})")) == 20320

    def test_asking_about_two_characters_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output(f"print codePoint({quoted('ab')});")
        assert "reads one character" in str(caught.value)

    def test_asking_about_nothing_is_refused(self):
        with pytest.raises(Arithmetic):
            run_output(f"print codePoint({quoted('')});")

    def test_a_code_point_out_of_range_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output("print fromCodePoint(1114112);")
        assert "not a character code point" in str(caught.value)

    def test_a_negative_code_point_is_refused(self):
        with pytest.raises(Arithmetic):
            run_output("print fromCodePoint(-1);")

    def test_every_code_point_of_a_string_can_be_asked_for(self):
        assert evaluate(f"codePoints({quoted('abc')})") == "[97, 98, 99]"

    def test_a_string_can_be_built_from_code_points(self):
        assert evaluate("fromCodePoints([97, 98, 99])") == "abc"

    def test_code_points_round_trip(self):
        assert evaluate(f"fromCodePoints(codePoints({quoted(WIDE)}))") == WIDE

    def test_something_that_is_not_a_list_is_refused(self):
        with pytest.raises(TypeMismatch):
            run_output("print fromCodePoints(97);")


class TestMeasuring:
    def test_an_ascii_string_has_one_byte_per_character(self):
        assert evaluate(f"byteLength({quoted('abc')})") == "3"

    def test_an_accented_character_takes_two_bytes(self):
        # which is why the byte length is not the character count
        assert evaluate(f"byteLength({quoted(ACCENTED)})") == "5"

    def test_a_wide_character_takes_three_bytes(self):
        assert evaluate(f"byteLength({quoted(WIDE)})") == "6"

    def test_nothing_takes_no_bytes(self):
        assert evaluate(f"byteLength({quoted('')})") == "0"

    def test_an_ascii_string_is_recognised(self):
        assert evaluate(f"isAscii({quoted('abc')})") == "true"

    def test_an_accented_string_is_not_ascii(self):
        assert evaluate(f"isAscii({quoted(ACCENTED)})") == "false"

    def test_nothing_counts_as_ascii(self):
        assert evaluate(f"isAscii({quoted('')})") == "true"


class TestRefusals:
    @pytest.mark.parametrize(
        "call",
        [
            "toBase64(5)",
            "fromBase64(5)",
            "toHexText(5)",
            "urlEncoded(5)",
            "codePoint(5)",
            "byteLength(5)",
            "isAscii(5)",
        ],
    )
    def test_something_that_is_not_a_string_is_refused(self, call):
        with pytest.raises(TypeMismatch):
            run_output(f"print {call};")

    def test_a_code_point_that_is_not_whole_is_refused(self):
        with pytest.raises(TypeMismatch):
            run_output("print fromCodePoint(97.5);")


class TestBothBackendsAgree:
    @pytest.mark.parametrize(
        "expression",
        [
            f"toBase64({quoted('hello world')})",
            f"fromBase64({quoted('aGVsbG8=')})",
            f"toBase64Url({quoted('hello world')})",
            f"toHexText({quoted('abc')})",
            f"fromHexText({quoted('616263')})",
            f"urlEncoded({quoted('a b/c')})",
            f"urlDecoded({quoted('a%20b')})",
            f"formEncoded({quoted('a b')})",
            f"formDecoded({quoted('a+b')})",
            f"codePoint({quoted('a')})",
            "fromCodePoint(97)",
            f"codePoints({quoted('abc')})",
            "fromCodePoints([97, 98])",
            f"byteLength({quoted(ACCENTED)})",
            f"isAscii({quoted('abc')})",
        ],
    )
    def test_the_two_backends_agree(self, expression):
        source = f"print {expression};"
        assert run_output(source) == run_treewalk_output(source)
