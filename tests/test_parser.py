from __future__ import annotations

import pytest

from ember import exprnodes as e
from ember import stmtnodes as s
from ember.errors import Syntax
from ember.parser import parse
from ember.scanner import scan


def sexpr(expr: e.Expr) -> str:
    if isinstance(expr, e.Literal):
        return repr(expr.value)
    if isinstance(expr, e.Variable):
        return expr.name.lexeme
    if isinstance(expr, e.Unary):
        return f"({expr.operator.lexeme} {sexpr(expr.operand)})"
    if isinstance(expr, (e.Binary, e.Logical)):
        return f"({expr.operator.lexeme} {sexpr(expr.left)} {sexpr(expr.right)})"
    if isinstance(expr, e.Grouping):
        return f"(group {sexpr(expr.inner)})"
    if isinstance(expr, e.Assign):
        return f"(= {expr.name.lexeme} {sexpr(expr.value)})"
    if isinstance(expr, e.Call):
        inner = " ".join(sexpr(a) for a in expr.arguments)
        return f"(call {sexpr(expr.callee)} [{inner}])"
    if isinstance(expr, e.Index):
        return f"(index {sexpr(expr.collection)} {sexpr(expr.key)})"
    raise AssertionError(type(expr))


def first_expr(source: str) -> e.Expr:
    program = parse(scan(source))
    assert isinstance(program[0], s.ExpressionStmt)
    return program[0].expression


class TestPrecedence:
    def test_factor_binds_tighter_than_term(self):
        assert sexpr(first_expr("1 + 2 * 3;")) == "(+ 1 (* 2 3))"
        assert sexpr(first_expr("1 * 2 + 3;")) == "(+ (* 1 2) 3)"

    def test_subtraction_is_left_associative(self):
        assert sexpr(first_expr("1 - 2 - 3;")) == "(- (- 1 2) 3)"

    def test_grouping_overrides_precedence(self):
        assert sexpr(first_expr("(1 + 2) * 3;")) == "(* (group (+ 1 2)) 3)"

    def test_and_binds_tighter_than_or(self):
        assert sexpr(first_expr("a and b or c;")) == "(or (and a b) c)"

    def test_unary_binds_tighter_than_term(self):
        assert sexpr(first_expr("-a + b;")) == "(+ (- a) b)"


class TestPostfix:
    def test_calls_chain(self):
        assert sexpr(first_expr("f(1, 2)(3);")) == "(call (call f [1 2]) [3])"

    def test_indexing_chains(self):
        assert sexpr(first_expr("a[1][2];")) == "(index (index a 1) 2)"


class TestAssignment:
    def test_assignment_is_right_associative(self):
        assert sexpr(first_expr("x = y = 3;")) == "(= x (= y 3))"

    def test_a_non_variable_target_is_refused(self):
        with pytest.raises(Syntax):
            parse(scan("1 = 2;"))


class TestStatements:
    def test_a_program_is_a_list_of_statements(self):
        program = parse(scan("let x = 1; print x;"))
        assert isinstance(program[0], s.LetStmt)
        assert isinstance(program[1], s.PrintStmt)

    def test_a_const_requires_an_initializer(self):
        with pytest.raises(Syntax):
            parse(scan("const z;"))

    def test_if_else_while_for_and_functions_parse(self):
        program = parse(
            scan(
                "if (a) print a; else print b;"
                " while (a) a = a - 1;"
                " for (let i = 0; i < 3; i = i + 1) print i;"
                " fn add(x, y) { return x + y; }"
            )
        )
        assert [type(node).__name__ for node in program] == [
            "IfStmt",
            "WhileStmt",
            "ForStmt",
            "FunctionStmt",
        ]

    def test_a_block_groups_statements(self):
        program = parse(scan("{ let x = 1; print x; }"))
        assert isinstance(program[0], s.Block)
        assert len(program[0].statements) == 2


class TestCollections:
    def test_a_list_literal(self):
        program = parse(scan("let a = [1, 2, 3];"))
        assert isinstance(program[0].initializer, e.ListLiteral)
        assert len(program[0].initializer.elements) == 3

    def test_a_map_literal(self):
        program = parse(scan('let m = {"a": 1};'))
        assert isinstance(program[0].initializer, e.MapLiteral)
        assert len(program[0].initializer.pairs) == 1


class TestErrors:
    def test_a_missing_semicolon_is_refused(self):
        with pytest.raises(Syntax):
            parse(scan("let x = 1"))

    def test_an_unclosed_group_is_refused(self):
        with pytest.raises(Syntax):
            parse(scan("(1 + 2;"))

    def test_a_dangling_operator_is_refused(self):
        with pytest.raises(Syntax):
            parse(scan("1 +;"))
