from __future__ import annotations

from ember.precedence import Precedence, infix_precedence, is_infix
from ember.tokenkind import TokenKind


class TestLadder:
    def test_the_levels_are_ordered(self):
        assert Precedence.TERM < Precedence.FACTOR
        assert Precedence.OR < Precedence.AND
        assert Precedence.COMPARISON < Precedence.TERM

    def test_factor_binds_tighter_than_term(self):
        assert infix_precedence(TokenKind.STAR) > infix_precedence(TokenKind.PLUS)

    def test_comparison_binds_tighter_than_equality(self):
        assert infix_precedence(TokenKind.LESS) > infix_precedence(TokenKind.EQUAL_EQUAL)


class TestLookup:
    def test_a_known_infix_operator_has_a_level(self):
        assert infix_precedence(TokenKind.PLUS) == Precedence.TERM
        assert is_infix(TokenKind.PLUS)

    def test_a_non_operator_has_no_level(self):
        assert infix_precedence(TokenKind.NUMBER) == Precedence.NONE
        assert not is_infix(TokenKind.NUMBER)

    def test_a_call_paren_binds_at_call_level(self):
        assert infix_precedence(TokenKind.LEFT_PAREN) == Precedence.CALL
