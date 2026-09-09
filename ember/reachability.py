"""What a running program is holding onto, found by tracing rather than by collecting.

This is the mark half of a mark and sweep collector with no sweep, and the missing half is
deliberate rather than unfinished. The host language already collects, so a second collector
here would free nothing and could only get it wrong. What the mark phase produces on its own is
the interesting part anyway: the set of values a program can still reach, which answers the
question a program that grows without bound actually poses, which is not what is garbage but
what is still held and by what.

The roots are the same ones a collector would use. Every global, every value on the value stack,
every closure in a live call frame, and every upvalue that is still open. An open upvalue is a
root as an object rather than as a value, which took a correction: it names a stack slot rather
than holding anything, so only a closed upvalue leads anywhere, and the stack is already a root.
From those, the walk
follows what each value can lead to: a list's elements, a map's keys and values, a closure's
upvalues, an instance's fields and its class, a class's methods, and a function's constant pool,
which is how a nested function stays reachable. Following the constant pool matters and is easy
to forget: a function that is never called is still held by whatever holds the function that
could call it.

A subclass does not lead to its superclass, and that is a fact about this machine rather than an
omission here. Inheritance is implemented by copying the superclass's methods into the subclass
when the class is declared, so a subclass holds its own table and nothing points upwards. The
walk was written expecting a superclass link and there is none to follow: a superclass with no
other reference to it becomes unreachable once its subclass exists, which is correct for this
machine and would be wrong for one that resolved methods by walking a chain.

Cycles are handled the way any graph walk handles them, by remembering what has been seen, and
the identity of a value rather than its equality is what is remembered. Two equal lists are two
values, and a program holding both is holding twice as much, so counting them as one would
answer the wrong question. The identity is the host's, which is a detail that leaks slightly:
two small integers that are equal may be the same object in the host, so a count of reachable
numbers is an underestimate. Numbers are not what anyone is worried about holding, so the
underestimate is recorded here rather than worked around.

What this cannot see is anything the host holds outside the machine: a native function's own
state, or a value some part of the interpreter kept a reference to. A report from here is
therefore a lower bound on what is held, and its value is in the shape of the answer, which
object holds the large list, rather than in the exact total.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ember.builtins import install_builtins
from ember.classes import BoundMethod, EmberClass, Instance
from ember.closure import Closure, Upvalue
from ember.function import Function, NativeFunction
from ember.interpreter import build
from ember.valueops import type_name
from ember.vm import VM


@dataclass
class Report:
    """What was reachable, counted by kind, with the largest collections named."""

    counts: dict[str, int] = field(default_factory=dict)
    roots: int = 0
    biggest: list[tuple[str, int]] = field(default_factory=list)

    @property
    def total(self) -> int:
        return sum(self.counts.values())

    def of_kind(self, kind: str) -> int:
        return self.counts.get(kind, 0)

    def kinds(self) -> list[str]:
        return sorted(self.counts)

    def render(self) -> list[str]:
        lines = [f"{self.total} values reachable from {self.roots} roots"]
        for kind in self.kinds():
            lines.append(f"  {self.counts[kind]} {kind}")
        for what, size in self.biggest:
            lines.append(f"the largest {what} holds {size} entries")
        return lines

    def summary(self) -> str:
        return f"{self.total} reachable"


def _roots_of(machine: VM) -> list[Any]:
    """Every value a collector would start from, which is every value in use."""
    found: list[Any] = list(machine.globals.values())
    found.extend(machine.stack)
    for frame in machine.frames:
        found.append(frame.closure)
    # the open upvalues are roots as objects, not as values: an open one points at a
    # stack slot, and the stack is already a root, so nothing is reached twice
    found.extend(machine.open_upvalues)
    return found


def _children_of(value: Any) -> list[Any]:
    """Everything one value can lead to, which is what makes the walk a graph walk."""
    if isinstance(value, list):
        return list(value)
    if isinstance(value, dict):
        return [*value.keys(), *value.values()]
    if isinstance(value, Closure):
        # the function is followed too, which is how a nested function stays reachable
        return [value.function, *value.upvalues]
    if isinstance(value, Upvalue):
        # only a closed upvalue holds anything: an open one names a stack slot, which
        # the stack itself already leads to, and reading it here would need the stack
        return [value.closed_value] if value.is_closed else []
    if isinstance(value, Function):
        return list(value.chunk.constants)
    if isinstance(value, Instance):
        return [value.klass, *value.fields.values()]
    if isinstance(value, EmberClass):
        # no superclass link: this machine copies methods down when a class is
        # declared, so nothing about a subclass points at what it inherited from
        return list(value.methods.values())
    if isinstance(value, BoundMethod):
        return [value.receiver, value.method]
    return []


def _kind_of(value: Any) -> str:
    if isinstance(value, Closure):
        return "closure"
    if isinstance(value, Upvalue):
        return "upvalue"
    if isinstance(value, Function):
        return "function"
    if isinstance(value, NativeFunction):
        return "native"
    if isinstance(value, Instance):
        return "instance"
    if isinstance(value, EmberClass):
        return "class"
    if isinstance(value, BoundMethod):
        return "method"
    return type_name(value)


def reachable(machine: VM) -> dict[int, Any]:
    """Every value the machine can still reach, keyed by identity rather than equality."""
    seen: dict[int, Any] = {}
    pending = _roots_of(machine)
    while pending:
        value = pending.pop()
        # identity, because two equal lists are two values and a program holding both
        # is holding twice as much
        marker = id(value)
        if marker in seen:
            continue
        seen[marker] = value
        pending.extend(_children_of(value))
    return seen


def report_of(machine: VM, largest: int = 3) -> Report:
    found = reachable(machine)
    counts: dict[str, int] = {}
    sized: list[tuple[str, int]] = []
    for value in found.values():
        kind = _kind_of(value)
        counts[kind] = counts.get(kind, 0) + 1
        if isinstance(value, (list, dict)):
            sized.append((kind, len(value)))
    sized.sort(key=lambda pair: -pair[1])
    return Report(
        counts=counts,
        roots=len(_roots_of(machine)),
        biggest=sized[:largest],
    )


def after_running(source: str, optimize: bool = False) -> Report:
    """Run a program, then report what it is still holding when it finishes."""
    machine = VM()
    install_builtins(machine)
    machine.interpret(build(source, optimize=optimize))
    return report_of(machine)


def held_by_globals(machine: VM) -> dict[str, int]:
    """How much each global name leads to, which says where a growing program grows."""
    found: dict[str, int] = {}
    for name, value in machine.globals.items():
        seen: dict[int, Any] = {}
        pending = [value]
        while pending:
            one = pending.pop()
            if id(one) in seen:
                continue
            seen[id(one)] = one
            pending.extend(_children_of(one))
        found[name] = len(seen)
    return found


def largest_holders(machine: VM, count: int = 5) -> list[tuple[str, int]]:
    held = held_by_globals(machine)
    return sorted(held.items(), key=lambda pair: (-pair[1], pair[0]))[:count]
