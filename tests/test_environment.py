from __future__ import annotations

import pytest

from ember.environment import Environment
from ember.errors import Immutable, Unbound


class TestDefineAndGet:
    def test_a_defined_name_is_found(self):
        env = Environment()
        env.define("x", 5)
        assert env.get("x") == 5

    def test_an_inner_scope_sees_an_outer_binding(self):
        outer = Environment()
        outer.define("x", 5)
        inner = Environment(outer)
        assert inner.get("x") == 5

    def test_an_inner_binding_shadows_an_outer_one(self):
        outer = Environment()
        outer.define("x", 5)
        inner = Environment(outer)
        inner.define("x", 9)
        assert inner.get("x") == 9
        assert outer.get("x") == 5

    def test_an_unknown_name_is_unbound(self):
        with pytest.raises(Unbound):
            Environment().get("nope")


class TestAssign:
    def test_assignment_updates_the_defining_scope(self):
        outer = Environment()
        outer.define("x", 5)
        inner = Environment(outer)
        inner.assign("x", 7)
        assert outer.get("x") == 7

    def test_assigning_an_undeclared_name_is_unbound(self):
        with pytest.raises(Unbound):
            Environment().assign("x", 1)

    def test_assigning_a_constant_is_refused(self):
        env = Environment()
        env.define("k", 1, is_const=True)
        with pytest.raises(Immutable):
            env.assign("k", 2)

    def test_redefining_clears_constness(self):
        env = Environment()
        env.define("k", 1, is_const=True)
        env.define("k", 2, is_const=False)
        env.assign("k", 3)  # no longer const
        assert env.get("k") == 3


class TestHas:
    def test_has_follows_the_chain(self):
        outer = Environment()
        outer.define("x", 1)
        inner = Environment(outer)
        assert inner.has("x")
        assert not inner.has("y")
