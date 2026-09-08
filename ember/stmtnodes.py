"""Statement nodes: the tree shapes that stand for things that are done, not computed.

Where an expression produces a value, a statement performs an action:
it declares a variable, runs a block, loops, branches, defines a
function, or returns from one. The distinction matters because the two
compose differently. A statement can contain expressions and other
statements, but an expression can only contain expressions, and keeping
the two kinds of node in separate families makes that rule visible in
the types rather than left to convention. This module defines the
statement shapes as immutable dataclasses over a common Stmt base,
mirroring the expression nodes and keeping the same discipline of pure
data with the originating tokens retained for error reporting. A few
choices are worth naming. A let declaration carries a flag saying
whether it was written as a mutable let or an immutable const, so the
resolver and compiler can forbid reassigning a constant without needing
a separate node type. A function is represented as a statement that
names it and holds its parameters and body, which ties a function
definition to the scope it appears in. The for loop is kept as its own
node rather than being desugared into a while during parsing, because
preserving the author's structure gives clearer error messages and
leaves the choice of how to compile it, including whether to desugar,
to the compiler where the tradeoff belongs.
"""

from __future__ import annotations

from dataclasses import dataclass

from ember.exprnodes import Expr
from ember.token import Token


class Stmt:
    """The base of every statement node; carries no data itself."""


@dataclass(frozen=True)
class ExpressionStmt(Stmt):
    expression: Expr


@dataclass(frozen=True)
class PrintStmt(Stmt):
    keyword: Token
    expression: Expr


@dataclass(frozen=True)
class LetStmt(Stmt):
    name: Token
    initializer: Expr | None
    is_const: bool


@dataclass(frozen=True)
class Block(Stmt):
    statements: tuple[Stmt, ...]


@dataclass(frozen=True)
class IfStmt(Stmt):
    condition: Expr
    then_branch: Stmt
    else_branch: Stmt | None


@dataclass(frozen=True)
class WhileStmt(Stmt):
    condition: Expr
    body: Stmt


@dataclass(frozen=True)
class ForStmt(Stmt):
    initializer: Stmt | None
    condition: Expr | None
    increment: Expr | None
    body: Stmt


@dataclass(frozen=True)
class FunctionStmt(Stmt):
    name: Token
    parameters: tuple[Token, ...]
    body: tuple[Stmt, ...]


@dataclass(frozen=True)
class ReturnStmt(Stmt):
    keyword: Token
    value: Expr | None


@dataclass(frozen=True)
class BreakStmt(Stmt):
    keyword: Token


@dataclass(frozen=True)
class ContinueStmt(Stmt):
    keyword: Token


@dataclass(frozen=True)
class ClassStmt(Stmt):
    name: Token
    superclass: Token | None
    methods: tuple[FunctionStmt, ...]
