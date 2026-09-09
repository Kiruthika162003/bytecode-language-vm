"""Type checking without type annotations: find the definite mistakes, claim nothing more.

This language has no way to write a type down, so there is no type system here to check
a program against. What there is instead is inference from the shapes that are visible
in the source, and a rule about what to do with everything else. A literal has a known
type. An operator's result follows from its operands when both are known. A variable
initialised from a known expression and never reassigned to something of another type
keeps that type. Everything else, and that includes every function parameter, is
unknown, and an operation involving an unknown is never reported.

That rule is what makes the checker useful rather than noisy, and it is also the honest
limit of what it can do. Reporting only definite mistakes means every finding is a real
error: subtracting from a string, comparing a number with a string, calling something
that is not a function, indexing a boolean. It also means the checker is silent about
most function bodies, because a parameter's type is unknown, so a function that
subtracts one from its argument is unchecked no matter how it is called. A checker that
guessed at parameter types from call sites would find more, and would also report
mistakes that are not there in any program that calls a function two different ways,
which is the point at which people stop reading the output.

So this is a finder of errors, not a prover of their absence. A clean report means
nothing definite was found, not that the program is type correct, and the difference is
recorded in the report itself rather than left to the reader's optimism.

Assignment is tracked exactly where it can be and given up on where it cannot, and
finding the boundary took two corrections. Reassigning a name in straight line code is
certain, so the name simply takes the new type, and a first version that merged the two
into unknown missed a variable reassigned to a string and then subtracted from, which is
about as definite a mistake as there is. Inside a branch or an arm of a match it is not
certain, because only one arm runs, so those forget every name their bodies assign. A
loop needed forgetting twice: once before the body, since a second pass sees what the
first left, and once after, because a version that forgot only beforehand then recorded
whatever the body assigned and so treated a loop that might never run as one that
certainly had. A union type would be more precise than forgetting, and the language has
no way to write one down, so forgetting is what there is.

The checker never refuses to run a program: it reports, and the program still runs,
because the runtime already produces a precise error at the exact moment of the fault,
and a static checker that blocked programs the runtime handles correctly would be taking
away a working feature.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ember import exprnodes as e
from ember import stmtnodes as s
from ember.parser import parse
from ember.scanner import scan
from ember.tokenkind import TokenKind

UNKNOWN = "unknown"
NUMBER = "number"
STRING = "string"
BOOL = "bool"
NIL = "nil"
LIST = "list"
MAP = "map"
FUNCTION = "function"

# operators that need two numbers and give a number
_ARITHMETIC = (
    TokenKind.MINUS,
    TokenKind.STAR,
    TokenKind.SLASH,
    TokenKind.PERCENT,
)
_BITWISE = (
    TokenKind.AMPERSAND,
    TokenKind.PIPE,
    TokenKind.CARET,
    TokenKind.LESS_LESS,
    TokenKind.GREATER_GREATER,
)
# operators that need two of the same ordered type and give a bool
_ORDERING = (
    TokenKind.LESS,
    TokenKind.LESS_EQUAL,
    TokenKind.GREATER,
    TokenKind.GREATER_EQUAL,
)
_EQUALITY = (TokenKind.EQUAL_EQUAL, TokenKind.BANG_EQUAL)

_ORDERABLE = (NUMBER, STRING)


@dataclass(frozen=True)
class Finding:
    """One definite mistake, with the line and what would go wrong."""

    line: int
    kind: str
    message: str

    def render(self) -> str:
        return f"line {self.line}: {self.kind}: {self.message}"


@dataclass
class Scope:
    """What is known about the names in one scope."""

    types: dict[str, str] = field(default_factory=dict)
    arities: dict[str, tuple[int, int]] = field(default_factory=dict)

    def forget(self, name: str) -> None:
        # a name whose type stopped being certain is unknown, not wrong
        self.types[name] = UNKNOWN


class Checker:
    def __init__(self) -> None:
        self.findings: list[Finding] = []
        self._scopes: list[Scope] = [Scope()]

    def _report(self, line: int, kind: str, message: str) -> None:
        self.findings.append(Finding(line=line, kind=kind, message=message))

    def _known(self, name: str) -> str:
        for scope in reversed(self._scopes):
            if name in scope.types:
                return scope.types[name]
        return UNKNOWN

    def _arity_of(self, name: str) -> tuple[int, int] | None:
        for scope in reversed(self._scopes):
            if name in scope.arities:
                return scope.arities[name]
        return None

    def _declare(self, name: str, kind: str) -> None:
        self._scopes[-1].types[name] = kind

    def _assign(self, name: str, kind: str) -> None:
        # in straight line code an assignment is exact: whatever the name held before,
        # it holds this now. Branches and loops are where that stops being true, and
        # each forgets the names it touches rather than this doing so for them.
        for scope in reversed(self._scopes):
            if name in scope.types:
                scope.types[name] = kind
                return
        self._declare(name, kind)

    def _forget_assigned(self, *bodies) -> None:
        """Make every name these statements assign unknown, since either arm may run."""
        for name in _assigned_in(*bodies):
            for scope in reversed(self._scopes):
                if name in scope.types:
                    scope.forget(name)
                    break

    # statements

    def check_all(self, statements: list[s.Stmt]) -> None:
        for statement in statements:
            self.check(statement)

    def check(self, node: s.Stmt) -> None:
        """Dispatch one statement to whichever handler knows its shape.

        This is a table rather than a chain of type tests because the chain grew past
        the point where a reader could see the whole of it at once.
        """
        for kind, handler in self._handlers():
            if isinstance(node, kind):
                handler(node)
                return

    def _handlers(self):
        return (
            (s.LetStmt, self._let),
            ((s.ExpressionStmt, s.PrintStmt), self._bare_expression),
            (s.Block, self._nested_block),
            (s.IfStmt, self._if),
            (s.WhileStmt, self._while),
            (s.ForStmt, self._for),
            (s.ForEachStmt, self._for_each),
            (s.FunctionStmt, self._function),
            (s.ClassStmt, self._class),
            (s.ReturnStmt, self._return),
            (s.ThrowStmt, self._throw),
            (s.TryStmt, self._try),
            (s.MatchStmt, self._match),
        )

    def _let(self, node: s.LetStmt) -> None:
        has_value = node.initializer is not None
        self._declare(node.name.lexeme, self.type_of(node.initializer) if has_value else NIL)

    def _bare_expression(self, node: s.ExpressionStmt | s.PrintStmt) -> None:
        self.type_of(node.expression)

    def _nested_block(self, node: s.Block) -> None:
        self._scopes.append(Scope())
        self.check_all(list(node.statements))
        self._scopes.pop()

    def _if(self, node: s.IfStmt) -> None:
        self.type_of(node.condition)
        self._check_branches(node.then_branch, node.else_branch)

    def _while(self, node: s.WhileStmt) -> None:
        self.type_of(node.condition)
        self._check_loop(node.body)

    def _for(self, node: s.ForStmt) -> None:
        self._scopes.append(Scope())
        if node.initializer is not None:
            self.check(node.initializer)
        if node.condition is not None:
            self.type_of(node.condition)
        if node.increment is not None:
            self.type_of(node.increment)
        self._check_loop(node.body)
        self._scopes.pop()

    def _for_each(self, node: s.ForEachStmt) -> None:
        self.type_of(node.iterable)
        self._scopes.append(Scope())
        # the element type of a list is not tracked, so the variable is unknown
        self._declare(node.variable.lexeme, UNKNOWN)
        self._check_loop(node.body)
        self._scopes.pop()

    def _class(self, node: s.ClassStmt) -> None:
        self._declare(node.name.lexeme, FUNCTION)
        self._scopes[-1].arities[node.name.lexeme] = self._initializer_arity(node)
        for method in node.methods:
            self._function(method, register=False)

    def _return(self, node: s.ReturnStmt) -> None:
        if node.value is not None:
            self.type_of(node.value)

    def _throw(self, node: s.ThrowStmt) -> None:
        self.type_of(node.value)

    def _try(self, node: s.TryStmt) -> None:
        self.check(node.body)
        self._scopes.append(Scope())
        # whatever was thrown could be any value, so the caught name is unknown
        self._declare(node.catch_name.lexeme, UNKNOWN)
        self.check(node.handler)
        self._scopes.pop()
        self._forget_assigned(node.body, node.handler)

    def _match(self, node: s.MatchStmt) -> None:
        self.type_of(node.subject)
        for case in node.cases:
            for value in case.values:
                self.type_of(value)
            self.check(case.body)
        if node.default is not None:
            self.check(node.default)
        bodies = [case.body for case in node.cases]
        if node.default is not None:
            bodies.append(node.default)
        # only one arm runs, so a name any arm assigns is uncertain afterwards
        self._forget_assigned(*bodies)

    def _check_branches(self, then_branch: s.Stmt, else_branch: s.Stmt | None) -> None:
        self.check(then_branch)
        if else_branch is not None:
            self.check(else_branch)
        # a name assigned in one arm may hold either type once the arms rejoin, and a
        # union is not something this language can express, so it becomes unknown
        self._forget_assigned(then_branch, else_branch)

    def _check_loop(self, body: s.Stmt) -> None:
        # A loop body runs an unknown number of times, so a name it assigns cannot be
        # trusted inside the body, because the second pass sees what the first left.
        # It cannot be trusted afterwards either, and forgetting only beforehand was
        # not enough: checking the body then recorded the type the body assigned, so a
        # loop that might never run appeared to have certainly run.
        self._forget_assigned(body)
        self.check(body)
        self._forget_assigned(body)

    @staticmethod
    def _initializer_arity(node: s.ClassStmt) -> tuple[int, int]:
        for method in node.methods:
            if method.name.lexeme == "init":
                return Checker._arity_bounds(method)
        return (0, 0)

    @staticmethod
    def _arity_bounds(node: s.FunctionStmt) -> tuple[int, int]:
        total = len(node.parameters)
        named = total - 1 if node.is_variadic else total
        lowest = named - len(node.defaults)
        highest = -1 if node.is_variadic else named
        return (lowest, highest)

    def _function(self, node: s.FunctionStmt, register: bool = True) -> None:
        if register:
            self._declare(node.name.lexeme, FUNCTION)
            self._scopes[-1].arities[node.name.lexeme] = self._arity_bounds(node)
        self._scopes.append(Scope())
        for parameter in node.parameters:
            # a parameter has no declared type, which is why most bodies go unchecked
            self._declare(parameter.lexeme, UNKNOWN)
        self.check_all(list(node.body))
        self._scopes.pop()

    # expressions

    def type_of(self, node: e.Expr) -> str:
        if isinstance(node, e.Literal):
            return self._literal_type(node)
        if isinstance(node, e.Interpolation):
            for part in node.parts:
                for piece in part:
                    if isinstance(piece, e.Expr):
                        self.type_of(piece)
            return STRING
        if isinstance(node, e.Variable):
            return self._known(node.name.lexeme)
        if isinstance(node, e.Grouping):
            return self.type_of(node.inner)
        if isinstance(node, e.Unary):
            return self._unary(node)
        if isinstance(node, (e.Binary, e.Logical)):
            return self._binary(node)
        if isinstance(node, e.Conditional):
            self.type_of(node.condition)
            when_true = self.type_of(node.when_true)
            when_false = self.type_of(node.when_false)
            return when_true if when_true == when_false else UNKNOWN
        if isinstance(node, e.Assign):
            kind = self.type_of(node.value)
            self._assign(node.name.lexeme, kind)
            return kind
        if isinstance(node, e.Call):
            return self._call(node)
        if isinstance(node, e.Index):
            return self._index(node)
        if isinstance(node, e.SetIndex):
            self._index(e.Index(node.collection, node.bracket, node.key))
            return self.type_of(node.value)
        if isinstance(node, e.ListLiteral):
            for element in node.elements:
                self.type_of(element)
            return LIST
        if isinstance(node, e.MapLiteral):
            for key, value in node.pairs:
                self.type_of(key)
                self.type_of(value)
            return MAP
        if isinstance(node, e.Get):
            self.type_of(node.target)
            return UNKNOWN
        if isinstance(node, e.Set):
            self.type_of(node.target)
            return self.type_of(node.value)
        return UNKNOWN

    @staticmethod
    def _literal_type(node: e.Literal) -> str:
        value = node.token.literal
        if node.token.kind == TokenKind.NIL:
            return NIL
        if node.token.kind in (TokenKind.TRUE, TokenKind.FALSE):
            return BOOL
        if isinstance(value, bool):
            return BOOL
        if isinstance(value, (int, float)):
            return NUMBER
        if isinstance(value, str):
            return STRING
        return UNKNOWN

    def _unary(self, node: e.Unary) -> str:
        inner = self.type_of(node.operand)
        line = node.operator.span.start.line
        if node.operator.kind == TokenKind.BANG:
            return BOOL
        if node.operator.kind in (TokenKind.MINUS, TokenKind.TILDE):
            if inner not in (UNKNOWN, NUMBER):
                self._report(
                    line,
                    "not-a-number",
                    f"{node.operator.lexeme} needs a number, and this operand is "
                    f"a {inner}",
                )
            return NUMBER
        return UNKNOWN

    def _binary(self, node: e.Binary | e.Logical) -> str:
        left = self.type_of(node.left)
        right = self.type_of(node.right)
        kind = node.operator.kind
        line = node.operator.span.start.line
        if isinstance(node, e.Logical):
            # either operand can be any type, since truthiness is defined for all
            return UNKNOWN if left != right else left
        if kind == TokenKind.PLUS:
            return self._plus(left, right, line)
        if kind in _ARITHMETIC or kind in _BITWISE:
            for side, found in (("left", left), ("right", right)):
                if found not in (UNKNOWN, NUMBER):
                    self._report(
                        line,
                        "not-a-number",
                        f"{node.operator.lexeme} needs numbers, and its {side} "
                        f"operand is a {found}",
                    )
            return NUMBER
        if kind in _ORDERING:
            self._check_ordering(left, right, node.operator.lexeme, line)
            return BOOL
        if kind in _EQUALITY:
            self._check_equality(left, right, node.operator.lexeme, line)
            return BOOL
        return UNKNOWN

    def _plus(self, left: str, right: str, line: int) -> str:
        """Addition joins two numbers or two strings, and nothing else."""
        if UNKNOWN in (left, right):
            return UNKNOWN
        if left == right == NUMBER:
            return NUMBER
        if left == right == STRING:
            return STRING
        if left == right == LIST:
            return LIST
        self._report(
            line,
            "cannot-add",
            f"a {left} and a {right} cannot be added; addition joins two numbers, "
            "two strings, or two lists",
        )
        return UNKNOWN

    def _check_ordering(self, left: str, right: str, operator: str, line: int) -> None:
        if UNKNOWN in (left, right):
            return
        if left != right:
            self._report(
                line,
                "cannot-compare",
                f"{operator} compares two values of one kind, and this compares a "
                f"{left} with a {right}",
            )
            return
        if left not in _ORDERABLE:
            self._report(
                line,
                "not-orderable",
                f"{operator} needs values with an order, and a {left} has none",
            )

    def _check_equality(self, left: str, right: str, operator: str, line: int) -> None:
        if UNKNOWN in (left, right) or left == right:
            return
        if NIL in (left, right):
            # comparing anything with nil is how a program asks whether it is nil
            return
        self._report(
            line,
            "never-equal",
            f"a {left} and a {right} are never equal, so {operator} always gives the "
            "same answer",
        )

    def _call(self, node: e.Call) -> str:
        callee = self.type_of(node.callee)
        line = node.paren.span.start.line
        for argument in node.arguments:
            self.type_of(argument)
        if callee not in (UNKNOWN, FUNCTION):
            self._report(
                line,
                "not-callable",
                f"a {callee} cannot be called; only a function or a class can",
            )
            return UNKNOWN
        if isinstance(node.callee, e.Variable):
            self._check_arity(node.callee.name.lexeme, len(node.arguments), line)
        return UNKNOWN

    def _check_arity(self, name: str, given: int, line: int) -> None:
        bounds = self._arity_of(name)
        if bounds is None:
            return
        lowest, highest = bounds
        if given < lowest or (highest >= 0 and given > highest):
            self._report(
                line,
                "wrong-arity",
                f"{name} takes {self._wanted(lowest, highest)}, and this call "
                f"passes {given}",
            )

    @staticmethod
    def _wanted(lowest: int, highest: int) -> str:
        """How many arguments a function takes, worded so it reads as a sentence."""
        if highest < 0:
            noun = "argument" if lowest == 1 else "arguments"
            return f"at least {lowest} {noun}"
        if lowest == highest:
            noun = "argument" if lowest == 1 else "arguments"
            return f"{lowest} {noun}"
        return f"{lowest} to {highest} arguments"

    def _index(self, node: e.Index) -> str:
        collection = self.type_of(node.collection)
        key = self.type_of(node.key)
        line = node.bracket.span.start.line
        if collection not in (UNKNOWN, LIST, MAP, STRING):
            self._report(
                line,
                "not-indexable",
                f"a {collection} cannot be indexed; only a list, a map or a string can",
            )
            return UNKNOWN
        if collection in (LIST, STRING) and key not in (UNKNOWN, NUMBER):
            self._report(
                line,
                "bad-index",
                f"a {collection} is indexed by a number, and this index is a {key}",
            )
        return UNKNOWN


def _assigned_in(*nodes) -> set[str]:
    """Every name these statements assign to, following into nested statements."""
    found: set[str] = set()
    for node in nodes:
        if node is not None:
            _gather_assigned(node, found)
    return found


def _gather_assigned(node: s.Stmt, found: set[str]) -> None:
    if isinstance(node, (s.ExpressionStmt, s.PrintStmt)):
        _gather_expression(node.expression, found)
    elif isinstance(node, s.Block):
        for inner in node.statements:
            _gather_assigned(inner, found)
    elif isinstance(node, s.IfStmt):
        _gather_expression(node.condition, found)
        _gather_assigned(node.then_branch, found)
        if node.else_branch is not None:
            _gather_assigned(node.else_branch, found)
    elif isinstance(node, s.WhileStmt):
        _gather_expression(node.condition, found)
        _gather_assigned(node.body, found)
    elif isinstance(node, s.ForStmt):
        if node.initializer is not None:
            _gather_assigned(node.initializer, found)
        if node.condition is not None:
            _gather_expression(node.condition, found)
        if node.increment is not None:
            _gather_expression(node.increment, found)
        _gather_assigned(node.body, found)
    elif isinstance(node, s.ForEachStmt):
        _gather_expression(node.iterable, found)
        _gather_assigned(node.body, found)
    elif isinstance(node, s.TryStmt):
        _gather_assigned(node.body, found)
        _gather_assigned(node.handler, found)
    elif isinstance(node, s.MatchStmt):
        for case in node.cases:
            _gather_assigned(case.body, found)
        if node.default is not None:
            _gather_assigned(node.default, found)
    elif isinstance(node, s.LetStmt):
        if node.initializer is not None:
            _gather_expression(node.initializer, found)
    elif isinstance(node, s.ReturnStmt):
        if node.value is not None:
            _gather_expression(node.value, found)
    elif isinstance(node, s.ThrowStmt):
        _gather_expression(node.value, found)


_CHILD_FIELDS = (
    "left",
    "right",
    "operand",
    "inner",
    "condition",
    "when_true",
    "when_false",
    "value",
    "target",
    "collection",
    "key",
    "callee",
)


def _gather_expression(node: e.Expr, found: set[str]) -> None:
    if isinstance(node, e.Assign):
        found.add(node.name.lexeme)
    for name in _CHILD_FIELDS:
        child = getattr(node, name, None)
        if isinstance(child, e.Expr):
            _gather_expression(child, found)
    for name in ("elements", "arguments"):
        listed = getattr(node, name, None)
        if isinstance(listed, (list, tuple)):
            for entry in listed:
                if isinstance(entry, e.Expr):
                    _gather_expression(entry, found)
    for name in ("pairs", "parts"):
        listed = getattr(node, name, None)
        if isinstance(listed, (list, tuple)):
            for entry in listed:
                if isinstance(entry, tuple):
                    for piece in entry:
                        if isinstance(piece, e.Expr):
                            _gather_expression(piece, found)


def check(source: str) -> list[Finding]:
    """Every definite type mistake in a program, in source order."""
    checker = Checker()
    checker.check_all(list(parse(scan(source))))
    return sorted(checker.findings, key=lambda found: (found.line, found.kind))


def report(source: str) -> list[str]:
    found = check(source)
    if not found:
        # the honest phrasing: nothing definite was found, which is not a proof
        return ["no definite type mistakes found, which is not a proof there are none"]
    lines = [one.render() for one in found]
    noun = "mistake" if len(found) == 1 else "mistakes"
    lines.append(f"{len(found)} definite {noun}")
    return lines


def is_clean(source: str) -> bool:
    return not check(source)
