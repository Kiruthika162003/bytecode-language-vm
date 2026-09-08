from __future__ import annotations

import builtins

import pytest

from ember.errors import (
    Arithmetic,
    Arity,
    Compile,
    EmberError,
    Immutable,
    IndexRange,
    Resolve,
    StackFault,
    Syntax,
    TypeMismatch,
    Unbound,
)

ALL_KINDS = [
    Syntax,
    Resolve,
    Compile,
    TypeMismatch,
    Arity,
    Unbound,
    Arithmetic,
    IndexRange,
    StackFault,
    Immutable,
]


class TestHierarchy:
    def test_every_kind_descends_from_the_base(self):
        for kind in ALL_KINDS:
            assert issubclass(kind, EmberError)

    def test_the_base_descends_from_exception(self):
        assert issubclass(EmberError, Exception)

    def test_catching_the_base_catches_each_kind(self):
        for kind in ALL_KINDS:
            with pytest.raises(EmberError):
                raise kind("a message")


class TestDistinctness:
    def test_the_kinds_are_all_distinct_classes(self):
        assert len({kind.__name__ for kind in ALL_KINDS}) == len(ALL_KINDS)

    def test_no_kind_shadows_a_builtin_exception(self):
        builtin_names = set(dir(builtins))
        for kind in ALL_KINDS:
            assert kind.__name__ not in {"SyntaxError", "TypeError", "NameError"}
            assert kind.__name__ not in builtin_names
