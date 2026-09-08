"""Local scopes: bind a name to a stack slot at compile time so the machine never looks it up.

A global variable is found at run time by name, a dictionary lookup on
every access, which is flexible but slow and late: a misspelled global is
only noticed when the line runs. A local variable can do far better,
because the compiler knows the exact position a local will occupy on the
value stack and can compile an access into a direct slot number, turning a
named lookup into an array index and catching an unknown name while
compiling. This module is the bookkeeping that makes that possible. It
tracks the locals currently in scope as a stack, each tagged with the
block depth at which it was declared, so that entering a block raises the
depth and leaving it pops every local declared at that depth, restoring
the slots for reuse. Resolving a name walks the stack from the top so
that an inner declaration shadows an outer one of the same name, which is
what block scoping means. Two rules are enforced here rather than left to
the compiler. Declaring the same name twice in one block is a resolution
error, because it is almost always a mistake and the alternative, silent
shadowing within a single scope, hides it. And the number of live locals
cannot exceed what a one-byte slot can address, so the two-hundred-fifty-
seventh simultaneously live local is refused, the same byte-width limit
the rest of the format lives within. Whether a local was declared
constant is tracked too, so the compiler can forbid assigning to it.
"""

from __future__ import annotations

from dataclasses import dataclass

from ember.errors import Compile, Resolve

_MAX_LOCALS = 256


@dataclass
class Local:
    name: str
    depth: int
    is_const: bool


class LocalScope:
    def __init__(self) -> None:
        self._locals: list[Local] = []
        self._depth = 0

    @property
    def depth(self) -> int:
        return self._depth

    @property
    def count(self) -> int:
        return len(self._locals)

    def begin_scope(self) -> None:
        self._depth += 1

    def end_scope(self) -> int:
        removed = 0
        while self._locals and self._locals[-1].depth == self._depth:
            self._locals.pop()
            removed += 1
        self._depth -= 1
        return removed

    def declare(self, name: str, is_const: bool = False) -> int:
        for local in reversed(self._locals):
            if local.depth < self._depth:
                break
            if local.name == name:
                raise Resolve(
                    f"the name {name!r} is already declared in this scope; "
                    "choose a different name or remove the earlier declaration"
                )
        if len(self._locals) >= _MAX_LOCALS:
            raise Compile(
                f"a function cannot have more than {_MAX_LOCALS} local variables "
                "in scope at once"
            )
        self._locals.append(Local(name, self._depth, is_const))
        return len(self._locals) - 1

    def declare_reserved(self) -> int:
        # slot 0 of every frame is reserved for the callee itself and cannot
        # be named, so it is declared with a name no source can produce
        if len(self._locals) >= _MAX_LOCALS:
            raise Compile("a function cannot reserve its callee slot; it is full")
        self._locals.append(Local("", self._depth, is_const=True))
        return len(self._locals) - 1

    def resolve(self, name: str) -> int | None:
        for index in range(len(self._locals) - 1, -1, -1):
            if self._locals[index].name == name and self._locals[index].name != "":
                return index
        return None

    def is_const(self, slot: int) -> bool:
        return self._locals[slot].is_const
