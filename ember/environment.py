"""The environment: a chain of scopes that maps a name to its value at run time.

A tree-walking interpreter does not compile names to slots the way the
bytecode compiler does; it looks each name up as it runs, and this module
is the structure it looks in. An environment is a dictionary of names
bound in the current scope together with a link to the enclosing
environment, so resolving a name searches the current scope and then
walks outward until it finds a binding or runs out of scopes. That chain
is exactly what lexical scoping means, and because a function can hold on
to the environment it was defined in, it is also what makes closures work
in the tree-walker for free: the captured chain keeps the enclosing
variables alive and reachable. Two rules are enforced here so the
interpreter does not have to repeat them. Defining a name records whether
it was declared constant, and a later assignment to a constant is
refused rather than allowed to overwrite it. And assignment, unlike
definition, must find an existing binding somewhere along the chain and
update it in place, so assigning to a name that was never declared is an
unbound-name error rather than silently creating a global. The honest
cost of this representation is speed: every variable access is a
dictionary lookup and possibly several, up the chain, where the compiled
backend reaches a local in one indexed step. That gap is the whole reason
the bytecode backend exists, and keeping this structure simple makes the
comparison between the two honest.
"""

from __future__ import annotations

from typing import Any

from ember.errors import Immutable, Unbound


class Environment:
    def __init__(self, enclosing: Environment | None = None) -> None:
        self._values: dict[str, Any] = {}
        self._consts: set[str] = set()
        self.enclosing = enclosing

    def define(self, name: str, value: Any, is_const: bool = False) -> None:
        self._values[name] = value
        if is_const:
            self._consts.add(name)
        else:
            self._consts.discard(name)

    def get(self, name: str) -> Any:
        environment: Environment | None = self
        while environment is not None:
            if name in environment._values:
                return environment._values[name]
            environment = environment.enclosing
        raise Unbound(f"the name {name!r} is not defined")

    def assign(self, name: str, value: Any) -> None:
        environment: Environment | None = self
        while environment is not None:
            if name in environment._values:
                if name in environment._consts:
                    raise Immutable(
                        f"the constant {name!r} cannot be assigned to after its "
                        "declaration"
                    )
                environment._values[name] = value
                return
            environment = environment.enclosing
        raise Unbound(
            f"cannot assign to {name!r} because it was never declared"
        )

    def has(self, name: str) -> bool:
        environment: Environment | None = self
        while environment is not None:
            if name in environment._values:
                return True
            environment = environment.enclosing
        return False
