"""Operator precedence: the numeric ladder saying how tightly each operator binds.

The heart of parsing expressions is deciding, when two operators compete
for the same operand, which one takes it. Multiplication takes its
operands before addition does, so times binds tighter than plus, and the
whole of this knowledge can be captured as a ladder of numbers where a
higher rung binds tighter. A Pratt parser reads that ladder directly:
it parses an operand, then keeps absorbing following operators as long as
they bind at least as tightly as the level it was asked to parse,
recursing to gather the right-hand side of each. This module holds the
ladder as an ordered enumeration of precedence levels and a table
mapping each infix operator's token kind to its level. Naming the levels
rather than scattering bare integers through the parser keeps the
relationships legible: one can see at a glance that comparison sits below
term, which sits below factor. The single genuine subtlety the ladder
alone cannot express is associativity, whether a minus b minus c groups
to the left or the right. This ladder is consulted with a small rule in
the parser, parse the right side at one level higher for
left-associative operators, which is where associativity actually lives;
the table here stays a pure statement of binding strength so that the two
concerns do not tangle.
"""

from __future__ import annotations

from enum import IntEnum

from ember.tokenkind import TokenKind


class Precedence(IntEnum):
    NONE = 0
    ASSIGNMENT = 1
    CONDITIONAL = 2
    OR = 3
    AND = 4
    BIT_OR = 5
    BIT_XOR = 6
    BIT_AND = 7
    EQUALITY = 8
    COMPARISON = 9
    SHIFT = 10
    TERM = 11
    FACTOR = 12
    UNARY = 13
    CALL = 14
    PRIMARY = 15


_INFIX: dict[TokenKind, Precedence] = {
    TokenKind.OR: Precedence.OR,
    TokenKind.AND: Precedence.AND,
    TokenKind.EQUAL_EQUAL: Precedence.EQUALITY,
    TokenKind.BANG_EQUAL: Precedence.EQUALITY,
    TokenKind.LESS: Precedence.COMPARISON,
    TokenKind.LESS_EQUAL: Precedence.COMPARISON,
    TokenKind.GREATER: Precedence.COMPARISON,
    TokenKind.GREATER_EQUAL: Precedence.COMPARISON,
    TokenKind.PIPE: Precedence.BIT_OR,
    TokenKind.CARET: Precedence.BIT_XOR,
    TokenKind.AMPERSAND: Precedence.BIT_AND,
    TokenKind.LESS_LESS: Precedence.SHIFT,
    TokenKind.GREATER_GREATER: Precedence.SHIFT,
    TokenKind.PLUS: Precedence.TERM,
    TokenKind.MINUS: Precedence.TERM,
    TokenKind.STAR: Precedence.FACTOR,
    TokenKind.SLASH: Precedence.FACTOR,
    TokenKind.PERCENT: Precedence.FACTOR,
    TokenKind.LEFT_PAREN: Precedence.CALL,
    TokenKind.LEFT_BRACKET: Precedence.CALL,
    TokenKind.DOT: Precedence.CALL,
}


def infix_precedence(kind: TokenKind) -> Precedence:
    return _INFIX.get(kind, Precedence.NONE)


def is_infix(kind: TokenKind) -> bool:
    return kind in _INFIX
