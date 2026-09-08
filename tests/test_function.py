from __future__ import annotations

from ember.chunk import Chunk
from ember.function import Function, NativeFunction


class TestFunction:
    def test_it_carries_name_arity_and_chunk(self):
        chunk = Chunk()
        fn = Function("add", 2, chunk)
        assert fn.name == "add"
        assert fn.arity == 2
        assert fn.chunk is chunk

    def test_the_repr_names_the_function(self):
        fn = Function("add", 2, Chunk())
        assert "add" in repr(fn)

    def test_an_unnamed_function_reprs_as_script(self):
        fn = Function("", 0, Chunk())
        assert "script" in repr(fn)


class TestNativeFunction:
    def test_it_wraps_a_host_callable(self):
        native = NativeFunction("len", 1, lambda args: len(args[0]))
        assert native.arity == 1
        assert native.handler(["abc"]) == 3

    def test_the_repr_marks_it_native(self):
        native = NativeFunction("clock", 0, lambda _args: 0.0)
        assert "native" in repr(native)
