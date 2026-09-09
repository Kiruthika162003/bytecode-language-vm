"""The verifier: prove a chunk is well formed before the machine is asked to run it.

The machine trusts its input completely. It reads an operand as a constant index
without checking the pool has that many entries, follows a jump without checking
it lands anywhere sensible, and pops two values for an addition without checking
two are there. That trust is correct for bytecode this compiler produced, and
misplaced for bytecode that arrived from anywhere else: a file written by an older
version, a chunk edited by an optimiser with a bug, a program assembled by hand.
This module supplies the check, and the interesting part is not the easy
validations but the stack discipline. Walking the instructions in order is not
enough, because a jump means an instruction can be reached along several paths, so
the verifier propagates a stack height along every edge and insists that all paths
reaching one instruction agree on it. Disagreement is the signature of a real bug:
it means the height at that point depends on which way control came, and the
compiler's assumption that a slot is at a known offset no longer holds. The
handler edge is the subtle one. A catch clause is reached with the stack truncated
to what it was when the try began and the thrown value pushed on top, so the edge
into a handler carries one more than the edge past it, and encoding that is what
lets a try block verify at all. The verifier reports every problem it finds rather
than stopping at the first, because a chunk that is wrong is usually wrong in
several places at once, and it never repairs anything: deciding what a malformed
chunk was meant to do is guesswork, and running a guess is worse than refusing.

Not every problem is a fault, and learning that changed this module. The first
version treated unreachable code as an error, and on a corpus of twenty three
programs it condemned eleven of them, which looked like a verifier bug until the
disassembly said otherwise. The reports were correct: the compiler ends every
function with an unconditional nil-and-return epilogue, and a function whose body
already returns on every path can never reach it, so those instructions really are
dead. They are also entirely safe, and the peephole pass deletes them, which the
measurement then confirmed from the other direction: thirteen unreachable reports
across the corpus unoptimised, one after the peephole pass, and zero faults in
either case. So a problem now carries a severity, unreachable code is the one
warning, and refusing to run is reserved for the kinds that mean the machine would
actually misbehave.

One expectation here was simply wrong and is worth leaving on the record. The
target check was written assuming the verifier would be the first thing to look at
a jump, and a test that bent a jump to land past the end of the code proved
otherwise: the decoder refuses such a chunk itself, because turning byte distances
into instruction indexes requires every landing to be an instruction start, and it
raised before the verifier saw anything. That made the exception the report, which
defeats the purpose of a checker that promises to list every problem at once. So
decoding now happens inside the verifier's own guard and a chunk it cannot read
comes back as a problem like any other. The target check stayed, because it costs
one comparison and the module should not depend on another module's refusal for
its own soundness, but it is a second line rather than the first.
"""

from __future__ import annotations

from dataclasses import dataclass

from ember.errors import Compile
from ember.function import Function
from ember.instructions import Program, decode
from ember.opcode import OpCode, operand_bytes
from ember.stackeffect import TERMINAL, effect_of, is_covered

BAD_OPERAND = "bad-operand"
BAD_TARGET = "bad-target"
STACK_UNDERFLOW = "stack-underflow"
STACK_DISAGREEMENT = "stack-disagreement"
MISSING_RETURN = "missing-return"
UNKNOWN_OPCODE = "unknown-opcode"
UNREACHABLE_CODE = "unreachable-code"
UNDECODABLE = "undecodable"
TRUNCATED = "truncated-instruction"

_CONSTANT_OPERANDS = (
    OpCode.CONSTANT,
    OpCode.DEFINE_GLOBAL,
    OpCode.DEFINE_GLOBAL_CONST,
    OpCode.GET_GLOBAL,
    OpCode.SET_GLOBAL,
    OpCode.CLOSURE,
    OpCode.CLASS,
    OpCode.METHOD,
    OpCode.GET_PROPERTY,
    OpCode.SET_PROPERTY,
    OpCode.GET_SUPER,
)

_UPVALUE_OPERANDS = (OpCode.GET_UPVALUE, OpCode.SET_UPVALUE)


ERROR = "error"
WARNING = "warning"

# Unreachable code is safe to run, so it is the one kind that is not a fault.
_SEVERITIES = {UNREACHABLE_CODE: WARNING}


@dataclass(frozen=True)
class Problem:
    kind: str
    index: int
    message: str

    @property
    def severity(self) -> str:
        return _SEVERITIES.get(self.kind, ERROR)

    @property
    def is_fault(self) -> bool:
        return self.severity == ERROR

    def render(self) -> str:
        return f"instruction {self.index}: {self.severity}: {self.kind}: {self.message}"


class Verifier:
    def __init__(self, function: Function) -> None:
        self._function = function
        self._problems: list[Problem] = []
        self._refusal: str | None = None
        try:
            self._program: Program = decode(function.chunk)
        except Compile as refused:
            # a chunk the decoder cannot read becomes a report, not an exception
            self._program = Program(constants=list(function.chunk.constants))
            self._refusal = str(refused)

    def verify(self) -> list[Problem]:
        self._problems = []
        if self._refusal is not None:
            self._add(UNDECODABLE, 0, self._refusal)
            return self._problems
        instructions = self._program.instructions
        if not instructions:
            self._add(MISSING_RETURN, 0, "the chunk is empty, so it can never return")
            return self._problems
        self._check_operands()
        heights = self._walk()
        self._check_tail(heights)
        return sorted(self._problems, key=lambda found: (found.index, found.kind))

    def _add(self, kind: str, index: int, message: str) -> None:
        self._problems.append(Problem(kind, index, message))

    def _check_operands(self) -> None:
        pool = len(self._program.constants)
        for index, instruction in enumerate(self._program.instructions):
            if not is_covered(instruction.opcode):
                self._add(
                    UNKNOWN_OPCODE,
                    index,
                    f"{instruction.opcode.name} has no recorded stack effect, so its "
                    "behaviour cannot be checked",
                )
                continue
            if self._is_truncated(instruction):
                self._add(
                    TRUNCATED,
                    index,
                    f"{instruction.opcode.name} wants "
                    f"{operand_bytes(instruction.opcode)} operand bytes but the code "
                    "ends first, so the chunk was cut short",
                )
                continue
            if instruction.opcode in _CONSTANT_OPERANDS:
                operand = instruction.operands[0]
                if operand >= pool:
                    self._add(
                        BAD_OPERAND,
                        index,
                        f"{instruction.opcode.name} names constant {operand} but the "
                        f"pool holds {pool}",
                    )
            if instruction.opcode in _UPVALUE_OPERANDS:
                operand = instruction.operands[0]
                if operand >= self._function.upvalue_count:
                    self._add(
                        BAD_OPERAND,
                        index,
                        f"{instruction.opcode.name} names upvalue {operand} but this "
                        f"function captures {self._function.upvalue_count}",
                    )
            # the decoder rejects a landing that is not an instruction start, so
            # this is a second line of defence rather than the first
            if instruction.target is not None and not 0 <= instruction.target <= len(
                self._program.instructions
            ):
                self._add(
                    BAD_TARGET,
                    index,
                    f"the target {instruction.target} is not an instruction here",
                )

    @staticmethod
    def _is_truncated(instruction: object) -> bool:
        opcode = instruction.opcode  # type: ignore[attr-defined]
        if opcode == OpCode.CLOSURE:
            # the one variable width instruction, whose length the decoder settles
            return False
        if instruction.target is not None:  # type: ignore[attr-defined]
            # a jump keeps its landing rather than its bytes, so it is complete
            return False
        return len(instruction.operands) < operand_bytes(opcode)  # type: ignore[attr-defined]

    def _walk(self) -> dict[int, int]:
        """Propagate a stack height along every edge, insisting the paths agree."""
        instructions = self._program.instructions
        count = len(instructions)
        heights: dict[int, int] = {0: 0}
        pending: list[int] = [0]
        while pending:
            index = pending.pop()
            if index >= count:
                continue
            height = heights[index]
            instruction = instructions[index]
            if not is_covered(instruction.opcode):
                continue
            operand = instruction.operands[0] if instruction.operands else 0
            change = effect_of(instruction.opcode, operand)
            consumed = -change if change < 0 else 0
            if height < consumed:
                self._add(
                    STACK_UNDERFLOW,
                    index,
                    f"{instruction.opcode.name} needs {consumed} values but only "
                    f"{height} are on the stack",
                )
                continue
            after = height + change
            for successor, arriving in self._edges(index, instruction, after, height):
                if successor > count:
                    continue
                known = heights.get(successor)
                if known is None:
                    heights[successor] = arriving
                    pending.append(successor)
                elif known != arriving:
                    self._add(
                        STACK_DISAGREEMENT,
                        successor,
                        f"one path arrives with {known} values on the stack and another "
                        f"with {arriving}, so the height here depends on the route taken",
                    )
        self._check_reachability(heights)
        return heights

    def _edges(
        self, index: int, instruction: object, after: int, before: int
    ) -> list[tuple[int, int]]:
        opcode = instruction.opcode  # type: ignore[attr-defined]
        target = instruction.target  # type: ignore[attr-defined]
        if opcode == OpCode.PUSH_HANDLER:
            # the catch clause is reached with the stack cut back to where the try
            # began and the thrown value pushed, so that edge carries one more
            return [(index + 1, after), (target, before + 1)]
        if opcode in (OpCode.JUMP, OpCode.LOOP):
            return [(target, after)]
        if opcode in (OpCode.JUMP_IF_FALSE, OpCode.JUMP_IF_TRUE):
            return [(index + 1, after), (target, after)]
        if opcode in TERMINAL:
            return []
        return [(index + 1, after)]

    def _check_reachability(self, heights: dict[int, int]) -> None:
        for index in range(len(self._program.instructions)):
            if index not in heights:
                self._add(
                    UNREACHABLE_CODE,
                    index,
                    "no path reaches this instruction, so it can never run",
                )
                # one report is enough to say the tail is dead
                return

    def _check_tail(self, heights: dict[int, int]) -> None:
        del heights
        last = self._program.instructions[-1]
        if last.opcode not in (OpCode.RETURN, OpCode.THROW):
            self._add(
                MISSING_RETURN,
                len(self._program.instructions) - 1,
                f"the chunk ends with {last.opcode.name}, so control would run past "
                "the end; every path must leave through a return",
            )


def verify(function: Function) -> list[Problem]:
    """Every problem found, faults and warnings alike."""
    return Verifier(function).verify()


def verify_deeply(function: Function) -> list[Problem]:
    """Verify a function and every function nested in its constant pool."""
    found = list(verify(function))
    for constant in function.chunk.constants:
        if isinstance(constant, Function):
            found.extend(verify_deeply(constant))
    return found


def faults(function: Function) -> list[Problem]:
    """Only the problems that would make running the chunk unsafe."""
    return [problem for problem in verify(function) if problem.is_fault]


def faults_deeply(function: Function) -> list[Problem]:
    return [problem for problem in verify_deeply(function) if problem.is_fault]


def warnings_deeply(function: Function) -> list[Problem]:
    return [problem for problem in verify_deeply(function) if not problem.is_fault]


def is_safe(function: Function) -> bool:
    """Whether the machine can be handed this function without risk."""
    return not faults_deeply(function)


def describe(function: Function) -> list[str]:
    """One rendered line per problem, faults first, for a person to read."""
    found = verify_deeply(function)
    ordered = [problem for problem in found if problem.is_fault]
    ordered.extend(problem for problem in found if not problem.is_fault)
    return [problem.render() for problem in ordered]
