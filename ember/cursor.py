"""The character cursor: read source left to right while keeping line and column current.

Scanning is almost entirely a matter of looking at the current
character, deciding what to do, and moving on, and doing that while
keeping an accurate line and column is fiddly enough that it is worth
isolating from the logic that decides what tokens mean. This module is
that isolation. A Cursor holds the source and a position, and offers the
small vocabulary a scanner actually uses: peek at the current character
without consuming it, peek one further ahead to distinguish a
one-character operator from a two-character one, advance past the
current character, and conditionally advance only if the current
character matches an expected one. The single subtle responsibility it
carries is line and column bookkeeping: advancing past a newline resets
the column and increments the line, and advancing past anything else
moves the column on, so the position a scanner reads from the cursor is
always right without the scanner ever counting newlines itself. The
honest limitation is that the cursor works in terms of Python string
indices, which are code points, so a column is a count of code points
and not of grapheme clusters or display width; a tool that needed to
place a caret under a wide character would have to widen this notion of
column, which this module leaves out to stay simple and fast for the
common case of ASCII-heavy source.
"""

from __future__ import annotations

from ember.sourcepos import Position


class Cursor:
    def __init__(self, source: str) -> None:
        self._source = source
        self._offset = 0
        self._line = 1
        self._column = 1

    @property
    def source(self) -> str:
        return self._source

    @property
    def offset(self) -> int:
        return self._offset

    def at_end(self) -> bool:
        return self._offset >= len(self._source)

    def position(self) -> Position:
        line = self._line
        column = self._column
        if self._offset >= len(self._source):
            # clamp a past-the-end position to the last real column so it
            # stays a valid Position that still points near the trouble
            line = max(line, 1)
            column = max(column, 1)
        return Position(self._offset, line, column)

    def peek(self, ahead: int = 0) -> str:
        index = self._offset + ahead
        if index < 0 or index >= len(self._source):
            return ""
        return self._source[index]

    def advance(self) -> str:
        if self.at_end():
            return ""
        char = self._source[self._offset]
        self._offset += 1
        if char == "\n":
            self._line += 1
            self._column = 1
        else:
            self._column += 1
        return char

    def match(self, expected: str) -> bool:
        if self.peek() != expected:
            return False
        self.advance()
        return True
