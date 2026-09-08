from __future__ import annotations

from ember import stmtnodes as s
from ember.deadcode import prune_program
from ember.optimizer import optimize_program
from ember.parser import parse
from ember.scanner import scan


def pruned(source: str) -> list[s.Stmt]:
    return prune_program(parse(scan(source)))


def optimized(source: str) -> list[s.Stmt]:
    return optimize_program(parse(scan(source)))


class TestBranches:
    def test_a_true_branch_replaces_the_if(self):
        program = pruned('if (true) print "a"; else print "b";')
        assert isinstance(program[0], s.PrintStmt)

    def test_a_false_branch_selects_the_else(self):
        program = pruned('if (false) print "a"; else print "b";')
        assert isinstance(program[0], s.PrintStmt)
        assert program[0].expression.value == "b"

    def test_a_false_if_with_no_else_becomes_empty(self):
        program = pruned('if (false) print "a";')
        assert isinstance(program[0], s.Block)
        assert program[0].statements == ()

    def test_a_variable_condition_is_left_alone(self):
        program = pruned('if (x) print "a"; else print "b";')
        assert isinstance(program[0], s.IfStmt)


class TestLoops:
    def test_a_false_while_disappears(self):
        program = pruned('while (false) print "never";')
        assert isinstance(program[0], s.Block)
        assert program[0].statements == ()

    def test_a_true_while_is_kept(self):
        program = pruned("while (true) print 1;")
        assert isinstance(program[0], s.WhileStmt)

    def test_a_false_for_keeps_only_its_initializer(self):
        program = pruned('for (let i = 0; false; i = i + 1) print "never";')
        assert isinstance(program[0], s.Block)
        assert len(program[0].statements) == 1
        assert isinstance(program[0].statements[0], s.LetStmt)


class TestUnreachable:
    def test_statements_after_a_return_are_dropped(self):
        program = pruned('fn f() { return 1; print "dead"; }')
        assert len(program[0].body) == 1

    def test_a_return_in_a_method_also_prunes(self):
        program = pruned('class C { m() { return 1; print "dead"; } }')
        assert len(program[0].methods[0].body) == 1

    def test_statements_before_a_return_are_kept(self):
        program = pruned('fn f() { print "live"; return 1; }')
        assert len(program[0].body) == 2


class TestWithFolding:
    def test_a_folded_condition_becomes_decidable(self):
        # 2 > 3 folds to false, so the branch can then be removed
        program = optimized('if (2 > 3) print "a"; else print "b";')
        assert isinstance(program[0], s.PrintStmt)
        assert program[0].expression.value == "b"

    def test_a_folded_loop_condition_removes_the_loop(self):
        program = optimized('while (1 > 2) print "never";')
        assert isinstance(program[0], s.Block)
        assert program[0].statements == ()


class TestConservatism:
    def test_a_declaration_is_not_removed_from_a_live_block(self):
        program = pruned("{ let x = 1; print x; }")
        assert len(program[0].statements) == 2
