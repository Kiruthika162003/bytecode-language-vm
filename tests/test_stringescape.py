from __future__ import annotations

import pytest

from ember.errors import Syntax
from ember.stringescape import decode


class TestSimpleEscapes:
    def test_a_body_with_no_escapes_is_unchanged(self):
        assert decode("hello world") == "hello world"

    def test_newline_and_tab(self):
        assert decode(r"a\nb\tc") == "a\nb\tc"

    def test_escaped_quote_and_backslash(self):
        assert decode(r"say \"hi\" \\ done") == 'say "hi" \\ done'

    def test_a_null_escape(self):
        assert decode(r"\0") == "\0"


class TestHexEscapes:
    def test_a_two_digit_hex_escape(self):
        assert decode(r"\x41\x42") == "AB"

    def test_a_four_digit_unicode_escape(self):
        # build the backslash with chr(92) so the escape is not pre-decoded
        assert decode(chr(92) + "u0042") == "B"
        assert decode(chr(92) + "u00e9") == "é"


class TestRefusals:
    def test_a_lone_trailing_backslash_is_refused(self):
        with pytest.raises(Syntax):
            decode("\\")

    def test_an_unknown_escape_is_refused(self):
        with pytest.raises(Syntax):
            decode(r"\q")

    def test_a_short_hex_escape_is_refused(self):
        with pytest.raises(Syntax):
            decode(r"\x1")

    def test_a_non_hex_unicode_escape_is_refused(self):
        with pytest.raises(Syntax):
            decode(r"\uZZZZ")
