"""Stack effects: how many values each instruction leaves behind, as a table.

Every instruction changes the height of the value stack by a fixed amount, and
writing that amount down for each one turns a question that would otherwise need
the machine to answer into arithmetic. The table is the foundation the verifier
stands on, and it is kept in its own module for a reason worth stating: it is a
restatement of what the machine does, so if the two ever disagree one of them is
wrong, and keeping the claim separate from the implementation is what makes that
disagreement findable. The effects that are easy to get wrong are the ones where
an instruction reads without consuming. Storing to a local or a global leaves its
value on the stack rather than removing it, because an assignment is an expression
whose value the surrounding code may still want, so those effects are zero rather
than negative. The conditional jumps likewise peek at the condition instead of
popping it, which is why the compiler emits an explicit pop on each branch and why
these count as zero here. Three instructions carry an operand that determines
their effect rather than having a fixed one, a call by its argument count and the
two collection builders by their element counts, so those are computed from the
operand instead of looked up. And two end a path rather than continuing it, so the
table records their effect while the verifier, not this module, knows that nothing
follows them.
"""

from __future__ import annotations

from ember.opcode import OpCode

# Instructions after which control does not fall through to the next instruction.
TERMINAL = (OpCode.RETURN, OpCode.THROW, OpCode.JUMP, OpCode.LOOP)

_FIXED: dict[OpCode, int] = {
    OpCode.CONSTANT: 1,
    OpCode.NIL: 1,
    OpCode.TRUE: 1,
    OpCode.FALSE: 1,
    OpCode.POP: -1,
    OpCode.DEFINE_GLOBAL: -1,
    OpCode.DEFINE_GLOBAL_CONST: -1,
    OpCode.GET_GLOBAL: 1,
    # a store leaves its value behind, because an assignment is an expression
    OpCode.SET_GLOBAL: 0,
    OpCode.GET_LOCAL: 1,
    OpCode.SET_LOCAL: 0,
    OpCode.GET_UPVALUE: 1,
    OpCode.SET_UPVALUE: 0,
    OpCode.CLOSE_UPVALUE: -1,
    OpCode.ADD: -1,
    OpCode.SUBTRACT: -1,
    OpCode.MULTIPLY: -1,
    OpCode.DIVIDE: -1,
    OpCode.MODULO: -1,
    OpCode.NEGATE: 0,
    OpCode.EQUAL: -1,
    OpCode.NOT_EQUAL: -1,
    OpCode.LESS: -1,
    OpCode.LESS_EQUAL: -1,
    OpCode.GREATER: -1,
    OpCode.GREATER_EQUAL: -1,
    OpCode.NOT: 0,
    OpCode.BIT_AND: -1,
    OpCode.BIT_OR: -1,
    OpCode.BIT_XOR: -1,
    OpCode.BIT_NOT: 0,
    OpCode.SHIFT_LEFT: -1,
    OpCode.SHIFT_RIGHT: -1,
    OpCode.TO_STRING: 0,
    OpCode.JUMP: 0,
    # the conditional jumps peek rather than pop, which is why the compiler emits
    # an explicit pop on each branch
    OpCode.JUMP_IF_FALSE: 0,
    OpCode.JUMP_IF_TRUE: 0,
    OpCode.LOOP: 0,
    OpCode.RETURN: -1,
    OpCode.PRINT: -1,
    OpCode.INDEX_GET: -1,
    OpCode.INDEX_SET: -2,
    OpCode.CLOSURE: 1,
    OpCode.CLASS: 1,
    OpCode.METHOD: -1,
    OpCode.GET_PROPERTY: 0,
    OpCode.SET_PROPERTY: -1,
    OpCode.INHERIT: -1,
    OpCode.GET_SUPER: -1,
    OpCode.ITER_PREPARE: 0,
    OpCode.ITER_SIZE: 0,
    OpCode.PUSH_HANDLER: 0,
    OpCode.POP_HANDLER: 0,
    OpCode.THROW: -1,
}

# These three read their effect from their operand rather than from the table.
OPERAND_DRIVEN = (OpCode.CALL, OpCode.BUILD_LIST, OpCode.BUILD_MAP)


def effect_of(opcode: OpCode, operand: int = 0) -> int:
    """How much this instruction changes the stack height."""
    if opcode == OpCode.CALL:
        # the callee and its arguments come off, one result goes on
        return -operand
    if opcode == OpCode.BUILD_LIST:
        return 1 - operand
    if opcode == OpCode.BUILD_MAP:
        return 1 - 2 * operand
    return _FIXED[opcode]


def is_covered(opcode: OpCode) -> bool:
    return opcode in _FIXED or opcode in OPERAND_DRIVEN


def uncovered() -> list[OpCode]:
    """Any opcode the table has forgotten, which a test uses to keep it complete."""
    return [opcode for opcode in OpCode if not is_covered(opcode)]
