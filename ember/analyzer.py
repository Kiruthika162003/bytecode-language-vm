"""Static analysis: report what compiles cleanly but a reader would still question.

The compiler's job is to decide whether a program is legal, and it says nothing
about whether the program is sensible. A variable declared and never read is
legal. So is a branch whose condition can only be true, a statement written after
a return, and a method that never touches the instance it was reached through.
Each of those is usually a mistake or a leftover, and each is cheap to find on
the syntax tree, so this module finds them and reports them as diagnostics rather
than errors: a diagnostic never stops a program from running, because a linter
that refuses to run your code is a linter people turn off. The design problem in
a tool like this is not detection but false positives, since a rule that cries
wolf gets ignored along with the rules that do not. So three concessions are
built in deliberately. A name beginning with an underscore is exempt from the
unused checks, because that is the established way of saying a binding exists on
purpose and is not meant to be read. Shadowing is only reported within one
function, since a local quite reasonably reuses a name that happens to exist as a
global. And an assignment does not count as a use, which is itself a judgement:
a variable only ever written is reported, because storing a value nobody reads is
the thing worth knowing about. The honest limitation is that every check here is
syntactic. Nothing tracks what a value holds or which branch runs, so a variable
read only inside an unreachable branch still counts as read, and proving otherwise
would need the dataflow analysis this module deliberately does not attempt.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ember import exprnodes as e
from ember import stmtnodes as s
from ember.valueops import is_truthy

UNUSED_LOCAL = "unused-local"
UNUSED_PARAMETER = "unused-parameter"
SHADOWED = "shadowed"
UNREACHABLE = "unreachable"
CONSTANT_CONDITION = "constant-condition"
EMPTY_BODY = "empty-body"
STATIC_METHOD = "method-ignores-this"
SELF_ASSIGNMENT = "self-assignment"


@dataclass(frozen=True)
class Diagnostic:
    kind: str
    line: int
    message: str

    def render(self) -> str:
        return f"line {self.line}: {self.kind}: {self.message}"


@dataclass
class _Binding:
    name: str
    line: int
    reads: int = 0
    is_parameter: bool = False


@dataclass
class _Unit:
    """One function's worth of scopes, so shadowing is judged within a function."""

    scopes: list[dict[str, _Binding]] = field(default_factory=list)
    uses_this: bool = False


def _exempt(name: str) -> bool:
    # the established way to say a binding is deliberate and not meant to be read
    return name.startswith("_")


class Analyzer:
    def __init__(self) -> None:
        self._diagnostics: list[Diagnostic] = []
        self._units: list[_Unit] = []

    def analyze(self, statements: list[s.Stmt]) -> list[Diagnostic]:
        self._diagnostics = []
        self._units = [_Unit(scopes=[{}])]
        self._body(tuple(statements))
        self._close_scope()
        self._units.pop()
        return sorted(self._diagnostics, key=lambda found: (found.line, found.kind))

    def _report(self, kind: str, line: int, message: str) -> None:
        self._diagnostics.append(Diagnostic(kind, line, message))

    @property
    def _unit(self) -> _Unit:
        return self._units[-1]

    def _open_scope(self) -> None:
        self._unit.scopes.append({})

    def _close_scope(self) -> None:
        for binding in self._unit.scopes.pop().values():
            if binding.reads or _exempt(binding.name):
                continue
            if binding.is_parameter:
                self._report(
                    UNUSED_PARAMETER,
                    binding.line,
                    f"the parameter {binding.name!r} is never read; prefix it with an "
                    "underscore if it exists only to fill a position",
                )
            else:
                self._report(
                    UNUSED_LOCAL,
                    binding.line,
                    f"the local {binding.name!r} is never read; remove it or prefix it "
                    "with an underscore",
                )

    def _declare(self, name: str, line: int, is_parameter: bool = False) -> None:
        for enclosing in self._unit.scopes[:-1]:
            if name in enclosing and not _exempt(name):
                self._report(
                    SHADOWED,
                    line,
                    f"the name {name!r} hides another declared on line "
                    f"{enclosing[name].line} in the same function",
                )
                break
        self._unit.scopes[-1][name] = _Binding(name, line, is_parameter=is_parameter)

    def _mark_read(self, name: str) -> None:
        # the search walks outward through enclosing functions as well as scopes,
        # because a nested function may read a variable of the one containing it;
        # searching only the innermost function reported every captured variable
        # as unused, which was a false positive on every closure
        for unit in reversed(self._units):
            for scope in reversed(unit.scopes):
                if name in scope:
                    scope[name].reads += 1
                    return

    def _body(self, statements: tuple[s.Stmt, ...]) -> None:
        stopped_at: s.Stmt | None = None
        for statement in statements:
            if stopped_at is not None:
                line = _line_of_statement(statement)
                self._report(
                    UNREACHABLE,
                    line,
                    f"this cannot run, because the {_name_of(stopped_at)} above it "
                    "always leaves the block first",
                )
                stopped_at = None
            self._statement(statement)
            if isinstance(
                statement, (s.ReturnStmt, s.BreakStmt, s.ContinueStmt, s.ThrowStmt)
            ):
                stopped_at = statement

    def _statement(self, node: s.Stmt) -> None:
        if isinstance(node, (s.ExpressionStmt, s.PrintStmt)):
            self._expression(node.expression)
        elif isinstance(node, s.LetStmt):
            if node.initializer is not None:
                self._expression(node.initializer)
            self._declare(node.name.lexeme, node.name.line)
        elif isinstance(node, s.Block):
            self._open_scope()
            self._body(node.statements)
            self._close_scope()
        elif isinstance(node, s.IfStmt):
            self._condition(node.condition, "if")
            self._nested(node.then_branch, "if")
            if node.else_branch is not None:
                self._nested(node.else_branch, "else")
        elif isinstance(node, s.WhileStmt):
            self._condition(node.condition, "while", allow_true=True)
            self._nested(node.body, "while")
        elif isinstance(node, s.ForStmt):
            self._for(node)
        elif isinstance(node, s.ForEachStmt):
            self._expression(node.iterable)
            self._open_scope()
            self._declare(node.variable.lexeme, node.variable.line)
            self._nested(node.body, "for")
            self._close_scope()
        elif isinstance(node, s.FunctionStmt):
            self._declare(node.name.lexeme, node.name.line)
            self._mark_read(node.name.lexeme)
            self._function(node, is_method=False)
        elif isinstance(node, s.ClassStmt):
            self._class(node)
        elif isinstance(node, s.ReturnStmt):
            if node.value is not None:
                self._expression(node.value)
        elif isinstance(node, s.ThrowStmt):
            self._expression(node.value)
        elif isinstance(node, s.TryStmt):
            self._nested(node.body, "try")
            self._open_scope()
            self._declare(node.catch_name.lexeme, node.catch_name.line)
            self._nested(node.handler, "catch")
            self._close_scope()

    def _condition(self, node: e.Expr, where: str, allow_true: bool = False) -> None:
        self._expression(node)
        if not isinstance(node, e.Literal):
            return
        truth = is_truthy(node.value)
        if truth and allow_true:
            # while (true) is an idiom for a loop that breaks out, not a mistake
            return
        outcome = "always true" if truth else "never true"
        self._report(
            CONSTANT_CONDITION,
            _line_of_expression(node),
            f"the {where} condition is {outcome}, so the branch is decided before "
            "the program runs",
        )

    def _nested(self, body: s.Stmt, where: str) -> None:
        if isinstance(body, s.Block) and not body.statements:
            self._report(
                EMPTY_BODY,
                _line_of_statement(body),
                f"the {where} body is empty, so the construct has no effect",
            )
        self._statement(body)

    def _for(self, node: s.ForStmt) -> None:
        self._open_scope()
        if node.initializer is not None:
            self._statement(node.initializer)
        if node.condition is not None:
            self._condition(node.condition, "for", allow_true=True)
        if node.increment is not None:
            self._expression(node.increment)
        self._nested(node.body, "for")
        self._close_scope()

    def _function(self, node: s.FunctionStmt, is_method: bool) -> None:
        self._units.append(_Unit(scopes=[{}]))
        for parameter in node.parameters:
            self._declare(parameter.lexeme, parameter.line, is_parameter=True)
        self._body(node.body)
        uses_this = self._unit.uses_this
        self._close_scope()
        self._units.pop()
        if is_method and not uses_this and node.name.lexeme != "init":
            self._report(
                STATIC_METHOD,
                node.name.line,
                f"the method {node.name.lexeme!r} never mentions this, so it does not "
                "depend on the instance it was reached through",
            )

    def _class(self, node: s.ClassStmt) -> None:
        self._declare(node.name.lexeme, node.name.line)
        self._mark_read(node.name.lexeme)
        if node.superclass is not None:
            self._mark_read(node.superclass.lexeme)
        for method in node.methods:
            self._function(method, is_method=True)

    def _expression(self, node: e.Expr) -> None:
        if isinstance(node, e.Variable):
            self._mark_read(node.name.lexeme)
        elif isinstance(node, e.This):
            for unit in self._units:
                unit.uses_this = True
        elif isinstance(node, e.Super):
            self._unit.uses_this = True
        elif isinstance(node, e.Assign):
            self._expression(node.value)
            same = (
                isinstance(node.value, e.Variable)
                and node.value.name.lexeme == node.name.lexeme
            )
            if same:
                self._report(
                    SELF_ASSIGNMENT,
                    node.name.line,
                    f"{node.name.lexeme!r} is assigned to itself, which changes nothing",
                )
            # a write is deliberately not a read, so a variable only ever written
            # is still reported as unused
        elif isinstance(node, e.Interpolation):
            for kind, value in node.parts:
                if kind != "text":
                    self._expression(value)
        elif isinstance(node, e.Unary):
            self._expression(node.operand)
        elif isinstance(node, (e.Binary, e.Logical)):
            self._expression(node.left)
            self._expression(node.right)
        elif isinstance(node, e.Conditional):
            self._expression(node.condition)
            self._expression(node.when_true)
            self._expression(node.when_false)
        elif isinstance(node, e.Grouping):
            self._expression(node.inner)
        elif isinstance(node, e.Call):
            self._expression(node.callee)
            for argument in node.arguments:
                self._expression(argument)
        elif isinstance(node, e.Index):
            self._expression(node.collection)
            self._expression(node.key)
        elif isinstance(node, e.SetIndex):
            self._expression(node.collection)
            self._expression(node.key)
            self._expression(node.value)
        elif isinstance(node, e.Get):
            self._expression(node.target)
        elif isinstance(node, e.Set):
            self._expression(node.target)
            self._expression(node.value)
        elif isinstance(node, e.ListLiteral):
            for element in node.elements:
                self._expression(element)
        elif isinstance(node, e.MapLiteral):
            for key, value in node.pairs:
                self._expression(key)
                self._expression(value)


def _name_of(node: s.Stmt) -> str:
    return {
        s.ReturnStmt: "return",
        s.BreakStmt: "break",
        s.ContinueStmt: "continue",
        s.ThrowStmt: "throw",
    }[type(node)]


def _line_of_statement(node: s.Stmt) -> int:
    for attribute in ("keyword", "name", "variable", "catch_name"):
        token = getattr(node, attribute, None)
        if token is not None and hasattr(token, "line"):
            return token.line
    for attribute in ("expression", "condition", "iterable", "value"):
        child = getattr(node, attribute, None)
        if child is not None:
            return _line_of_expression(child)
    if isinstance(node, s.Block) and node.statements:
        return _line_of_statement(node.statements[0])
    return 1


def _line_of_expression(node: e.Expr) -> int:
    candidates = (
        "token",
        "name",
        "operator",
        "paren",
        "bracket",
        "brace",
        "keyword",
        "question",
    )
    for attribute in candidates:
        token = getattr(node, attribute, None)
        if token is not None and hasattr(token, "line"):
            return token.line
    children = ("left", "inner", "target", "collection", "callee", "operand", "condition")
    for attribute in children:
        child = getattr(node, attribute, None)
        if child is not None:
            return _line_of_expression(child)
    return 1


def analyze(statements: list[s.Stmt]) -> list[Diagnostic]:
    return Analyzer().analyze(statements)
