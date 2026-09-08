from __future__ import annotations

import pytest

from ember.chunk import Chunk
from ember.compiler import compile_program
from ember.disassembler import disassemble_instruction
from ember.errors import Compile, Immutable
from ember.opcode import OpCode
from ember.parser import parse
from ember.scanner import scan


def compile_source(source: str):
    return compile_program(parse(scan(source)))


def chunk_opcodes(chunk: Chunk) -> list[str]:
    # step with the disassembler so the variable-width CLOSURE is skipped by
    # its true size rather than by a fixed operand count
    names = []
    offset = 0
    while offset < len(chunk):
        names.append(OpCode(chunk.code[offset]).name)
        _, offset = disassemble_instruction(chunk, offset)
    return names


def opcodes(source: str) -> list[str]:
    return chunk_opcodes(compile_source(source).chunk)


class TestEmission:
    def test_a_literal_add_emits_two_constants_and_add(self):
        assert opcodes("1 + 2;")[:3] == ["CONSTANT", "CONSTANT", "ADD"]

    def test_a_global_declaration_emits_define_global(self):
        assert "DEFINE_GLOBAL" in opcodes("let x = 1;")

    def test_a_const_global_emits_the_const_define(self):
        assert "DEFINE_GLOBAL_CONST" in opcodes("const x = 1;")

    def test_a_local_uses_slots_not_names(self):
        names = opcodes("{ let x = 1; print x; }")
        assert "GET_LOCAL" in names
        assert "GET_GLOBAL" not in names

    def test_a_while_emits_a_loop(self):
        assert "LOOP" in opcodes("while (true) print 1;")

    def test_the_script_ends_with_nil_and_return(self):
        assert opcodes("1;")[-2:] == ["NIL", "RETURN"]


class TestCompileErrors:
    def test_reassigning_a_const_global_is_refused(self):
        with pytest.raises(Immutable):
            compile_source("const k = 1; k = 2;")

    def test_reassigning_a_const_local_is_refused(self):
        with pytest.raises(Immutable):
            compile_source("{ const k = 1; k = 2; }")

    def test_too_many_constants_is_refused(self):
        # 300 distinct string literals overflow the one-byte constant pool
        body = "".join(f'print "s{i}";' for i in range(300))
        with pytest.raises(Compile):
            compile_source(body)


class TestFunctions:
    def test_a_function_becomes_a_closure_and_a_global(self):
        names = opcodes("fn f() { return 1; }")
        assert "CLOSURE" in names
        assert "DEFINE_GLOBAL" in names

    def test_a_function_capturing_nothing_declares_no_upvalues(self):
        function = compile_source("fn f() { return 1; }")
        inner = next(c for c in function.chunk.constants if hasattr(c, "upvalue_count"))
        assert inner.upvalue_count == 0

    def test_a_function_capturing_an_enclosing_local_declares_an_upvalue(self):
        source = "fn outer() { let x = 1; fn inner() { return x; } return inner; }"
        outer = compile_source(source)
        outer_fn = next(c for c in outer.chunk.constants if hasattr(c, "upvalue_count"))
        inner_fn = next(
            c for c in outer_fn.chunk.constants if hasattr(c, "upvalue_count")
        )
        assert inner_fn.upvalue_count == 1

    def test_a_captured_local_is_closed_rather_than_popped(self):
        source = "fn outer() { { let x = 1; fn inner() { return x; } } return 0; }"
        outer = compile_source(source)
        outer_fn = next(c for c in outer.chunk.constants if hasattr(c, "upvalue_count"))
        body = chunk_opcodes(outer_fn.chunk)
        assert "CLOSE_UPVALUE" in body
