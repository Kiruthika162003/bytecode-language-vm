"""The scanner: turn source text into a flat stream of tokens for the parser.

The scanner is the first stage that gives the source any structure. It
walks the text with a cursor, skipping the whitespace and comments that
carry no meaning, and at each remaining character it decides which token
begins there and consumes exactly that token. Punctuation is a single
character, operators are one character or two where a trailing equals
sign changes the meaning, numbers and strings and identifiers are runs
recognized by their first character and extended by a small loop, and an
identifier is promoted to a keyword only after the whole run is read.
Every token it emits records the span it came from, so a later error can
quote and locate it. The design decision worth stating is error
handling. This scanner offers two modes. By default it raises on the
first malformed token, which is what the compilation pipeline wants,
because there is no point parsing text that does not tokenize. In
recovering mode it instead emits an ERROR token for the bad character
and continues, so a tool like an editor can surface many lexical
problems from one pass rather than stopping at the first. The honest
tradeoff is that recovery here is the simplest possible kind, skip the
offending character and carry on, which can produce a cascade of
follow-on errors from a single real mistake; a scanner tuned for editor
use would resynchronize more cleverly, which this module leaves aside.
Both modes always terminate the stream with a single EOF token so the
parser has a definite stopping point.
"""

from __future__ import annotations

from ember.cursor import Cursor
from ember.errors import Syntax
from ember.keywords import kind_of
from ember.numberparse import parse as parse_number
from ember.sourcepos import Position, Span
from ember.stringescape import decode as decode_escapes
from ember.token import Token
from ember.tokenkind import TokenKind

_SINGLE = {
    "(": TokenKind.LEFT_PAREN,
    ")": TokenKind.RIGHT_PAREN,
    "{": TokenKind.LEFT_BRACE,
    "}": TokenKind.RIGHT_BRACE,
    "[": TokenKind.LEFT_BRACKET,
    "]": TokenKind.RIGHT_BRACKET,
    ",": TokenKind.COMMA,
    ".": TokenKind.DOT,
    ";": TokenKind.SEMICOLON,
    ":": TokenKind.COLON,
    "+": TokenKind.PLUS,
    "-": TokenKind.MINUS,
    "*": TokenKind.STAR,
    "%": TokenKind.PERCENT,
}

_MAYBE_EQUAL = {
    "!": (TokenKind.BANG, TokenKind.BANG_EQUAL),
    "=": (TokenKind.EQUAL, TokenKind.EQUAL_EQUAL),
    "<": (TokenKind.LESS, TokenKind.LESS_EQUAL),
    ">": (TokenKind.GREATER, TokenKind.GREATER_EQUAL),
}


def _is_digit(char: str) -> bool:
    return "0" <= char <= "9"


def _is_alpha(char: str) -> bool:
    return char == "_" or char.isalpha()


def _is_alnum(char: str) -> bool:
    return _is_alpha(char) or _is_digit(char)


class Scanner:
    def __init__(self, source: str, recover: bool = False) -> None:
        self._cursor = Cursor(source)
        self._recover = recover

    def scan(self) -> list[Token]:
        tokens: list[Token] = []
        while True:
            self._skip_trivia()
            start = self._cursor.position()
            if self._cursor.at_end():
                tokens.append(Token(TokenKind.EOF, "", Span(start, start)))
                return tokens
            token = self._scan_one(start)
            if token is not None:
                tokens.append(token)

    def _span(self, start: Position) -> Span:
        return Span(start, self._cursor.position())

    def _make(self, kind: TokenKind, start: Position, literal: object = None) -> Token:
        span = self._span(start)
        return Token(kind, span.text(self._cursor.source), span, literal)

    def _error(self, start: Position, message: str) -> Token | None:
        if not self._recover:
            raise Syntax(message)
        span = self._span(start)
        return Token(TokenKind.ERROR, span.text(self._cursor.source), span, message)

    def _skip_trivia(self) -> None:
        while not self._cursor.at_end():
            char = self._cursor.peek()
            if char in " \t\r\n":
                self._cursor.advance()
            elif char == "/" and self._cursor.peek(1) == "/":
                while not self._cursor.at_end() and self._cursor.peek() != "\n":
                    self._cursor.advance()
            elif char == "/" and self._cursor.peek(1) == "*":
                self._skip_block_comment()
            else:
                return

    def _skip_block_comment(self) -> None:
        self._cursor.advance()
        self._cursor.advance()
        while not self._cursor.at_end():
            if self._cursor.peek() == "*" and self._cursor.peek(1) == "/":
                self._cursor.advance()
                self._cursor.advance()
                return
            self._cursor.advance()
        raise Syntax(
            "a block comment was opened with /* but never closed; add a "
            "matching */"
        )

    def _scan_one(self, start: Position) -> Token | None:
        char = self._cursor.advance()
        if char in _SINGLE:
            return self._make(_SINGLE[char], start)
        if char in _MAYBE_EQUAL:
            plain, equal = _MAYBE_EQUAL[char]
            if self._cursor.match("="):
                return self._make(equal, start)
            return self._make(plain, start)
        if char == '"':
            return self._scan_string(start)
        if _is_digit(char):
            return self._scan_number(start)
        if _is_alpha(char):
            return self._scan_identifier(start)
        return self._error(
            start,
            f"unexpected character {char!r}; it does not begin any token",
        )

    def _scan_string(self, start: Position) -> Token | None:
        while not self._cursor.at_end() and self._cursor.peek() != '"':
            if self._cursor.peek() == "\\":
                self._cursor.advance()
            if not self._cursor.at_end():
                self._cursor.advance()
        if self._cursor.at_end():
            return self._error(
                start,
                "a string was opened but never closed; add a closing quote",
            )
        self._cursor.advance()
        raw = self._span(start).text(self._cursor.source)
        body = raw[1:-1]
        value = decode_escapes(body)
        return self._make(TokenKind.STRING, start, value)

    def _scan_number(self, start: Position) -> Token:
        while _is_alnum(self._cursor.peek()) or self._cursor.peek() == ".":
            self._cursor.advance()
        text = self._span(start).text(self._cursor.source)
        value, _ = parse_number(text)
        return self._make(TokenKind.NUMBER, start, value)

    def _scan_identifier(self, start: Position) -> Token:
        while _is_alnum(self._cursor.peek()):
            self._cursor.advance()
        text = self._span(start).text(self._cursor.source)
        return self._make(kind_of(text), start)


def scan(source: str) -> list[Token]:
    return Scanner(source, recover=False).scan()


def scan_recovering(source: str) -> list[Token]:
    return Scanner(source, recover=True).scan()
