from __future__ import annotations

from ember.tokenkind import TokenKind


class TestTokenKind:
    def test_the_kinds_are_all_distinct(self):
        values = list(TokenKind)
        assert len({k.value for k in values}) == len(values)

    def test_literals_report_themselves(self):
        assert TokenKind.NUMBER.is_literal
        assert TokenKind.STRING.is_literal
        assert TokenKind.TRUE.is_literal
        assert not TokenKind.PLUS.is_literal

    def test_keywords_report_themselves(self):
        assert TokenKind.WHILE.is_keyword
        assert TokenKind.RETURN.is_keyword
        assert not TokenKind.IDENTIFIER.is_keyword
        assert not TokenKind.LEFT_PAREN.is_keyword

    def test_the_synthetic_kinds_exist(self):
        assert TokenKind.EOF in TokenKind
        assert TokenKind.ERROR in TokenKind

    def test_a_boolean_literal_is_both_literal_and_keyword(self):
        assert TokenKind.TRUE.is_literal
        assert TokenKind.TRUE.is_keyword
