"""Classes, instances, and bound methods: the three objects behind behaviour on data.

A class in this language is a value like any other, and it does two jobs.
Called like a function it manufactures a fresh instance, and consulted by
name it supplies the methods that instance responds to. An instance holds
its own fields, a plain mapping from name to value that a program may add
to at any time, and a link to the class it came from so that a name not
found among its fields can be looked for among the methods. That two-step
lookup, fields first and methods second, is the whole of property access,
and its order matters: a field shadows a method of the same name, which
lets an instance override behaviour with data, and the reverse order would
make it impossible to store a value under a name the class already used.
The third object is the one that is easy to overlook. A method reached
through an instance cannot be handed out as the bare function it was
compiled to, because it would then have no idea which instance it belongs
to; so property access wraps it in a bound method that remembers the
receiver, and calling that bound method feeds the receiver in as the
frame's own slot zero, which is exactly where the compiler arranged for
this to live. The honest cost is an allocation per method access, since
every time a method is fetched a fresh binding is made; a runtime that
cared would fuse the fetch and the call into one instruction so the
binding never has to exist, an optimisation this straightforward version
leaves on the table in exchange for a model that is easy to follow.
"""

from __future__ import annotations

from typing import Any

from ember.closure import Closure

INITIALIZER = "init"


class EmberClass:
    """A named collection of methods that can also be called to make instances."""

    __slots__ = ("methods", "name")

    def __init__(self, name: str) -> None:
        self.name = name
        self.methods: dict[str, Closure] = {}

    def find_method(self, name: str) -> Closure | None:
        return self.methods.get(name)

    @property
    def initializer(self) -> Closure | None:
        return self.methods.get(INITIALIZER)

    @property
    def arity(self) -> int:
        initializer = self.initializer
        return initializer.arity if initializer is not None else 0

    def __repr__(self) -> str:
        return f"<class {self.name}>"


class Instance:
    """One object of a class, holding its own fields and a link to that class."""

    __slots__ = ("fields", "klass")

    def __init__(self, klass: EmberClass) -> None:
        self.klass = klass
        self.fields: dict[str, Any] = {}

    def __repr__(self) -> str:
        return f"<{self.klass.name} instance>"


class BoundMethod:
    """A method paired with the receiver it was reached through."""

    __slots__ = ("method", "receiver")

    def __init__(self, receiver: Instance, method: Closure) -> None:
        self.receiver = receiver
        self.method = method

    @property
    def name(self) -> str:
        return self.method.name

    @property
    def arity(self) -> int:
        return self.method.arity

    def __repr__(self) -> str:
        # printed the same way a plain function is, so the two backends agree
        # even though only this one has a distinct bound-method type
        return f"<fn {self.method.name}>"
