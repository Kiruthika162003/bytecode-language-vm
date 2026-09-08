"""Expression nodes: the tree shapes that stand for things that produce a value.

An expression is any piece of a program that computes a value: a
literal, a variable read, an arithmetic combination, a function call, an
index into a list. The parser builds one of these node objects for each
such piece, nesting them so that the structure of the tree records the
structure of the computation and, crucially, the precedence and grouping
the source intended, which the flat token stream did not. This module
defines those node types as small immutable dataclasses, one per shape,
sharing a common Expr base so a later stage can accept any expression
where one is expected. The deliberate choice here is to keep the nodes
as pure data with no behavior of their own. A tree-walking interpreter
often hangs an evaluate method on each node, but this runtime compiles
the tree to bytecode instead, and spreading the compilation logic across
dozens of node methods would scatter it; keeping the nodes dumb lets the
compiler hold all of that logic in one place and dispatch on the node's
type. Each node keeps the token or tokens it came from, not for its
value but so that an error raised while compiling or running it can
point back at the exact source. The honest cost of one class per shape
is a long list of tiny types, but the alternative, a single node with a
tag field, trades that verbosity for a loss of the type checker's help
in knowing which fields a given shape actually has.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ember.token import Token


class Expr:
    """The base of every expression node; carries no data itself."""


@dataclass(frozen=True)
class Literal(Expr):
    value: Any
    token: Token


@dataclass(frozen=True)
class Variable(Expr):
    name: Token


@dataclass(frozen=True)
class Unary(Expr):
    operator: Token
    operand: Expr


@dataclass(frozen=True)
class Binary(Expr):
    left: Expr
    operator: Token
    right: Expr


@dataclass(frozen=True)
class Logical(Expr):
    left: Expr
    operator: Token
    right: Expr


@dataclass(frozen=True)
class Grouping(Expr):
    inner: Expr


@dataclass(frozen=True)
class Assign(Expr):
    name: Token
    value: Expr


@dataclass(frozen=True)
class Call(Expr):
    callee: Expr
    paren: Token
    arguments: tuple[Expr, ...]


@dataclass(frozen=True)
class Index(Expr):
    collection: Expr
    bracket: Token
    key: Expr


@dataclass(frozen=True)
class SetIndex(Expr):
    collection: Expr
    bracket: Token
    key: Expr
    value: Expr


@dataclass(frozen=True)
class Get(Expr):
    target: Expr
    name: Token


@dataclass(frozen=True)
class Set(Expr):
    target: Expr
    name: Token
    value: Expr


@dataclass(frozen=True)
class This(Expr):
    keyword: Token


@dataclass(frozen=True)
class ListLiteral(Expr):
    bracket: Token
    elements: tuple[Expr, ...]


@dataclass(frozen=True)
class MapLiteral(Expr):
    brace: Token
    pairs: tuple[tuple[Expr, Expr], ...]
