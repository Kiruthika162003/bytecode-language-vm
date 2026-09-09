"""The call graph: which functions call which, and what that reveals.

Knowing who calls whom answers questions the other analyses cannot. Which functions
are never called from anywhere, so are dead weight in the program rather than dead
code inside a function. Which functions call themselves, directly or around a cycle,
so cannot be inlined without a depth limit. How deep the calls can nest, which bounds
how much frame space a run could need. All three come from one walk of the syntax
tree, gathering the names each function body mentions in call position.

The graph is built from names rather than from values, and that is the limitation that
governs everything here. A call whose callee is an expression rather than a name, a
closure returned from another function and then called, or a method reached through an
instance, cannot be attributed to a definition by reading the source: knowing which
function runs would need to know what the expression evaluates to, which is the
program running. So an edge exists when a function body mentions another function's
name in call position, and calls through values are counted separately and reported as
such. This means the unreachable set is a set of functions unreachable through named
calls, which is a weaker claim than unreachable, and it is stated that way rather than
implied to be stronger. A function called only through a closure will appear unused,
and the report says how many indirect calls the program makes so a reader can judge
how much to trust the list.

Recursion detection is exact for what it can see. A cycle in the named graph is real
recursion, found by depth first search, and both the direct case of a function naming
itself and the mutual case of two functions naming each other are reported the same
way, because they have the same consequence for anything that wants to expand a call.
The depth figure is the longest chain through the graph and is only computed when
there is no cycle, since a cycle makes the longest chain unbounded, and reporting a
number there would be inventing one.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ember import exprnodes as e
from ember import stmtnodes as s
from ember.parser import parse
from ember.scanner import scan

_SCRIPT = "<script>"


@dataclass
class Graph:
    """Every named function and the names each one calls."""

    calls: dict[str, set[str]] = field(default_factory=dict)
    indirect: dict[str, int] = field(default_factory=dict)

    @property
    def names(self) -> list[str]:
        return sorted(self.calls)

    @property
    def indirect_total(self) -> int:
        return sum(self.indirect.values())

    def callers_of(self, name: str) -> list[str]:
        return sorted(who for who, called in self.calls.items() if name in called)

    def called_by(self, name: str) -> list[str]:
        return sorted(self.calls.get(name, set()))

    def describe(self) -> list[str]:
        lines = []
        for name in self.names:
            called = ", ".join(self.called_by(name)) or "nothing"
            lines.append(f"{name} calls {called}")
        return lines


class _Walker:
    """Gathers the names a function body calls, following nested functions."""

    def __init__(self) -> None:
        self.graph = Graph()
        self._where: list[str] = [_SCRIPT]
        self.graph.calls[_SCRIPT] = set()
        self.graph.indirect[_SCRIPT] = 0

    def _here(self) -> str:
        return self._where[-1]

    def _enter(self, name: str) -> None:
        self._where.append(name)
        self.graph.calls.setdefault(name, set())
        self.graph.indirect.setdefault(name, 0)

    def _leave(self) -> None:
        self._where.pop()

    def statements(self, listed: list[s.Stmt]) -> None:
        for statement in listed:
            self.statement(statement)

    def statement(self, node: s.Stmt) -> None:
        if isinstance(node, s.FunctionStmt):
            self._enter(node.name.lexeme)
            for default in node.defaults:
                if isinstance(default, e.Expr):
                    self.expression(default)
            self.statements(list(node.body))
            self._leave()
        elif isinstance(node, s.ClassStmt):
            for method in node.methods:
                # a method is named for its class so two classes may share a method name
                self._enter(f"{node.name.lexeme}.{method.name.lexeme}")
                self.statements(list(method.body))
                self._leave()
        elif isinstance(node, s.Block):
            self.statements(list(node.statements))
        elif isinstance(node, s.IfStmt):
            self.expression(node.condition)
            self.statement(node.then_branch)
            if node.else_branch is not None:
                self.statement(node.else_branch)
        elif isinstance(node, s.WhileStmt):
            self.expression(node.condition)
            self.statement(node.body)
        elif isinstance(node, s.ForStmt):
            if node.initializer is not None:
                self.statement(node.initializer)
            if node.condition is not None:
                self.expression(node.condition)
            if node.increment is not None:
                self.expression(node.increment)
            self.statement(node.body)
        elif isinstance(node, s.ForEachStmt):
            self.expression(node.iterable)
            self.statement(node.body)
        elif isinstance(node, s.TryStmt):
            self.statement(node.body)
            self.statement(node.handler)
        elif isinstance(node, s.MatchStmt):
            self.expression(node.subject)
            for case in node.cases:
                for value in case.values:
                    self.expression(value)
                self.statement(case.body)
            if node.default is not None:
                self.statement(node.default)
        elif isinstance(node, (s.ExpressionStmt, s.PrintStmt)):
            self.expression(node.expression)
        elif isinstance(node, s.LetStmt):
            if node.initializer is not None:
                self.expression(node.initializer)
        elif isinstance(node, s.ReturnStmt):
            if node.value is not None:
                self.expression(node.value)
        elif isinstance(node, s.ThrowStmt):
            self.expression(node.value)

    def expression(self, node: e.Expr) -> None:
        if isinstance(node, e.Call):
            if isinstance(node.callee, e.Variable):
                self.graph.calls[self._here()].add(node.callee.name.lexeme)
            elif isinstance(node.callee, e.Get):
                # a method reached through a value, whose class is not known here
                self.graph.indirect[self._here()] += 1
                self.expression(node.callee)
            else:
                self.graph.indirect[self._here()] += 1
                self.expression(node.callee)
            for argument in node.arguments:
                self.expression(argument)
            return
        for child in _children(node):
            self.expression(child)


def _children(node: e.Expr) -> list[e.Expr]:
    found: list[e.Expr] = []
    for name in (
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
    ):
        child = getattr(node, name, None)
        if isinstance(child, e.Expr):
            found.append(child)
    for name in ("elements", "arguments"):
        listed = getattr(node, name, None)
        if isinstance(listed, (list, tuple)):
            found.extend(entry for entry in listed if isinstance(entry, e.Expr))
    # a map's pairs and an interpolation's parts both hold tuples, so they are
    # flattened rather than read by a field name that only one of them has
    for name in ("pairs", "parts"):
        listed = getattr(node, name, None)
        if isinstance(listed, (list, tuple)):
            for entry in listed:
                if isinstance(entry, tuple):
                    found.extend(part for part in entry if isinstance(part, e.Expr))
    return found


def build_graph(source: str) -> Graph:
    walker = _Walker()
    walker.statements(list(parse(scan(source))))
    return walker.graph


def defined_functions(graph: Graph) -> list[str]:
    """Every function the program defines, which is everything but the script."""
    return [name for name in graph.names if name != _SCRIPT]


def reachable(graph: Graph, start: str = _SCRIPT) -> set[str]:
    """Every function reachable from the script through named calls."""
    seen = {start}
    pending = [start]
    while pending:
        current = pending.pop()
        for called in graph.calls.get(current, set()):
            if called not in seen and called in graph.calls:
                seen.add(called)
                pending.append(called)
    return seen


def never_called(graph: Graph) -> list[str]:
    """Functions no named call reaches, which is weaker than never called at all."""
    found = reachable(graph)
    return [name for name in defined_functions(graph) if name not in found]


def _cycles_from(graph: Graph, start: str) -> list[list[str]]:
    found: list[list[str]] = []
    path: list[str] = []
    walking: set[str] = set()

    def descend(name: str) -> None:
        if name in walking:
            # the path from where this name first appeared is the cycle
            begins = path.index(name)
            found.append([*path[begins:], name])
            return
        if name not in graph.calls:
            return
        walking.add(name)
        path.append(name)
        for called in sorted(graph.calls[name]):
            descend(called)
        path.pop()
        walking.discard(name)

    descend(start)
    return found


def recursive_functions(graph: Graph) -> list[str]:
    """Functions that can reach themselves, directly or around a cycle."""
    found: set[str] = set()
    for name in graph.calls:
        for cycle in _cycles_from(graph, name):
            found.update(cycle)
    return sorted(found)


def directly_recursive(graph: Graph) -> list[str]:
    return sorted(name for name, called in graph.calls.items() if name in called)


def has_cycle(graph: Graph) -> bool:
    return bool(recursive_functions(graph))


def deepest_chain(graph: Graph) -> int:
    """The longest chain of named calls, which only exists when nothing recurses."""
    if has_cycle(graph):
        # a cycle makes the longest chain unbounded, so there is no number to give
        return -1
    depths: dict[str, int] = {}

    def measure(name: str) -> int:
        if name in depths:
            return depths[name]
        called = [c for c in graph.calls.get(name, set()) if c in graph.calls]
        depths[name] = 1 + max((measure(c) for c in called), default=0)
        return depths[name]

    return max((measure(name) for name in graph.calls), default=0)


def report(source: str) -> list[str]:
    graph = build_graph(source)
    count = len(defined_functions(graph))
    lines = [f"{count} function{'' if count == 1 else 's'} defined"]
    unused = never_called(graph)
    if unused:
        lines.append("never reached by a named call: " + ", ".join(unused))
    recursive = recursive_functions(graph)
    if recursive:
        lines.append("can reach themselves: " + ", ".join(recursive))
    depth = deepest_chain(graph)
    if depth >= 0:
        lines.append(f"the longest chain of calls is {depth} deep")
    else:
        lines.append("the longest chain is unbounded, because something recurses")
    if graph.indirect_total:
        # so a reader can judge how much to trust the unreached list
        total = graph.indirect_total
        verb = "call goes" if total == 1 else "calls go"
        lines.append(
            f"{total} {verb} through a value rather than a name, "
            "and none of them appear as edges here"
        )
    return lines
