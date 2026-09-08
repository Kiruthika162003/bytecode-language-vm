from __future__ import annotations

import pytest

from ember.interpreter import build, run_output, run_treewalk_output
from ember.optimizer import optimize
from ember.parser import parse
from ember.scanner import scan

# Programs spanning what the passes touch and what they must leave alone. The
# claim under test is the only one an optimizer may never break: the program
# means the same thing afterwards.
PROGRAMS = [
    "print 1 + 2 * 3;",
    "print (2 + 3) * (4 - 1);",
    'print "a" + "b";',
    "print not false; print -(-5);",
    'print true and "x"; print false or "y";',
    'if (false) { print "a"; } else { print "b"; }',
    'if (2 > 3) { print "a"; } else { print "b"; }',
    'while (false) { print "never"; } print "done";',
    "let s = 0; for (let i = 0; i < 5; i = i + 1) s = s + i; print s;",
    'fn f() { return 1; print "dead"; } print f();',
    "print 1 / 0 == 1;",
    'print "a" + 0;',
    "let x = 2; print x + 0; print x * 1;",
    "class C { init() { this.v = 3 * 3; } get() { return this.v; } } print C().get();",
    (
        "class A { m() { return 1 + 1; } }"
        " class B < A { m() { return super.m() * 2; } } print B().m();"
    ),
    (
        "fn make() { let c = 0; fn inc() { c = c + 1; return c; } return inc; }"
        " let g = make(); print g(); print g();"
    ),
]


@pytest.mark.parametrize("source", PROGRAMS)
def test_optimizing_does_not_change_what_a_program_means(source: str):
    def outcome(runner, optimize_flag: bool):
        try:
            return ("ok", runner(source, optimize=optimize_flag))
        except Exception as exc:
            return ("error", type(exc).__name__)

    plain_vm = outcome(run_output, False)
    tight_vm = outcome(run_output, True)
    plain_tree = outcome(run_treewalk_output, False)
    tight_tree = outcome(run_treewalk_output, True)
    assert plain_vm == tight_vm
    assert plain_vm == plain_tree
    assert plain_vm == tight_tree


class TestFixedPoint:
    def test_it_reports_the_rounds_it_took(self):
        _, report = optimize(parse(scan("print 1 + 2 * 3;")))
        assert report.rounds >= 1
        assert report.changed

    def test_an_already_minimal_program_reports_no_change(self):
        _, report = optimize(parse(scan("print x;")))
        assert not report.changed

    def test_it_reaches_a_fixed_point_rather_than_looping(self):
        _, report = optimize(parse(scan('if (1 < 2) { print 3 * 3; } else { print 0; }')))
        assert report.rounds <= 8


class TestMeasuredEffect:
    def test_folding_shrinks_the_emitted_chunk(self):
        plain = build("print 1 + 2 * 3 - 4 / 2;", optimize=False).chunk
        tight = build("print 1 + 2 * 3 - 4 / 2;", optimize=True).chunk
        # measured, not assumed: four constants and the arithmetic collapse to one load
        assert len(plain.code) == 17
        assert len(tight.code) == 5
        assert len(plain.constants) == 4
        assert len(tight.constants) == 1

    def test_pruning_removes_an_unreachable_branch_entirely(self):
        source = 'if (false) { print "a"; print "b"; print "c"; } print "d";'
        plain = build(source, optimize=False).chunk
        tight = build(source, optimize=True).chunk
        assert len(tight.code) < len(plain.code)
        assert "a" not in tight.constants

    def test_an_unoptimizable_program_is_not_made_worse(self):
        source = "let x = 1; print x + x;"
        plain = build(source, optimize=False).chunk
        tight = build(source, optimize=True).chunk
        assert len(tight.code) <= len(plain.code)
