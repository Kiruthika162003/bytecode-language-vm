"""The token: a scanned lexeme paired with its kind, its text, and where it sits.

A token is the unit the parser consumes, and it needs to carry four
things at once. The kind says what grammatical role the lexeme can play,
the lexeme is the exact source text so an error can quote it and an
identifier can be looked up by name, the literal is the already-decoded
value for the kinds that have one so the parser need not re-parse a
number or unescape a string, and the span says where the lexeme sits so
an error can point at it. Bundling all four into one immutable value
means the parser passes a single object rather than four parallel
lists, and freezing it means a token cannot be mutated out from under
the parser after it has been produced. The one subtlety is the literal:
most kinds have none, so it defaults to nothing, and only a number,
string, or boolean carries a decoded value; storing the literal here
rather than recomputing it keeps the decode logic in the scanner, which
is the only stage that has the raw text and the rules for reading it.
This module defines that value and a compact representation for
debugging that shows the kind and lexeme without the noisy span.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ember.sourcepos import Span
from ember.tokenkind import TokenKind


@dataclass(frozen=True)
class Token:
    kind: TokenKind
    lexeme: str
    span: Span
    literal: Any = None

    def __repr__(self) -> str:
        if self.literal is not None:
            return f"Token({self.kind.name}, {self.lexeme!r}, literal={self.literal!r})"
        return f"Token({self.kind.name}, {self.lexeme!r})"

    @property
    def line(self) -> int:
        return self.span.start.line
