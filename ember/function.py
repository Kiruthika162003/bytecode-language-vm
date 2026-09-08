"""Callable values: a compiled function and a native function share one shape to the caller.

A program calls two very different things through the same syntax. Some
callables are written in Ember, compiled to a chunk of bytecode that the
machine will execute by pushing a new frame; others are written in the
host language, Python, and do their work by running host code directly,
which is how a program reaches facilities it could not implement itself,
like reading the clock or measuring a list. This module defines both and,
by giving them a common notion of a name and an arity, lets the call
instruction check the argument count the same way for either before
dispatching on which kind it actually is. A Function carries its name for
error messages, its arity so a wrong call is caught before it runs, and
the chunk that is its body. A NativeFunction carries a name, an arity,
and the host callable that implements it. Keeping arity on both is the
point: the check that a function received the number of arguments it
expects belongs to the calling convention, not to either implementation,
so doing it once against this shared field keeps the two kinds
interchangeable at the call site. The honest boundary is that a native
function runs outside the machine's control, so it can do anything the
host can, including failing in ways the machine cannot describe; the
runtime wraps the common mistakes but ultimately trusts native code to
behave, which is the price of an escape hatch to the host.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from ember.chunk import Chunk


@dataclass
class Function:
    name: str
    arity: int
    chunk: Chunk
    upvalue_count: int = 0

    def __repr__(self) -> str:
        label = self.name if self.name else "<script>"
        return f"<fn {label}>"


@dataclass
class NativeFunction:
    name: str
    arity: int
    handler: Callable[..., Any]
    needs_machine: bool = False

    def __repr__(self) -> str:
        return f"<native {self.name}>"
