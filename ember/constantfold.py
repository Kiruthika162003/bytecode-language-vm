"""Constant folding: compute at compile time whatever does not depend on the program running.

An expression built only from literals has the same value every time the
program runs, so computing it once while compiling is strictly better than
recomputing it on every execution. This pass rewrites the syntax tree,
replacing such an expression with the literal it evaluates to, so that a
line like a radius times two times pi becomes a single constant load
instead of two multiplications. It also folds the short-circuit
operators, which is sound in a way worth spelling out: a false left side
of an and evaluates to that false and never looks at the right, so the
whole expression collapses to false, and a true left side of an and
collapses to the right side alone. What this pass deliberately does not
do is the algebraic simplification a statically typed compiler would
reach for. Rewriting a value plus zero into the value, or a value times
one into the value, is unsound in this language, because plus is
overloaded over numbers, strings, and lists, and the compiler cannot know
which a variable holds; a string plus zero is a type error the program is
entitled to receive, and an optimiser that quietly deleted it would
change the meaning of the code. The same caution governs division: a
division by a literal zero is left exactly as written so it still raises
at run time rather than failing during compilation, since the error
belongs to the program's execution and may sit on a branch that never
runs. Folding is applied bottom-up and repeatedly to a fixed point, so a
nested expression collapses all the way in one pass over the tree.
"""

from __future__ import annotations

from typing import Any

from ember import exprnodes as e
from ember import stmtnodes as s
from ember.token import Token
from ember.tokenkind import TokenKind
from ember.valueops import is_truthy, values_equal

_NUMERIC = {
    TokenKind.MINUS: lambda a, b: a - b,
    TokenKind.STAR: lambda a, b: a * b,
}

_COMPARISON = {
    TokenKind.LESS: lambda a, b: a < b,
    TokenKind.LESS_EQUAL: lambda a, b: a <= b,
    TokenKind.GREATER: lambda a, b: a > b,
    TokenKind.GREATER_EQUAL: lambda a, b: a >= b,
}


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _literal(value: Any, token: Token) -> e.Literal:
    return e.Literal(value, token)


def fold_expression(node: e.Expr) -> e.Expr:
    if isinstance(node, e.Grouping):
        inner = fold_expression(node.inner)
        if isinstance(inner, e.Literal):
            return inner
        return e.Grouping(inner)
    if isinstance(node, e.Unary):
        return _fold_unary(node)
    if isinstance(node, e.Binary):
        return _fold_binary(node)
    if isinstance(node, e.Logical):
        return _fold_logical(node)
    if isinstance(node, e.Conditional):
        return _fold_conditional(node)
    if isinstance(node, e.Assign):
        return e.Assign(node.name, fold_expression(node.value))
    if isinstance(node, e.Call):
        arguments = tuple(fold_expression(argument) for argument in node.arguments)
        return e.Call(fold_expression(node.callee), node.paren, arguments)
    if isinstance(node, e.Index):
        return e.Index(
            fold_expression(node.collection), node.bracket, fold_expression(node.key)
        )
    if isinstance(node, e.SetIndex):
        return e.SetIndex(
            fold_expression(node.collection),
            node.bracket,
            fold_expression(node.key),
            fold_expression(node.value),
        )
    if isinstance(node, e.Get):
        return e.Get(fold_expression(node.target), node.name)
    if isinstance(node, e.Set):
        return e.Set(fold_expression(node.target), node.name, fold_expression(node.value))
    if isinstance(node, e.ListLiteral):
        elements = tuple(fold_expression(item) for item in node.elements)
        return e.ListLiteral(node.bracket, elements)
    if isinstance(node, e.MapLiteral):
        pairs = tuple(
            (fold_expression(key), fold_expression(value)) for key, value in node.pairs
        )
        return e.MapLiteral(node.brace, pairs)
    return node


def _fold_unary(node: e.Unary) -> e.Expr:
    operand = fold_expression(node.operand)
    if isinstance(operand, e.Literal):
        if node.operator.kind == TokenKind.MINUS and _is_number(operand.value):
            return _literal(-operand.value, node.operator)
        if node.operator.kind in (TokenKind.BANG, TokenKind.NOT):
            return _literal(not is_truthy(operand.value), node.operator)
    return e.Unary(node.operator, operand)


def _fold_binary(node: e.Binary) -> e.Expr:
    left = fold_expression(node.left)
    right = fold_expression(node.right)
    rebuilt = e.Binary(left, node.operator, right)
    if not (isinstance(left, e.Literal) and isinstance(right, e.Literal)):
        return rebuilt
    a = left.value
    b = right.value
    kind = node.operator.kind
    token = node.operator
    if kind == TokenKind.EQUAL_EQUAL:
        return _literal(values_equal(a, b), token)
    if kind == TokenKind.BANG_EQUAL:
        return _literal(not values_equal(a, b), token)
    if kind == TokenKind.PLUS:
        if _is_number(a) and _is_number(b):
            return _literal(a + b, token)
        if isinstance(a, str) and isinstance(b, str):
            return _literal(a + b, token)
        return rebuilt
    if not (_is_number(a) and _is_number(b)):
        # comparisons of two strings are foldable, everything else is left for
        # the machine so its type error still reaches the program
        if kind in _COMPARISON and isinstance(a, str) and isinstance(b, str):
            return _literal(_COMPARISON[kind](a, b), token)
        return rebuilt
    if kind in _NUMERIC:
        return _literal(_NUMERIC[kind](a, b), token)
    if kind in _COMPARISON:
        return _literal(_COMPARISON[kind](a, b), token)
    if kind in (TokenKind.SLASH, TokenKind.PERCENT):
        if b == 0:
            # left exactly as written so the division still raises at run time
            return rebuilt
        if kind == TokenKind.SLASH:
            return _literal(a / b, token)
        return _literal(a % b, token)
    return rebuilt


def _fold_logical(node: e.Logical) -> e.Expr:
    left = fold_expression(node.left)
    right = fold_expression(node.right)
    if isinstance(left, e.Literal):
        truthy = is_truthy(left.value)
        if node.operator.kind == TokenKind.AND:
            return left if not truthy else right
        return left if truthy else right
    return e.Logical(left, node.operator, right)


def _fold_conditional(node: e.Conditional) -> e.Expr:
    condition = fold_expression(node.condition)
    when_true = fold_expression(node.when_true)
    when_false = fold_expression(node.when_false)
    if isinstance(condition, e.Literal):
        # a known condition selects an arm outright, and the other disappears
        return when_true if is_truthy(condition.value) else when_false
    return e.Conditional(condition, node.question, when_true, when_false)


def fold_statement(node: s.Stmt) -> s.Stmt:
    if isinstance(node, s.ExpressionStmt):
        return s.ExpressionStmt(fold_expression(node.expression))
    if isinstance(node, s.PrintStmt):
        return s.PrintStmt(node.keyword, fold_expression(node.expression))
    if isinstance(node, s.LetStmt):
        initializer = (
            fold_expression(node.initializer) if node.initializer is not None else None
        )
        return s.LetStmt(node.name, initializer, node.is_const)
    if isinstance(node, s.Block):
        return s.Block(tuple(fold_statement(inner) for inner in node.statements))
    if isinstance(node, s.IfStmt):
        return s.IfStmt(
            fold_expression(node.condition),
            fold_statement(node.then_branch),
            fold_statement(node.else_branch) if node.else_branch is not None else None,
        )
    if isinstance(node, s.WhileStmt):
        return s.WhileStmt(fold_expression(node.condition), fold_statement(node.body))
    if isinstance(node, s.ForStmt):
        return s.ForStmt(
            fold_statement(node.initializer) if node.initializer is not None else None,
            fold_expression(node.condition) if node.condition is not None else None,
            fold_expression(node.increment) if node.increment is not None else None,
            fold_statement(node.body),
        )
    if isinstance(node, s.TryStmt):
        return s.TryStmt(
            node.keyword,
            fold_statement(node.body),
            node.catch_name,
            fold_statement(node.handler),
        )
    if isinstance(node, s.ThrowStmt):
        return s.ThrowStmt(node.keyword, fold_expression(node.value))
    if isinstance(node, s.ForEachStmt):
        return s.ForEachStmt(
            node.variable, fold_expression(node.iterable), fold_statement(node.body)
        )
    if isinstance(node, s.FunctionStmt):
        body = tuple(fold_statement(inner) for inner in node.body)
        return s.FunctionStmt(node.name, node.parameters, body)
    if isinstance(node, s.ClassStmt):
        methods = tuple(_fold_method(method) for method in node.methods)
        return s.ClassStmt(node.name, node.superclass, methods)
    if isinstance(node, s.ReturnStmt):
        value = fold_expression(node.value) if node.value is not None else None
        return s.ReturnStmt(node.keyword, value)
    return node


def _fold_method(node: s.FunctionStmt) -> s.FunctionStmt:
    body = tuple(fold_statement(inner) for inner in node.body)
    return s.FunctionStmt(node.name, node.parameters, body)


def fold_program(statements: list[s.Stmt]) -> list[s.Stmt]:
    return [fold_statement(statement) for statement in statements]
