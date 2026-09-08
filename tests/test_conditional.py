from __future__ import annotations

import pytest

from ember import exprnodes as e
from ember import stmtnodes as s
from ember.constantfold import fold_program
from ember.errors import Syntax
from ember.interpreter import run, run_output, run_treewalk_output
from ember.parser import parse
from ember.scanner import scan

SHARED = [
    'print 1 < 2 ? "yes" : "no";',
    'let n = 5; print n > 3 ? "big" : n > 1 ? "mid" : "small";',
    "print true ? 1 : 2; print false ? 1 : 2;",
    'let x = 1 == 1 ? "a" : "b"; print x;',
    "fn sign(n) { return n < 0 ? -1 : n > 0 ? 1 : 0; }"
    " print sign(-4); print sign(0); print sign(9);",
    'print [1, 2] ? "truthy" : "falsey";',
    'let a = nil; print a ? "set" : "unset";',
]


def first_expression(source: str) -> e.Expr:
    program = fold_program(parse(scan(source)))
    assert isinstance(program[0], s.ExpressionStmt)
    return program[0].expression


class TestConditional:
    def test_it_selects_the_true_arm(self):
        assert run_output('print 1 < 2 ? "yes" : "no";') == ["yes"]

    def test_it_selects_the_false_arm(self):
        assert run_output('print 1 > 2 ? "yes" : "no";') == ["no"]

    def test_it_yields_a_value_usable_in_a_declaration(self):
        assert run_output('let x = 1 == 1 ? "a" : "b"; print x;') == ["a"]

    def test_only_the_selected_arm_runs(self):
        source = (
            'fn loud() { print "ran"; return 1; }'
            " let v = false ? loud() : 2; print v;"
        )
        assert run_output(source) == ["2"]

    def test_truthiness_follows_the_language_rule(self):
        # only false and nil are falsey, so an empty list picks the true arm
        assert run_output('print [] ? "truthy" : "falsey";') == ["truthy"]
        assert run_output('print nil ? "set" : "unset";') == ["unset"]


class TestChaining:
    def test_a_chain_groups_to_the_right(self):
        source = 'let n = 2; print n > 3 ? "big" : n > 1 ? "mid" : "small";'
        assert run_output(source) == ["mid"]

    def test_a_three_way_sign_function(self):
        source = (
            "fn sign(n) { return n < 0 ? -1 : n > 0 ? 1 : 0; }"
            " print sign(-4); print sign(0); print sign(9);"
        )
        assert run_output(source) == ["-1", "0", "1"]


class TestFolding:
    def test_a_known_condition_selects_an_arm_at_compile_time(self):
        node = first_expression('true ? "a" : "b";')
        assert isinstance(node, e.Literal)
        assert node.value == "a"

    def test_a_known_false_condition_selects_the_other(self):
        node = first_expression('false ? "a" : "b";')
        assert isinstance(node, e.Literal)
        assert node.value == "b"

    def test_a_folded_comparison_makes_the_condition_known(self):
        node = first_expression('2 > 3 ? "a" : "b";')
        assert isinstance(node, e.Literal)
        assert node.value == "b"

    def test_an_unknown_condition_is_left_alone(self):
        assert isinstance(first_expression('x ? "a" : "b";'), e.Conditional)


class TestSyntax:
    def test_a_missing_colon_is_refused(self):
        with pytest.raises(Syntax):
            run("print 1 ? 2;")

    def test_a_missing_false_arm_is_refused(self):
        with pytest.raises(Syntax):
            run("print 1 ? 2 : ;")


class TestBothBackendsAgree:
    @pytest.mark.parametrize("source", SHARED)
    def test_agreement(self, source: str):
        assert run_output(source) == run_treewalk_output(source)

    @pytest.mark.parametrize("source", SHARED)
    def test_agreement_when_fully_optimized(self, source: str):
        assert run_output(source, optimize=True, peephole=True) == run_treewalk_output(
            source, optimize=True
        )
