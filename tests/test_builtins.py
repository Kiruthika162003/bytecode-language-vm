from __future__ import annotations

import pytest

from ember.errors import Arithmetic, IndexRange, TypeMismatch
from ember.interpreter import run, run_output


class TestMeasurement:
    def test_len_of_a_string_list_and_map(self):
        assert run_output('print len("hello");') == ["5"]
        assert run_output("print len([1, 2, 3]);") == ["3"]
        assert run_output('print len({"a": 1});') == ["1"]


class TestConversion:
    def test_int_and_float_and_str(self):
        assert run_output('print int("42");') == ["42"]
        assert run_output("print float(3);") == ["3.0"]
        assert run_output("print str(3.5);") == ["3.5"]

    def test_type_reports_the_language_type(self):
        assert run_output("print type([1]);") == ["list"]
        assert run_output('print type("s");') == ["string"]


class TestMath:
    def test_abs_sqrt_floor_ceil(self):
        assert run_output("print abs(-5);") == ["5"]
        assert run_output("print sqrt(16);") == ["4.0"]
        assert run_output("print floor(3.7);") == ["3"]
        assert run_output("print ceil(3.2);") == ["4"]

    def test_min_and_max_over_a_list(self):
        assert run_output("print min([3, 1, 2]);") == ["1"]
        assert run_output("print max([3, 1, 2]);") == ["3"]


class TestListAndMap:
    def test_push_and_pop_mutate_a_list(self):
        assert run_output("let a = [1]; push(a, 2); print a; print pop(a);") == [
            "[1, 2]",
            "2",
        ]

    def test_keys_values_and_contains(self):
        assert run_output('let m = {"x": 1}; print keys(m); print contains(m, "x");') == [
            '["x"]',
            "true",
        ]

    def test_range_builds_a_list(self):
        assert run_output("print range(4);") == ["[0, 1, 2, 3]"]


class TestBuiltinErrors:
    def test_len_of_a_number_is_refused(self):
        with pytest.raises(TypeMismatch):
            run("print len(5);")

    def test_sqrt_of_a_negative_is_refused(self):
        with pytest.raises(Arithmetic):
            run("print sqrt(-1);")

    def test_min_of_an_empty_list_is_refused(self):
        with pytest.raises(IndexRange):
            run("print min([]);")


class TestShadowing:
    def test_a_program_can_shadow_a_builtin(self):
        # builtins are ordinary global values, so a program may redefine one
        assert run_output("fn len(x) { return 99; } print len([1, 2, 3]);") == ["99"]
