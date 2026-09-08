"""Interpolation: split a string body into the literal runs and the expressions between them.

Writing a value into a sentence by hand means breaking the sentence into pieces
and joining them with plus signs, which puts the punctuation of the concatenation
in the way of reading the sentence. Interpolation lets the value sit where it
belongs, and the work of supporting it divides cleanly in two: deciding where the
holes are, which is a scanning problem and lives here, and turning what is inside
each hole into an expression, which is a parsing problem and does not. So this
module answers only the first question. It walks a string body and returns an
alternating sequence of literal text and expression source, leaving the source
untouched for the parser to handle later. The part that needs care is finding the
end of a hole. A closing brace cannot simply be the next one, because the
expression inside may contain braces of its own, most obviously a map literal, so
the scan counts depth and stops at the brace that returns it to zero. A quote
inside the expression is tracked too, so a brace inside a nested string is not
mistaken for structure. The deliberate limitation is that this module does not
validate what it hands back: an expression that is malformed, or empty, is
reported as such by the parser when it tries to read it, because that is where the
grammar lives and duplicating a judgement about syntax here would let the two
drift apart.
"""

from __future__ import annotations

from ember.errors import Syntax

TEXT = "text"
EXPRESSION = "expression"

_OPEN = "${"


def _find_close(body: str, start: int) -> int:
    """Find the brace that closes a hole opened at start, counting nesting."""
    depth = 1
    index = start
    quote: str | None = None
    while index < len(body):
        char = body[index]
        if quote is not None:
            if char == chr(92):
                index += 2
                continue
            if char == quote:
                quote = None
            index += 1
            continue
        if char in ('"', "'"):
            quote = char
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index
        index += 1
    raise Syntax(
        "an interpolation was opened with ${ but never closed; add a matching }",
        at_end=True,
    )


def split(body: str) -> list[tuple[str, str]]:
    """Split a string body into (kind, text) parts, alternating text and expressions."""
    parts: list[tuple[str, str]] = []
    literal: list[str] = []
    index = 0
    length = len(body)
    while index < length:
        if body[index] == chr(92) and index + 1 < length:
            # an escape is copied through untouched, so a backslash-dollar stays
            # an escape for the unescaping stage rather than opening a hole here
            literal.append(body[index : index + 2])
            index += 2
            continue
        if body.startswith(_OPEN, index):
            end = _find_close(body, index + 2)
            if literal:
                parts.append((TEXT, "".join(literal)))
                literal = []
            parts.append((EXPRESSION, body[index + 2 : end]))
            index = end + 1
            continue
        literal.append(body[index])
        index += 1
    if literal:
        parts.append((TEXT, "".join(literal)))
    return parts


def has_holes(body: str) -> bool:
    """Say whether a string body contains any interpolation at all."""
    index = 0
    while index < len(body):
        if body[index] == chr(92):
            index += 2
            continue
        if body.startswith(_OPEN, index):
            return True
        index += 1
    return False
