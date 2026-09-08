"""The token kinds: the closed vocabulary of things the scanner can produce.

Every token the scanner emits is one of a fixed, known set of kinds, and
naming that set explicitly as an enumeration rather than as loose
strings pays off at every later stage. The parser switches on the kind,
and an enumeration lets a mistyped kind fail loudly at import time
rather than silently never matching. The kinds fall into natural groups:
the single-character punctuation, the one- or two-character operators
where a second character changes the meaning, the literals whose value
is carried alongside the kind, the keywords that a bare identifier is
promoted to, and the two synthetic kinds that are never written in
source. Those last two earn their place: an ERROR kind lets the scanner
report a bad character as a token and keep going rather than aborting at
the first mistake, so one run can surface many errors, and an EOF kind
gives the parser a definite thing to stop on instead of testing for the
end of a list on every step. The honest tradeoff of a flat enumeration
is that it does not, by itself, encode which kinds are operators or which
bind tighter; that structure lives in the precedence table and the
parser, kept separate so this vocabulary stays a simple, stable list.
"""

from __future__ import annotations

from enum import Enum, auto


class TokenKind(Enum):
    LEFT_PAREN = auto()
    RIGHT_PAREN = auto()
    LEFT_BRACE = auto()
    RIGHT_BRACE = auto()
    LEFT_BRACKET = auto()
    RIGHT_BRACKET = auto()
    COMMA = auto()
    DOT = auto()
    SEMICOLON = auto()
    COLON = auto()

    PLUS = auto()
    MINUS = auto()
    STAR = auto()
    SLASH = auto()
    PERCENT = auto()

    PLUS_EQUAL = auto()
    MINUS_EQUAL = auto()
    STAR_EQUAL = auto()
    SLASH_EQUAL = auto()
    PERCENT_EQUAL = auto()

    AMPERSAND = auto()
    PIPE = auto()
    CARET = auto()
    TILDE = auto()
    LESS_LESS = auto()
    GREATER_GREATER = auto()
    QUESTION = auto()
    ELLIPSIS = auto()

    BANG = auto()
    BANG_EQUAL = auto()
    EQUAL = auto()
    EQUAL_EQUAL = auto()
    GREATER = auto()
    GREATER_EQUAL = auto()
    LESS = auto()
    LESS_EQUAL = auto()

    IDENTIFIER = auto()
    STRING = auto()
    INTERPOLATION = auto()
    NUMBER = auto()

    AND = auto()
    OR = auto()
    NOT = auto()
    IF = auto()
    ELSE = auto()
    WHILE = auto()
    FOR = auto()
    BREAK = auto()
    CONTINUE = auto()
    IN = auto()
    MATCH = auto()
    CASE = auto()
    DEFAULT = auto()
    TRY = auto()
    CATCH = auto()
    THROW = auto()
    FN = auto()
    RETURN = auto()
    LET = auto()
    CONST = auto()
    CLASS = auto()
    THIS = auto()
    SUPER = auto()
    TRUE = auto()
    FALSE = auto()
    NIL = auto()
    PRINT = auto()

    ERROR = auto()
    EOF = auto()

    @property
    def is_literal(self) -> bool:
        return self in (
            TokenKind.STRING,
            TokenKind.INTERPOLATION,
            TokenKind.NUMBER,
            TokenKind.TRUE,
            TokenKind.FALSE,
            TokenKind.NIL,
        )

    @property
    def is_keyword(self) -> bool:
        return self in _KEYWORD_KINDS


_KEYWORD_KINDS = frozenset(
    {
        TokenKind.AND,
        TokenKind.OR,
        TokenKind.NOT,
        TokenKind.IF,
        TokenKind.ELSE,
        TokenKind.WHILE,
        TokenKind.FOR,
        TokenKind.BREAK,
        TokenKind.CONTINUE,
        TokenKind.IN,
        TokenKind.MATCH,
        TokenKind.CASE,
        TokenKind.DEFAULT,
        TokenKind.TRY,
        TokenKind.CATCH,
        TokenKind.THROW,
        TokenKind.FN,
        TokenKind.RETURN,
        TokenKind.LET,
        TokenKind.CONST,
        TokenKind.CLASS,
        TokenKind.THIS,
        TokenKind.SUPER,
        TokenKind.TRUE,
        TokenKind.FALSE,
        TokenKind.NIL,
        TokenKind.PRINT,
    }
)
