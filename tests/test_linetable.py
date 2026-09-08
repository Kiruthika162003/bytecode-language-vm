from __future__ import annotations

import pytest

from ember.errors import EmberError
from ember.linetable import LineTable


class TestRecording:
    def test_a_single_line_is_one_run(self):
        table = LineTable()
        for _ in range(5):
            table.record(1)
        assert table.length == 5
        assert table.run_count == 1

    def test_changing_lines_starts_a_new_run(self):
        table = LineTable()
        table.record(1)
        table.record(1)
        table.record(2)
        assert table.run_count == 2

    def test_returning_to_a_line_starts_another_run(self):
        table = LineTable()
        table.record(1)
        table.record(2)
        table.record(1)
        assert table.run_count == 3


class TestLookup:
    def test_each_offset_maps_to_its_line(self):
        table = LineTable()
        table.record(10)
        table.record(10)
        table.record(11)
        table.record(20)
        assert table.line_at(0) == 10
        assert table.line_at(1) == 10
        assert table.line_at(2) == 11
        assert table.line_at(3) == 20

    def test_an_offset_past_the_end_is_refused(self):
        table = LineTable()
        table.record(1)
        with pytest.raises(EmberError):
            table.line_at(5)

    def test_a_negative_offset_is_refused(self):
        table = LineTable()
        table.record(1)
        with pytest.raises(EmberError):
            table.line_at(-1)


class TestRefusals:
    def test_a_line_below_one_is_refused(self):
        table = LineTable()
        with pytest.raises(EmberError):
            table.record(0)
