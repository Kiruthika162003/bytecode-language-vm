from __future__ import annotations

import pytest

from ember.errors import (
    Arithmetic,
    Arity,
    Immutable,
    IndexRange,
    StackFault,
    TypeMismatch,
    Unbound,
)
from ember.interpreter import run, run_output


class TestArithmetic:
    def test_precedence_is_respected(self):
        assert run_output("print 1 + 2 * 3;") == ["7"]

    def test_division_produces_a_float(self):
        assert run_output("print 10 / 4;") == ["2.5"]

    def test_modulo(self):
        assert run_output("print 17 % 5;") == ["2"]

    def test_unary_negation(self):
        assert run_output("print -(3 + 4);") == ["-7"]


class TestControlFlow:
    def test_if_takes_the_true_branch(self):
        assert run_output('if (1 < 2) print "a"; else print "b";') == ["a"]

    def test_if_takes_the_false_branch(self):
        assert run_output('if (1 > 2) print "a"; else print "b";') == ["b"]

    def test_while_loops(self):
        assert run_output("let n = 3; while (n > 0) { print n; n = n - 1; }") == [
            "3",
            "2",
            "1",
        ]

    def test_for_accumulates(self):
        source = "let s = 0; for (let i = 1; i <= 5; i = i + 1) s = s + i; print s;"
        assert run_output(source) == ["15"]

    def test_logical_and_short_circuits(self):
        assert run_output('print false and "x";') == ["false"]

    def test_logical_or_short_circuits(self):
        assert run_output('print true or "x";') == ["true"]


class TestScopes:
    def test_a_block_local_shadows_a_global(self):
        assert run_output("let x = 1; { let x = 2; print x; } print x;") == ["2", "1"]


class TestFunctions:
    def test_a_function_returns_a_value(self):
        assert run_output("fn add(a, b) { return a + b; } print add(2, 3);") == ["5"]

    def test_recursion_computes_fibonacci(self):
        source = "fn fib(n) { if (n < 2) return n; return fib(n-1) + fib(n-2); } print fib(10);"
        assert run_output(source) == ["55"]

    def test_a_function_with_no_return_yields_nil(self):
        assert run_output("fn f() { } print f();") == ["nil"]


class TestCollections:
    def test_list_indexing(self):
        assert run_output("let a = [10, 20, 30]; print a[1];") == ["20"]

    def test_negative_indexing(self):
        assert run_output("let a = [10, 20, 30]; print a[-1];") == ["30"]

    def test_map_lookup(self):
        assert run_output('let m = {"k": 99}; print m["k"];') == ["99"]

    def test_string_concatenation(self):
        assert run_output('print "foo" + "bar";') == ["foobar"]


class TestInstrumentation:
    def test_it_counts_instructions_and_tracks_the_stack(self):
        machine = run("print 1 + 2;")
        assert machine.instruction_count > 0
        assert machine.max_stack >= 2


class TestRuntimeErrors:
    def test_division_by_zero(self):
        with pytest.raises(Arithmetic):
            run("print 1 / 0;")

    def test_adding_mismatched_types(self):
        with pytest.raises(TypeMismatch):
            run('print 1 + "a";')

    def test_reading_an_undefined_global(self):
        with pytest.raises(Unbound):
            run("print missing;")

    def test_indexing_out_of_range(self):
        with pytest.raises(IndexRange):
            run("let a = [1]; print a[9];")

    def test_calling_with_the_wrong_arity(self):
        with pytest.raises(Arity):
            run("fn f(x) { return x; } print f();")

    def test_assigning_to_a_const(self):
        with pytest.raises(Immutable):
            run("const k = 1; k = 2;")

    def test_calling_a_non_function(self):
        with pytest.raises(TypeMismatch):
            run("let x = 5; x();")

    def test_runaway_recursion_is_capped(self):
        with pytest.raises(StackFault):
            run("fn f() { return f(); } f();")
