from __future__ import annotations

import pytest

from ember.errors import Syntax
from ember.scanner import scan, scan_recovering
from ember.tokenkind import TokenKind


def kinds(source: str) -> list[TokenKind]:
    return [token.kind for token in scan(source)]


class TestBasics:
    def test_a_stream_always_ends_with_eof(self):
        assert kinds("")[-1] == TokenKind.EOF
        assert kinds("1 + 1")[-1] == TokenKind.EOF

    def test_a_simple_statement(self):
        assert kinds("let x = 42;") == [
            TokenKind.LET,
            TokenKind.IDENTIFIER,
            TokenKind.EQUAL,
            TokenKind.NUMBER,
            TokenKind.SEMICOLON,
            TokenKind.EOF,
        ]

    def test_keywords_are_recognized(self):
        assert kinds("if while fn return")[:4] == [
            TokenKind.IF,
            TokenKind.WHILE,
            TokenKind.FN,
            TokenKind.RETURN,
        ]


class TestOperators:
    def test_two_character_operators(self):
        assert kinds("!= <= >= ==")[:4] == [
            TokenKind.BANG_EQUAL,
            TokenKind.LESS_EQUAL,
            TokenKind.GREATER_EQUAL,
            TokenKind.EQUAL_EQUAL,
        ]

    def test_one_character_operators_when_no_equals_follows(self):
        assert kinds("! < > =")[:4] == [
            TokenKind.BANG,
            TokenKind.LESS,
            TokenKind.GREATER,
            TokenKind.EQUAL,
        ]


class TestLiterals:
    def test_a_string_literal_is_unescaped(self):
        tokens = scan(r'"line\nbreak"')
        assert tokens[0].kind == TokenKind.STRING
        assert tokens[0].literal == "line\nbreak"

    def test_integer_and_float_literals(self):
        tokens = scan("42 3.5")
        assert tokens[0].literal == 42
        assert tokens[1].literal == 3.5


class TestTrivia:
    def test_line_comments_are_skipped(self):
        assert kinds("a // comment\nb") == [
            TokenKind.IDENTIFIER,
            TokenKind.IDENTIFIER,
            TokenKind.EOF,
        ]

    def test_block_comments_are_skipped_across_lines(self):
        assert kinds("a /* x\ny */ b") == [
            TokenKind.IDENTIFIER,
            TokenKind.IDENTIFIER,
            TokenKind.EOF,
        ]

    def test_the_line_advances_across_a_newline(self):
        tokens = scan("a\nb")
        assert tokens[0].line == 1
        assert tokens[1].line == 2


class TestErrors:
    def test_an_unterminated_string_is_refused(self):
        with pytest.raises(Syntax):
            scan('"never closed')

    def test_an_unexpected_character_is_refused(self):
        with pytest.raises(Syntax):
            scan("a @ b")

    def test_an_unclosed_block_comment_is_refused(self):
        with pytest.raises(Syntax):
            scan("/* open")


class TestRecovery:
    def test_recovery_emits_an_error_token_and_continues(self):
        tokens = scan_recovering("a @ b")
        recovered = [token.kind for token in tokens]
        assert TokenKind.ERROR in recovered
        assert recovered[-1] == TokenKind.EOF
        assert recovered.count(TokenKind.IDENTIFIER) == 2
