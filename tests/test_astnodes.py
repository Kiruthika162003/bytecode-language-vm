from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from ember import exprnodes as e
from ember import stmtnodes as s
from ember.scanner import scan


def tok(source: str):
    return scan(source)[0]


class TestExpressionNodes:
    def test_a_literal_holds_its_value(self):
        node = e.Literal(42, tok("42"))
        assert node.value == 42
        assert isinstance(node, e.Expr)

    def test_a_binary_nests_expressions(self):
        left = e.Literal(1, tok("1"))
        right = e.Literal(2, tok("2"))
        node = e.Binary(left, tok("+"), right)
        assert node.left is left
        assert node.right is right
        assert isinstance(node, e.Expr)

    def test_a_call_holds_a_tuple_of_arguments(self):
        callee = e.Variable(tok("f"))
        node = e.Call(callee, tok("("), (e.Literal(1, tok("1")),))
        assert len(node.arguments) == 1

    def test_expression_nodes_are_frozen(self):
        node = e.Literal(1, tok("1"))
        with pytest.raises(FrozenInstanceError):
            node.value = 2  # type: ignore[misc]


class TestStatementNodes:
    def test_a_let_records_its_constness(self):
        node = s.LetStmt(tok("x"), e.Literal(1, tok("1")), is_const=True)
        assert node.is_const
        assert isinstance(node, s.Stmt)

    def test_a_block_holds_a_tuple_of_statements(self):
        inner = s.ExpressionStmt(e.Literal(1, tok("1")))
        node = s.Block((inner,))
        assert node.statements == (inner,)

    def test_an_if_may_have_no_else(self):
        node = s.IfStmt(e.Literal(True, tok("true")), s.Block(()), None)
        assert node.else_branch is None

    def test_statement_nodes_are_frozen(self):
        node = s.ReturnStmt(tok("return"), None)
        with pytest.raises(FrozenInstanceError):
            node.value = e.Literal(1, tok("1"))  # type: ignore[misc]


class TestFamilies:
    def test_expressions_and_statements_are_separate_bases(self):
        assert not issubclass(e.Expr, s.Stmt)
        assert not issubclass(s.Stmt, e.Expr)
