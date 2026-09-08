"""Source positions: track where every token came from so errors can point at it.

An error message that says only what went wrong, without saying where,
sends the reader hunting through the file. A runtime that wants to point
at the offending character must therefore carry position information
from the very first stage, the scanner, all the way through to the
error it eventually raises. This module defines the two small values
that carry it: a Position, which is a single point given by its byte
offset into the source together with the human-facing line and column,
and a Span, which is a half-open range between two offsets naming a
whole token or expression. Keeping the raw offset alongside the line and
column is deliberate: the offset is what slicing the source needs to
quote the exact text, while the line and column are what a person reads,
and computing one from the other on demand is more error-prone than
carrying both. The honest cost is that every token grows by a few
integers, which for a scanner that produces one token per few characters
is a real fraction of its memory; a runtime that scanned enormous files
would store offsets only and recover line and column lazily from a line
table, which this module leaves to a later stage for the sake of a
simpler token.
"""

from __future__ import annotations

from dataclasses import dataclass

from ember.errors import EmberError


@dataclass(frozen=True)
class Position:
    offset: int
    line: int
    column: int

    def __post_init__(self) -> None:
        if self.offset < 0:
            raise EmberError(
                f"a source offset cannot be negative, but got {self.offset}"
            )
        if self.line < 1:
            raise EmberError(
                f"source lines are numbered from one, but got line {self.line}"
            )
        if self.column < 1:
            raise EmberError(
                f"source columns are numbered from one, but got column {self.column}"
            )


@dataclass(frozen=True)
class Span:
    start: Position
    end: Position

    def __post_init__(self) -> None:
        if self.end.offset < self.start.offset:
            raise EmberError(
                "a span cannot end before it starts, but the end offset "
                f"{self.end.offset} is before the start offset {self.start.offset}"
            )

    @property
    def length(self) -> int:
        return self.end.offset - self.start.offset

    def text(self, source: str) -> str:
        return source[self.start.offset : self.end.offset]
