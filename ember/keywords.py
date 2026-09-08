"""The keyword table: which identifiers are reserved words, and which kind each becomes.

A scanner cannot tell a keyword from a variable name by shape alone,
because both are runs of letters. The standard resolution, and the one
here, is to scan every such run as though it were an identifier and then
consult a table: if the text is a reserved word the token is promoted to
that word's kind, and otherwise it stays a plain identifier. Doing the
lookup once, after the run is complete, is both simpler and faster than
trying to recognize keywords character by character while scanning, and
it keeps the rule for what counts as an identifier in one place. This
module holds that table and the single function that applies it. The
design choice worth naming is that the set of keywords is fixed and
closed: a program cannot introduce a new keyword, so a name like a
function or variable can never collide with future syntax by accident,
at the cost that adding a language feature which needs a new keyword can
break existing programs that used the word as a name. The table maps the
reserved text directly to its TokenKind so the promotion is a single
dictionary lookup.
"""

from __future__ import annotations

from ember.tokenkind import TokenKind

KEYWORDS: dict[str, TokenKind] = {
    "and": TokenKind.AND,
    "or": TokenKind.OR,
    "not": TokenKind.NOT,
    "if": TokenKind.IF,
    "else": TokenKind.ELSE,
    "while": TokenKind.WHILE,
    "for": TokenKind.FOR,
    "fn": TokenKind.FN,
    "return": TokenKind.RETURN,
    "let": TokenKind.LET,
    "const": TokenKind.CONST,
    "class": TokenKind.CLASS,
    "this": TokenKind.THIS,
    "true": TokenKind.TRUE,
    "false": TokenKind.FALSE,
    "nil": TokenKind.NIL,
    "print": TokenKind.PRINT,
}


def kind_of(text: str) -> TokenKind:
    return KEYWORDS.get(text, TokenKind.IDENTIFIER)


def is_keyword(text: str) -> bool:
    return text in KEYWORDS
