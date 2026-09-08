from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from ember.errors import EmberError
from ember.sourcepos import Position, Span


class TestPosition:
    def test_it_holds_offset_line_and_column(self):
        pos = Position(offset=10, line=2, column=4)
        assert (pos.offset, pos.line, pos.column) == (10, 2, 4)

    def test_a_negative_offset_is_refused(self):
        with pytest.raises(EmberError):
            Position(offset=-1, line=1, column=1)

    def test_a_line_below_one_is_refused(self):
        with pytest.raises(EmberError):
            Position(offset=0, line=0, column=1)

    def test_a_column_below_one_is_refused(self):
        with pytest.raises(EmberError):
            Position(offset=0, line=1, column=0)

    def test_positions_are_frozen(self):
        pos = Position(offset=0, line=1, column=1)
        with pytest.raises(FrozenInstanceError):
            pos.offset = 5  # type: ignore[misc]


class TestSpan:
    def test_length_is_the_offset_difference(self):
        span = Span(Position(3, 1, 4), Position(8, 1, 9))
        assert span.length == 5

    def test_text_slices_the_source(self):
        source = "let x = 42;"
        span = Span(Position(8, 1, 9), Position(10, 1, 11))
        assert span.text(source) == "42"

    def test_an_empty_span_has_zero_length(self):
        span = Span(Position(4, 1, 5), Position(4, 1, 5))
        assert span.length == 0
        assert span.text("abcd") == ""

    def test_an_end_before_the_start_is_refused(self):
        with pytest.raises(EmberError):
            Span(Position(9, 1, 10), Position(2, 1, 3))
