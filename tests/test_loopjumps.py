from __future__ import annotations

import pytest

from ember import stmtnodes as s
from ember.deadcode import prune_program
from ember.errors import Syntax
from ember.interpreter import run, run_output, run_treewalk_output
from ember.parser import parse
from ember.scanner import scan

SHARED = [
    "for (let i = 0; i < 10; i = i + 1) { if (i == 3) break; print i; }",
    "for (let i = 0; i < 6; i = i + 1) { if (i % 2 == 0) continue; print i; }",
    "let n = 0; while (true) { n = n + 1; if (n > 3) break; print n; }",
    "let i = 0; while (i < 6) { i = i + 1; if (i % 2 == 0) continue; print i; }",
    (
        "for (let i = 0; i < 3; i = i + 1)"
        " { for (let j = 0; j < 3; j = j + 1) { if (j == 1) break; print i * 10 + j; } }"
    ),
    "for (let i = 0; i < 4; i = i + 1) { let a = i * 2; if (i == 2) break; print a; }",
    "for (let i = 0; i < 4; i = i + 1) { let a = i; if (a == 1) continue; print a; }",
    (
        "let s = 0; for (let i = 1; i <= 100; i = i + 1)"
        " { s = s + i; if (s > 10) break; } print s;"
    ),
]


class TestBreak:
    def test_break_leaves_a_for_loop(self):
        assert run_output(
            "for (let i = 0; i < 10; i = i + 1) { if (i == 3) break; print i; }"
        ) == ["0", "1", "2"]

    def test_break_leaves_a_while_loop(self):
        source = "let n = 0; while (true) { n = n + 1; if (n > 3) break; print n; }"
        assert run_output(source) == ["1", "2", "3"]

    def test_break_only_leaves_the_innermost_loop(self):
        source = (
            "for (let i = 0; i < 3; i = i + 1)"
            " { for (let j = 0; j < 3; j = j + 1) { if (j == 1) break; print i * 10 + j; } }"
        )
        assert run_output(source) == ["0", "10", "20"]

    def test_break_discards_the_locals_the_body_declared(self):
        source = (
            "for (let i = 0; i < 4; i = i + 1)"
            " { let a = i * 2; if (i == 2) break; print a; }"
        )
        assert run_output(source) == ["0", "2"]


class TestContinue:
    def test_continue_skips_the_rest_of_an_iteration(self):
        assert run_output(
            "for (let i = 0; i < 6; i = i + 1) { if (i % 2 == 0) continue; print i; }"
        ) == ["1", "3", "5"]

    def test_continue_still_runs_the_for_increment(self):
        # if the increment were skipped this would never terminate
        source = (
            "let seen = 0; for (let i = 0; i < 4; i = i + 1)"
            " { if (i < 2) continue; seen = seen + 1; } print seen;"
        )
        assert run_output(source) == ["2"]

    def test_continue_works_in_a_while_loop(self):
        assert run_output(
            "let i = 0; while (i < 6) { i = i + 1; if (i % 2 == 0) continue; print i; }"
        ) == ["1", "3", "5"]


class TestPlacementRules:
    def test_break_outside_a_loop_is_refused(self):
        with pytest.raises(Syntax):
            run("break;")

    def test_continue_outside_a_loop_is_refused(self):
        with pytest.raises(Syntax):
            run("continue;")

    def test_break_inside_a_function_in_a_loop_is_refused(self):
        # the function is a new frame, so there is no loop for break to act on
        with pytest.raises(Syntax):
            run("for (let i = 0; i < 2; i = i + 1) { fn g() { break; } }")

    def test_a_missing_semicolon_is_refused(self):
        with pytest.raises(Syntax):
            run("for (let i = 0; i < 2; i = i + 1) { break }")


class TestDeadCodeAfterJumps:
    def test_statements_after_a_break_are_dropped(self):
        program = prune_program(parse(scan('while (true) { break; print "dead"; }')))
        body = program[0].body
        assert len(body.statements) == 1

    def test_statements_after_a_continue_are_dropped(self):
        program = prune_program(parse(scan('while (true) { continue; print "dead"; }')))
        assert len(program[0].body.statements) == 1

    def test_the_jump_itself_is_kept(self):
        program = prune_program(parse(scan("while (true) { break; }")))
        assert isinstance(program[0].body.statements[0], s.BreakStmt)


class TestBothBackendsAgree:
    @pytest.mark.parametrize("source", SHARED)
    def test_agreement(self, source: str):
        assert run_output(source) == run_treewalk_output(source)

    @pytest.mark.parametrize("source", SHARED)
    def test_agreement_when_optimized(self, source: str):
        assert run_output(source, optimize=True) == run_treewalk_output(source, optimize=True)
