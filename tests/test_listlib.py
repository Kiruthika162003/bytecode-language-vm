from __future__ import annotations

import pytest

from ember.errors import IndexRange, TypeMismatch
from ember.interpreter import run, run_output


class TestReading:
    def test_first_and_last(self):
        assert run_output("print first([1, 2, 3]);") == ["1"]
        assert run_output("print last([1, 2, 3]);") == ["3"]

    def test_sum(self):
        assert run_output("print sum([1, 2, 3, 4]);") == ["10"]

    def test_index_of_and_count(self):
        assert run_output("print list_index_of([5, 6, 7], 6);") == ["1"]
        assert run_output("print count([1, 1, 2, 1], 1);") == ["3"]


class TestTransforming:
    def test_slice_returns_a_new_list(self):
        assert run_output("let a = [1, 2, 3, 4]; print slice(a, 1, 3); print a;") == [
            "[2, 3]",
            "[1, 2, 3, 4]",
        ]

    def test_reversed_does_not_mutate(self):
        assert run_output("let a = [1, 2, 3]; print reversed(a); print a;") == [
            "[3, 2, 1]",
            "[1, 2, 3]",
        ]

    def test_sorted_orders_numbers(self):
        assert run_output("print sorted([3, 1, 2]);") == ["[1, 2, 3]"]

    def test_unique_drops_duplicates_keeping_order(self):
        assert run_output("print unique([1, 1, 2, 3, 3, 1]);") == ["[1, 2, 3]"]

    def test_concat(self):
        assert run_output("print concat([1, 2], [3, 4]);") == ["[1, 2, 3, 4]"]


class TestErrors:
    def test_first_of_empty_is_refused(self):
        with pytest.raises(IndexRange):
            run("print first([]);")

    def test_sorted_needs_numbers(self):
        with pytest.raises(TypeMismatch):
            run('print sorted(["a", "b"]);')

    def test_reversed_needs_a_list(self):
        with pytest.raises(TypeMismatch):
            run("print reversed(5);")
