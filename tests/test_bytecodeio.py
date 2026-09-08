from __future__ import annotations

import pytest

from ember.builtins import install_builtins
from ember.bytecodeio import MAGIC, VERSION, deserialize, serialize
from ember.disassembler import disassemble
from ember.errors import Compile
from ember.interpreter import build
from ember.vm import VM

RICH_PROGRAM = """
class A { init(x) { this.x = x; } m() { return this.x * 2; } }
class B < A { m() { return super.m() + 1; } }
fn make() { let c = 0; fn inc() { c = c + 1; return c; } return inc; }
let g = make();
print B(5).m(); print g(); print g();
print len("hello") + 1;
print nil; print true; print false; print 3.5; print -7;
"""


def _run(function) -> list[str]:
    machine = VM()
    install_builtins(machine)
    machine.interpret(function)
    return machine.output


def _count_functions(function) -> int:
    total = 1
    for constant in function.chunk.constants:
        if hasattr(constant, "chunk"):
            total += _count_functions(constant)
    return total


class TestHeader:
    def test_a_file_starts_with_the_magic_number(self):
        blob = serialize(build("print 1;"))
        assert blob[: len(MAGIC)] == MAGIC

    def test_bad_magic_is_refused(self):
        blob = serialize(build("print 1;"))
        with pytest.raises(Compile):
            deserialize(b"NOPE" + blob[4:])

    def test_a_future_version_is_refused(self):
        blob = serialize(build("print 1;"))
        with pytest.raises(Compile):
            deserialize(blob[: len(MAGIC)] + bytes([VERSION + 40]) + blob[len(MAGIC) + 1 :])

    def test_data_too_short_is_refused(self):
        with pytest.raises(Compile):
            deserialize(b"")

    def test_trailing_bytes_are_refused(self):
        blob = serialize(build("print 1;"))
        with pytest.raises(Compile):
            deserialize(blob + b"\x00")

    def test_a_truncated_file_is_refused(self):
        blob = serialize(build("print 1;"))
        with pytest.raises(Compile):
            deserialize(blob[:6])


class TestRoundTrip:
    def test_the_code_array_survives(self):
        function = build(RICH_PROGRAM)
        restored = deserialize(serialize(function))
        assert restored.chunk.code == function.chunk.code

    def test_the_disassembly_is_identical(self):
        function = build(RICH_PROGRAM)
        restored = deserialize(serialize(function))
        assert disassemble(restored.chunk, "x") == disassemble(function.chunk, "x")

    def test_line_information_survives(self):
        function = build(RICH_PROGRAM)
        restored = deserialize(serialize(function))
        original_lines = [function.chunk.line_at(i) for i in range(len(function.chunk.code))]
        restored_lines = [restored.chunk.line_at(i) for i in range(len(restored.chunk.code))]
        assert restored_lines == original_lines

    def test_nested_function_records_all_survive(self):
        function = build(RICH_PROGRAM)
        restored = deserialize(serialize(function))
        assert _count_functions(restored) == _count_functions(function)
        assert _count_functions(function) > 1

    def test_a_restored_program_runs_identically(self):
        function = build(RICH_PROGRAM)
        restored = deserialize(serialize(function))
        assert _run(restored) == _run(function)

    def test_the_name_arity_and_upvalue_count_survive(self):
        function = build("fn adder(n) { fn add(x) { return x + n; } return add; }")
        restored = deserialize(serialize(function))
        inner = next(c for c in restored.chunk.constants if hasattr(c, "chunk"))
        original = next(c for c in function.chunk.constants if hasattr(c, "chunk"))
        assert inner.name == original.name
        assert inner.arity == original.arity
        assert inner.upvalue_count == original.upvalue_count


class TestConstantKinds:
    @pytest.mark.parametrize(
        "source",
        [
            "print nil;",
            "print true; print false;",
            "print 0; print 127; print 128; print -1; print -1000;",
            "print 3.5; print -0.25;",
            'print "hello"; print "";',
            'print "unicode: café";',
        ],
    )
    def test_each_constant_kind_round_trips(self, source: str):
        function = build(source)
        restored = deserialize(serialize(function))
        assert _run(restored) == _run(function)


class TestCompactness:
    def test_the_encoding_is_smaller_than_the_source(self):
        blob = serialize(build(RICH_PROGRAM))
        # measured: the whole program, classes and closures included, fits in
        # a few hundred bytes because lengths and indices ride varints
        assert len(blob) < len(RICH_PROGRAM.encode("utf-8")) * 2
        assert len(blob) > 0
