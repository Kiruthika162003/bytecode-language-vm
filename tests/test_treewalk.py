from __future__ import annotations

import pytest

from ember.errors import Arithmetic, Arity, Immutable, TypeMismatch, Unbound
from ember.interpreter import run_treewalk, run_treewalk_output


class TestBasics:
    def test_arithmetic_and_precedence(self):
        assert run_treewalk_output("print 1 + 2 * 3;") == ["7"]

    def test_control_flow(self):
        source = "let s = 0; for (let i = 1; i <= 5; i = i + 1) s = s + i; print s;"
        assert run_treewalk_output(source) == ["15"]

    def test_recursion(self):
        source = "fn fib(n) { if (n < 2) return n; return fib(n-1) + fib(n-2); } print fib(10);"
        assert run_treewalk_output(source) == ["55"]

    def test_builtins_are_available(self):
        assert run_treewalk_output('print len("hello");') == ["5"]


class TestClosures:
    def test_a_closure_captures_an_enclosing_local(self):
        source = (
            "fn make() { let c = 0; fn inc() { c = c + 1; return c; } return inc; }"
            " let f = make(); print f(); print f(); print f();"
        )
        assert run_treewalk_output(source) == ["1", "2", "3"]

    def test_two_closures_have_independent_state(self):
        source = (
            "fn make() { let c = 0; fn inc() { c = c + 1; return c; } return inc; }"
            " let a = make(); let b = make(); print a(); print a(); print b();"
        )
        assert run_treewalk_output(source) == ["1", "2", "1"]


class TestErrors:
    def test_division_by_zero(self):
        with pytest.raises(Arithmetic):
            run_treewalk("print 1 / 0;")

    def test_unbound_name(self):
        with pytest.raises(Unbound):
            run_treewalk("print missing;")

    def test_wrong_arity(self):
        with pytest.raises(Arity):
            run_treewalk("fn f(x) { return x; } f();")

    def test_const_reassignment(self):
        with pytest.raises(Immutable):
            run_treewalk("const k = 1; k = 2;")

    def test_type_mismatch(self):
        with pytest.raises(TypeMismatch):
            run_treewalk('print 1 + "a";')


class TestInstrumentation:
    def test_it_counts_steps(self):
        walker = run_treewalk("print 1 + 2;")
        assert walker.steps > 0
