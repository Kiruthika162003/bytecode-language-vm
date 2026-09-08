from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from ember.sourcepos import Position, Span
from ember.token import Token
from ember.tokenkind import TokenKind


def _span(start: int, end: int) -> Span:
    return Span(Position(start, 1, start + 1), Position(end, 1, end + 1))


class TestToken:
    def test_it_carries_kind_lexeme_and_span(self):
        token = Token(TokenKind.PLUS, "+", _span(3, 4))
        assert token.kind == TokenKind.PLUS
        assert token.lexeme == "+"
        assert token.literal is None

    def test_a_literal_token_carries_its_value(self):
        token = Token(TokenKind.NUMBER, "42", _span(0, 2), literal=42)
        assert token.literal == 42

    def test_the_line_comes_from_the_span_start(self):
        span = Span(Position(0, 5, 1), Position(2, 5, 3))
        token = Token(TokenKind.NUMBER, "10", span, literal=10)
        assert token.line == 5

    def test_the_repr_shows_a_literal_when_present(self):
        token = Token(TokenKind.NUMBER, "42", _span(0, 2), literal=42)
        assert "42" in repr(token)
        assert "NUMBER" in repr(token)

    def test_the_repr_omits_a_missing_literal(self):
        token = Token(TokenKind.PLUS, "+", _span(0, 1))
        assert "literal" not in repr(token)

    def test_tokens_are_frozen(self):
        token = Token(TokenKind.PLUS, "+", _span(0, 1))
        with pytest.raises(FrozenInstanceError):
            token.lexeme = "-"  # type: ignore[misc]
