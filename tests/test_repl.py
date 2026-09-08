from __future__ import annotations

import pytest

from ember.errors import Arithmetic, Syntax
from ember.repl import Session, is_incomplete


class TestIncompleteInput:
    @pytest.mark.parametrize(
        "source",
        [
            "let x = ",
            "1 +",
            "fn f() {",
            "if (x) {",
            "let a = [1, 2",
            'let s = "unterminated',
            "/* open",
            "print (1",
        ],
    )
    def test_unfinished_input_is_incomplete(self, source: str):
        assert is_incomplete(source)

    @pytest.mark.parametrize(
        "source",
        [
            "1 + 2;",
            "fn f() { return 1; }",
            "",
            "   ",
            "1 + @",
            "}",
            "let x = 1;",
        ],
    )
    def test_finished_or_wrong_input_is_not_incomplete(self, source: str):
        assert not is_incomplete(source)

    def test_a_wrong_input_is_distinguished_from_an_unfinished_one(self):
        # both fail to parse, but only one is waiting for more text
        assert is_incomplete("1 +")
        assert not is_incomplete("1 + @")


class TestPersistence:
    def test_a_function_survives_to_the_next_input(self):
        session = Session()
        session.evaluate("fn dbl(x) { return x * 2; }")
        assert session.evaluate("dbl(21);") == ["42"]

    def test_a_variable_survives_to_the_next_input(self):
        session = Session()
        session.evaluate("let n = 5;")
        assert session.evaluate("n * n;") == ["25"]

    def test_a_class_survives_to_the_next_input(self):
        session = Session()
        session.evaluate("class P { init(x) { this.x = x; } get() { return this.x; } }")
        assert session.evaluate("P(9).get();") == ["9"]

    def test_a_definition_can_be_replaced(self):
        session = Session()
        session.evaluate("let n = 1;")
        session.evaluate("let n = 2;")
        assert session.evaluate("n;") == ["2"]

    def test_builtins_are_available(self):
        assert Session().evaluate('len("hello");') == ["5"]


class TestAutoPrinting:
    def test_a_lone_expression_is_printed(self):
        assert Session().evaluate("1 + 2;") == ["3"]

    def test_a_declaration_prints_nothing(self):
        assert Session().evaluate("let x = 1;") == []

    def test_an_explicit_print_is_not_doubled(self):
        assert Session().evaluate('print "hi";') == ["hi"]

    def test_two_statements_are_not_auto_printed(self):
        assert Session().evaluate("let a = 1; let b = 2;") == []

    def test_a_call_returning_nothing_shows_nil(self):
        # the truthful answer rather than a special case
        session = Session()
        session.evaluate("fn nothing() { }")
        assert session.evaluate("nothing();") == ["nil"]

    def test_a_returned_collection_is_printed(self):
        assert Session().evaluate("[1, 2, 3];") == ["[1, 2, 3]"]


class TestErrorRecovery:
    def test_a_fault_is_reported_without_raising(self):
        session = Session()
        printed, error = session.evaluate_safely("1 / 0;")
        assert printed == []
        assert error is not None
        assert "division by zero" in error

    def test_the_session_survives_a_fault(self):
        session = Session()
        session.evaluate("let n = 5;")
        session.evaluate_safely("1 / 0;")
        assert session.evaluate("n + 1;") == ["6"]

    def test_no_output_leaks_from_an_abandoned_run(self):
        # the faulted run left frames behind; the next input must not resume them
        session = Session()
        session.evaluate("fn dbl(x) { return x * 2; }")
        session.evaluate_safely("1 / 0;")
        assert session.evaluate("dbl(3);") == ["6"]

    def test_a_syntax_fault_is_reported_too(self):
        printed, error = Session().evaluate_safely("1 +;")
        assert printed == []
        assert error is not None

    def test_failures_are_counted(self):
        session = Session()
        session.evaluate_safely("1 / 0;")
        session.evaluate_safely("missing;")
        assert session.failures == 2

    def test_evaluate_raises_where_evaluate_safely_reports(self):
        session = Session()
        with pytest.raises(Arithmetic):
            session.evaluate("1 / 0;")
        with pytest.raises(Syntax):
            session.evaluate("1 +;")


class TestCounting:
    def test_inputs_are_counted(self):
        session = Session()
        session.evaluate("1;")
        session.evaluate("2;")
        assert session.inputs == 2

    def test_globals_are_reachable_for_inspection(self):
        session = Session()
        session.evaluate("let answer = 42;")
        assert session.globals["answer"] == 42
