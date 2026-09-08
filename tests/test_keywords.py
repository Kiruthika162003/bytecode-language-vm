from __future__ import annotations

from ember.keywords import KEYWORDS, is_keyword, kind_of
from ember.tokenkind import TokenKind


class TestKindOf:
    def test_a_reserved_word_becomes_its_kind(self):
        assert kind_of("while") == TokenKind.WHILE
        assert kind_of("fn") == TokenKind.FN
        assert kind_of("return") == TokenKind.RETURN

    def test_an_ordinary_name_stays_an_identifier(self):
        assert kind_of("counter") == TokenKind.IDENTIFIER
        assert kind_of("whileloop") == TokenKind.IDENTIFIER

    def test_the_lookup_is_case_sensitive(self):
        assert kind_of("While") == TokenKind.IDENTIFIER


class TestIsKeyword:
    def test_a_reserved_word_is_a_keyword(self):
        assert is_keyword("const")

    def test_a_name_is_not_a_keyword(self):
        assert not is_keyword("const_value")


class TestTable:
    def test_every_entry_maps_to_a_keyword_kind(self):
        for text, kind in KEYWORDS.items():
            assert kind.is_keyword, text
