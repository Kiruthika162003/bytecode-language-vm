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


class TestRuns:
    def test_the_compressed_runs_are_exposed(self):
        table = LineTable()
        table.record(10)
        table.record(10)
        table.record(11)
        assert table.runs == ((10, 2), (11, 1))

    def test_a_table_rebuilt_from_runs_answers_the_same(self):
        original = LineTable()
        for line in (5, 5, 5, 6, 9, 9):
            original.record(line)
        rebuilt = LineTable.from_runs(list(original.runs))
        assert rebuilt.length == original.length
        assert [rebuilt.line_at(i) for i in range(rebuilt.length)] == [
            original.line_at(i) for i in range(original.length)
        ]

    def test_the_exposed_runs_cannot_mutate_the_table(self):
        table = LineTable()
        table.record(1)
        runs = table.runs
        assert isinstance(runs, tuple)
        assert isinstance(runs[0], tuple)


class TestRefusals:
    def test_a_line_below_one_is_refused(self):
        table = LineTable()
        with pytest.raises(EmberError):
            table.record(0)

    def test_rebuilding_from_a_bad_line_is_refused(self):
        with pytest.raises(EmberError):
            LineTable.from_runs([(0, 1)])

    def test_rebuilding_from_an_empty_run_is_refused(self):
        with pytest.raises(EmberError):
            LineTable.from_runs([(1, 0)])
