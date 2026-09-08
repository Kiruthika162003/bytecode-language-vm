from __future__ import annotations

import pytest

from ember.compiler import compile_program
from ember.errors import Compile, Immutable
from ember.opcode import OpCode, operand_bytes
from ember.parser import parse
from ember.scanner import scan


def compile_source(source: str):
    return compile_program(parse(scan(source)))


def opcodes(source: str) -> list[str]:
    chunk = compile_source(source).chunk
    names = []
    offset = 0
    while offset < len(chunk):
        op = OpCode(chunk.code[offset])
        names.append(op.name)
        offset += 1 + operand_bytes(op)
    return names


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
    def test_a_function_becomes_a_constant_and_a_global(self):
        names = opcodes("fn f() { return 1; }")
        assert "CONSTANT" in names
        assert "DEFINE_GLOBAL" in names
