from __future__ import annotations

from ember.cursor import Cursor


class TestReading:
    def test_peek_does_not_consume(self):
        cursor = Cursor("abc")
        assert cursor.peek() == "a"
        assert cursor.peek() == "a"

    def test_peek_ahead_looks_further(self):
        cursor = Cursor("abc")
        assert cursor.peek(1) == "b"
        assert cursor.peek(2) == "c"

    def test_advance_consumes_and_returns(self):
        cursor = Cursor("ab")
        assert cursor.advance() == "a"
        assert cursor.advance() == "b"
        assert cursor.at_end()

    def test_peek_past_the_end_is_empty(self):
        cursor = Cursor("a")
        assert cursor.peek(5) == ""

    def test_advance_past_the_end_is_empty(self):
        cursor = Cursor("")
        assert cursor.advance() == ""


class TestMatch:
    def test_match_consumes_on_a_hit(self):
        cursor = Cursor("=+")
        assert cursor.match("=")
        assert cursor.peek() == "+"

    def test_match_leaves_the_cursor_on_a_miss(self):
        cursor = Cursor("=+")
        assert not cursor.match("!")
        assert cursor.peek() == "="


class TestPositionTracking:
    def test_the_column_advances_within_a_line(self):
        cursor = Cursor("abc")
        cursor.advance()
        cursor.advance()
        pos = cursor.position()
        assert pos.line == 1
        assert pos.column == 3

    def test_a_newline_resets_the_column_and_bumps_the_line(self):
        cursor = Cursor("a\nb")
        cursor.advance()  # a
        cursor.advance()  # newline
        pos = cursor.position()
        assert pos.line == 2
        assert pos.column == 1

    def test_the_offset_tracks_characters_consumed(self):
        cursor = Cursor("hello")
        cursor.advance()
        cursor.advance()
        assert cursor.offset == 2
