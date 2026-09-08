"""The instruction set: the fixed repertoire of one-byte operations the machine runs.

A bytecode virtual machine executes a flat array of small integers, and
this module names what each of those integers means. Every opcode is one
byte, and most are followed by a fixed number of operand bytes that the
machine reads inline: a constant load is followed by one byte selecting
which constant, a jump by two bytes giving how far, a local access by one
byte giving the slot. Naming the opcodes as an enumeration rather than
using bare numbers keeps the compiler and the machine speaking the same
language, and pairing the enumeration with a table of operand widths lets
both the disassembler and the machine step over instructions without
each hard-coding the shape of every opcode. The deliberate constraint is
that operands are bytes, so a single instruction can name at most 256
constants or reach a slot no higher than 255, and a jump can span no more
than 65535 bytes. These limits are not an accident of Python, which could
hold arbitrary integers in the list; they are chosen to make the format a
faithful byte-addressed encoding, and the compiler turns an overrun into
a clear compile-time error rather than silently emitting a value that
does not fit a byte. The honest cost is that a program with more than 256
constants in one function must be split or must use a wider load
instruction, which this compact set does not provide, trading a little
capacity for an encoding that is simple to read and to execute.
"""

from __future__ import annotations

from enum import IntEnum


class OpCode(IntEnum):
    CONSTANT = 0
    NIL = 1
    TRUE = 2
    FALSE = 3
    POP = 4

    DEFINE_GLOBAL = 5
    GET_GLOBAL = 6
    SET_GLOBAL = 7
    GET_LOCAL = 8
    SET_LOCAL = 9
    DEFINE_GLOBAL_CONST = 34

    ADD = 10
    SUBTRACT = 11
    MULTIPLY = 12
    DIVIDE = 13
    MODULO = 14
    NEGATE = 15

    EQUAL = 16
    NOT_EQUAL = 17
    LESS = 18
    LESS_EQUAL = 19
    GREATER = 20
    GREATER_EQUAL = 21
    NOT = 22

    JUMP = 23
    JUMP_IF_FALSE = 24
    JUMP_IF_TRUE = 25
    LOOP = 26

    CALL = 27
    RETURN = 28
    PRINT = 29

    BUILD_LIST = 30
    BUILD_MAP = 31
    INDEX_GET = 32
    INDEX_SET = 33

    CLOSURE = 35
    GET_UPVALUE = 36
    SET_UPVALUE = 37
    CLOSE_UPVALUE = 38

    CLASS = 39
    METHOD = 40
    GET_PROPERTY = 41
    SET_PROPERTY = 42
    INHERIT = 43
    GET_SUPER = 44
    ITER_PREPARE = 45
    ITER_SIZE = 46
    TO_STRING = 56

    BIT_AND = 50
    BIT_OR = 51
    BIT_XOR = 52
    BIT_NOT = 53
    SHIFT_LEFT = 54
    SHIFT_RIGHT = 55

    PUSH_HANDLER = 47
    POP_HANDLER = 48
    THROW = 49


# How many operand bytes follow each opcode. A jump carries a two-byte
# offset; the loads and calls carry one; the rest are bare. CLOSURE is the
# one variable-width instruction: the count below covers its constant
# operand, and two more bytes follow for each upvalue the closure captures,
# so a reader must consult the named function to step over it.
OPERAND_BYTES: dict[OpCode, int] = {
    OpCode.CONSTANT: 1,
    OpCode.NIL: 0,
    OpCode.TRUE: 0,
    OpCode.FALSE: 0,
    OpCode.POP: 0,
    OpCode.DEFINE_GLOBAL: 1,
    OpCode.DEFINE_GLOBAL_CONST: 1,
    OpCode.GET_GLOBAL: 1,
    OpCode.SET_GLOBAL: 1,
    OpCode.GET_LOCAL: 1,
    OpCode.SET_LOCAL: 1,
    OpCode.ADD: 0,
    OpCode.SUBTRACT: 0,
    OpCode.MULTIPLY: 0,
    OpCode.DIVIDE: 0,
    OpCode.MODULO: 0,
    OpCode.NEGATE: 0,
    OpCode.EQUAL: 0,
    OpCode.NOT_EQUAL: 0,
    OpCode.LESS: 0,
    OpCode.LESS_EQUAL: 0,
    OpCode.GREATER: 0,
    OpCode.GREATER_EQUAL: 0,
    OpCode.NOT: 0,
    OpCode.JUMP: 2,
    OpCode.JUMP_IF_FALSE: 2,
    OpCode.JUMP_IF_TRUE: 2,
    OpCode.LOOP: 2,
    OpCode.CALL: 1,
    OpCode.RETURN: 0,
    OpCode.PRINT: 0,
    OpCode.BUILD_LIST: 1,
    OpCode.BUILD_MAP: 1,
    OpCode.INDEX_GET: 0,
    OpCode.INDEX_SET: 0,
    OpCode.CLOSURE: 1,
    OpCode.GET_UPVALUE: 1,
    OpCode.SET_UPVALUE: 1,
    OpCode.CLOSE_UPVALUE: 0,
    OpCode.CLASS: 1,
    OpCode.METHOD: 1,
    OpCode.GET_PROPERTY: 1,
    OpCode.SET_PROPERTY: 1,
    OpCode.INHERIT: 0,
    OpCode.GET_SUPER: 1,
    OpCode.ITER_PREPARE: 0,
    OpCode.ITER_SIZE: 0,
    OpCode.PUSH_HANDLER: 2,
    OpCode.POP_HANDLER: 0,
    OpCode.THROW: 0,
    OpCode.BIT_AND: 0,
    OpCode.BIT_OR: 0,
    OpCode.BIT_XOR: 0,
    OpCode.TO_STRING: 0,
    OpCode.BIT_NOT: 0,
    OpCode.SHIFT_LEFT: 0,
    OpCode.SHIFT_RIGHT: 0,
}


def operand_bytes(opcode: OpCode) -> int:
    return OPERAND_BYTES[opcode]
