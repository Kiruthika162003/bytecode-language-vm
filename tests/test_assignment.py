from __future__ import annotations

import pytest

from ember.errors import IndexRange, TypeMismatch
from ember.interpreter import run, run_output


class TestIndexAssignment:
    def test_assigning_into_a_list(self):
        assert run_output("let a = [1, 2, 3]; a[1] = 99; print a;") == ["[1, 99, 3]"]

    def test_assigning_a_new_map_key(self):
        assert run_output('let m = {"x": 1}; m["y"] = 2; print m["y"];') == ["2"]

    def test_index_assignment_yields_the_value(self):
        assert run_output("let a = [0]; print (a[0] = 7);") == ["7"]

    def test_a_negative_index_assigns_from_the_end(self):
        assert run_output("let a = [1, 2, 3]; a[-1] = 9; print a;") == ["[1, 2, 9]"]


class TestCompoundAssignment:
    def test_each_compound_operator_on_a_variable(self):
        source = (
            "let x = 10; x += 5; print x; x -= 3; print x;"
            " x *= 2; print x; x /= 4; print x; x %= 2; print x;"
        )
        assert run_output(source) == ["15", "12", "24", "6.0", "0.0"]

    def test_compound_on_a_list_element(self):
        assert run_output("let a = [10, 20]; a[0] += 5; a[1] *= 2; print a;") == [
            "[15, 40]"
        ]

    def test_compound_string_concatenation(self):
        assert run_output('let s = "a"; s += "b"; s += "c"; print s;') == ["abc"]


class TestAssignmentErrors:
    def test_assigning_into_a_string_is_refused(self):
        with pytest.raises(TypeMismatch):
            run('let s = "abc"; s[0] = "z";')

    def test_assigning_out_of_range_is_refused(self):
        with pytest.raises(IndexRange):
            run("let a = [1]; a[5] = 2;")

    def test_a_list_cannot_be_a_map_key(self):
        with pytest.raises(TypeMismatch):
            run("let m = {}; m[[1]] = 2;")
