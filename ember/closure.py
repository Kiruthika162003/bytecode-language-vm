"""Closures and upvalues: let a function outlive the scope whose variables it still uses.

A function that mentions a variable from an enclosing function poses a
lifetime problem for a stack machine. The enclosing call's locals live in
a window of the value stack that disappears when that call returns, yet
the inner function may still be holding a reference and may be called
long afterwards. The classic answer, and the one here, is the upvalue: an
indirection standing between the closure and the variable, which starts
out pointing at the live stack slot and is later closed, meaning the
value is copied into the upvalue itself when the slot is about to vanish.
While the slot is alive an upvalue is open, and reads and writes go
straight through to the stack, so the inner function and the enclosing
one genuinely share one variable rather than a copy; once closed, the
upvalue owns the value and the closure keeps working with no stack behind
it. The sharing is why open upvalues must be interned by slot: two
closures capturing the same variable have to receive the same upvalue
object, or each would end up with its own copy and assignments through
one would be invisible to the other. A Closure pairs a compiled function
with the vector of upvalues captured where it was created, so the same
compiled body can be instantiated many times over different captured
state, which is exactly what makes a counter factory produce independent
counters. The honest cost of this design is the indirection itself: every
captured-variable access pays a hop that a plain local does not, which is
the price of letting a variable outlive its frame.
"""

from __future__ import annotations

from typing import Any

from ember.function import Function


class Upvalue:
    """One captured variable, open onto a stack slot or closed over a value."""

    __slots__ = ("closed_value", "is_closed", "location")

    def __init__(self, location: int) -> None:
        self.location = location
        self.is_closed = False
        self.closed_value: Any = None

    def get(self, stack: list[Any]) -> Any:
        if self.is_closed:
            return self.closed_value
        return stack[self.location]

    def set(self, stack: list[Any], value: Any) -> None:
        if self.is_closed:
            self.closed_value = value
        else:
            stack[self.location] = value

    def close(self, stack: list[Any]) -> None:
        if not self.is_closed:
            self.closed_value = stack[self.location]
            self.is_closed = True

    def __repr__(self) -> str:
        state = "closed" if self.is_closed else f"open at {self.location}"
        return f"<upvalue {state}>"


class Closure:
    """A compiled function paired with the upvalues captured where it was made."""

    __slots__ = ("function", "upvalues")

    def __init__(self, function: Function, upvalues: list[Upvalue] | None = None) -> None:
        self.function = function
        self.upvalues: list[Upvalue] = upvalues if upvalues is not None else []

    @property
    def name(self) -> str:
        return self.function.name

    @property
    def arity(self) -> int:
        return self.function.arity

    def __repr__(self) -> str:
        label = self.function.name if self.function.name else "<script>"
        return f"<fn {label}>"
