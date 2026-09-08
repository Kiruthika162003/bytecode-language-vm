from __future__ import annotations

import pytest

from ember.errors import Compile, Resolve
from ember.localscope import LocalScope


class TestDeclareAndResolve:
    def test_a_declared_local_resolves_to_its_slot(self):
        scope = LocalScope()
        scope.begin_scope()
        slot = scope.declare("x")
        assert scope.resolve("x") == slot

    def test_an_unknown_name_resolves_to_none(self):
        scope = LocalScope()
        scope.begin_scope()
        scope.declare("x")
        assert scope.resolve("y") is None

    def test_slots_are_assigned_in_order(self):
        scope = LocalScope()
        scope.begin_scope()
        assert scope.declare("a") == 0
        assert scope.declare("b") == 1


class TestShadowing:
    def test_an_inner_declaration_shadows_an_outer_one(self):
        scope = LocalScope()
        scope.begin_scope()
        outer = scope.declare("x")
        scope.begin_scope()
        inner = scope.declare("x")
        assert scope.resolve("x") == inner
        assert inner != outer

    def test_leaving_a_scope_reveals_the_outer_binding(self):
        scope = LocalScope()
        scope.begin_scope()
        outer = scope.declare("x")
        scope.begin_scope()
        scope.declare("x")
        removed = scope.end_scope()
        assert removed == 1
        assert scope.resolve("x") == outer


class TestConst:
    def test_constness_is_remembered(self):
        scope = LocalScope()
        scope.begin_scope()
        slot = scope.declare("k", is_const=True)
        assert scope.is_const(slot)


class TestRefusals:
    def test_redeclaring_in_the_same_scope_is_refused(self):
        scope = LocalScope()
        scope.begin_scope()
        scope.declare("x")
        with pytest.raises(Resolve):
            scope.declare("x")

    def test_the_same_name_in_a_nested_scope_is_allowed(self):
        scope = LocalScope()
        scope.begin_scope()
        scope.declare("x")
        scope.begin_scope()
        scope.declare("x")  # no error

    def test_too_many_locals_is_refused(self):
        scope = LocalScope()
        scope.begin_scope()
        for i in range(256):
            scope.declare(f"v{i}")
        with pytest.raises(Compile):
            scope.declare("one_too_many")


class TestReserved:
    def test_the_reserved_slot_cannot_be_resolved(self):
        scope = LocalScope()
        scope.begin_scope()
        scope.declare_reserved()
        assert scope.resolve("") is None
