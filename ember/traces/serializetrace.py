"""Serialization measured: a whole program with classes and closures, and what came back.

Caching compiled code is only safe if what comes back is indistinguishable
from what went out, so this trace serialises a program that exercises the
awkward parts of the format, two classes with inheritance, a closure factory,
a native call, and several constant kinds, then reads it back and compares.
The comparison is the disassembly rather than the raw code array, because
the disassembly also renders the constants and the source lines, so an
equal disassembly means the pool and the line table survived too, not just
the instructions. Counting the function records checks the recursion: the
program contains several nested functions, and the format writes each inline
inside its parent's constant pool, so a miscount would mean a nesting level
was lost. The byte total is reported because it is the reason the format
exists, and it is small largely because lengths and indices ride a
variable-length encoding rather than fixed fields.
"""

from __future__ import annotations

from ember.builtins import install_builtins
from ember.bytecodeio import deserialize, serialize
from ember.disassembler import disassemble
from ember.function import Function
from ember.interpreter import build
from ember.traces.finding import Finding
from ember.vm import VM

NAME = "serialize"
SOURCE = """class A { init(x) { this.x = x; } m() { return this.x * 2; } }
class B < A { m() { return super.m() + 1; } }
fn make() { let c = 0; fn inc() { c = c + 1; return c; } return inc; }
let g = make();
print B(5).m(); print g(); print g(); print len("hello") + 1;
"""


def _count_functions(function: Function) -> int:
    total = 1
    for constant in function.chunk.constants:
        if isinstance(constant, Function):
            total += _count_functions(constant)
    return total


def _execute(function: Function) -> list[str]:
    machine = VM()
    install_builtins(machine)
    machine.interpret(function)
    return machine.output


def run() -> Finding:
    original = build(SOURCE)
    blob = serialize(original)
    restored = deserialize(blob)
    same_text = disassemble(original.chunk, "x") == disassemble(restored.chunk, "x")
    lines_before = [original.chunk.line_at(i) for i in range(len(original.chunk.code))]
    lines_after = [restored.chunk.line_at(i) for i in range(len(restored.chunk.code))]
    records = _count_functions(original)
    holds = (
        same_text
        and lines_before == lines_after
        and records == _count_functions(restored)
        and records == 6
        and _execute(original) == _execute(restored)
    )
    claim = (
        f"a program with two classes, inheritance, and a closure factory "
        f"serialises to {len(blob)} bytes holding {records} nested function "
        "records, and reading it back gives byte-identical disassembly, the "
        "same line table, and the same output"
    )
    return Finding(NAME, claim, holds)
