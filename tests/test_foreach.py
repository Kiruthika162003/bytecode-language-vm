from __future__ import annotations

import pytest

from ember.errors import Syntax, TypeMismatch, Unbound
from ember.interpreter import run, run_output, run_treewalk_output
from ember.valueops import iteration_source

SHARED = [
    "for (x in [1, 2, 3]) print x;",
    'for (c in "abc") print c;',
    'for (k in {"a": 1, "b": 2}) print k;',
    'let m = {"a": 1, "b": 2}; for (k in m) print k + "=" + str(m[k]);',
    "let t = 0; for (x in [1, 2, 3, 4]) t = t + x; print t;",
    "for (x in [1, 2, 3, 4, 5]) { if (x == 3) break; print x; }",
    "for (x in [1, 2, 3, 4]) { if (x % 2 == 0) continue; print x; }",
    'for (x in []) print x; print "empty done";',
    "for (a in [1, 2]) for (b in [10, 20]) print a * b;",
    "for (x in [1, 2]) { let d = x * 10; print d; }",
    "fn dbl(n) { return n * 2; } for (x in map([1, 2, 3], dbl)) print x;",
    "let fs = []; for (x in [1, 2, 3]) { fn f() { return x; } push(fs, f); }"
    " for (g in fs) print g();",
]


class TestIterationSource:
    def test_a_list_iterates_over_its_elements(self):
        assert iteration_source([1, 2]) == [1, 2]

    def test_a_string_iterates_over_its_characters(self):
        assert iteration_source("ab") == ["a", "b"]

    def test_a_map_iterates_over_its_keys(self):
        assert iteration_source({"a": 1, "b": 2}) == ["a", "b"]

    def test_a_number_is_not_iterable(self):
        with pytest.raises(TypeMismatch):
            iteration_source(5)


class TestBasicIteration:
    def test_it_visits_each_element(self):
        assert run_output("for (x in [1, 2, 3]) print x;") == ["1", "2", "3"]

    def test_it_walks_a_string_by_character(self):
        assert run_output('for (c in "abc") print c;') == ["a", "b", "c"]

    def test_it_walks_a_map_by_key(self):
        assert run_output('for (k in {"a": 1, "b": 2}) print k;') == ["a", "b"]

    def test_a_key_can_fetch_its_value(self):
        source = 'let m = {"x": 9}; for (k in m) print m[k];'
        assert run_output(source) == ["9"]

    def test_an_empty_collection_runs_the_body_never(self):
        assert run_output('for (x in []) print "never"; print "done";') == ["done"]

    def test_it_accumulates_across_iterations(self):
        assert run_output("let t = 0; for (x in [1, 2, 3, 4]) t = t + x; print t;") == ["10"]


class TestEvaluationOfTheCollection:
    def test_the_collection_expression_runs_once(self):
        # if it were evaluated per iteration, "called" would print repeatedly
        source = 'fn once() { print "called"; return [1, 2]; } for (x in once()) print x;'
        assert run_output(source) == ["called", "1", "2"]


class TestLoopJumps:
    def test_break_leaves_the_iteration(self):
        assert run_output("for (x in [1, 2, 3, 4]) { if (x == 3) break; print x; }") == [
            "1",
            "2",
        ]

    def test_continue_skips_to_the_next_element(self):
        assert run_output("for (x in [1, 2, 3, 4]) { if (x % 2 == 0) continue; print x; }") == [
            "1",
            "3",
        ]

    def test_break_only_leaves_the_inner_iteration(self):
        source = (
            "for (a in [1, 2])"
            " { for (b in [10, 20]) { if (b == 20) break; print a * b; } }"
        )
        assert run_output(source) == ["10", "20"]


class TestScoping:
    def test_a_closure_captures_the_value_of_its_own_iteration(self):
        # each iteration gets a fresh binding, so the three closures differ
        source = (
            "let fs = []; for (x in [1, 2, 3]) { fn f() { return x; } push(fs, f); }"
            " for (g in fs) print g();"
        )
        assert run_output(source) == ["1", "2", "3"]

    def test_the_loop_variable_does_not_escape(self):
        # the name is a local of the loop, so afterwards it is not a global
        with pytest.raises(Unbound):
            run("for (x in [1]) print x; print x;")

    def test_a_body_local_is_discarded_each_iteration(self):
        assert run_output("for (x in [1, 2]) { let d = x * 10; print d; }") == ["10", "20"]


class TestErrors:
    def test_iterating_a_number_is_refused(self):
        with pytest.raises(TypeMismatch):
            run("for (x in 5) print x;")

    def test_iterating_nil_is_refused(self):
        with pytest.raises(TypeMismatch):
            run("for (x in nil) print x;")

    def test_a_missing_in_keyword_falls_back_to_the_counting_form(self):
        # without `in`, this parses as the three-clause loop and is malformed
        with pytest.raises(Syntax):
            run("for (x [1]) print x;")


class TestBothBackendsAgree:
    @pytest.mark.parametrize("source", SHARED)
    def test_agreement(self, source: str):
        assert run_output(source) == run_treewalk_output(source)

    @pytest.mark.parametrize("source", SHARED)
    def test_agreement_when_optimized(self, source: str):
        assert run_output(source, optimize=True) == run_treewalk_output(source, optimize=True)
