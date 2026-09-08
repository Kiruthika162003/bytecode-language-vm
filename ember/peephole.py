"""Peephole optimization: rewrite short instruction sequences the tree passes cannot see.

The tree passes fold arithmetic and delete unreachable statements, but they
work on the program as written and never see the instruction sequence that
comes out, where a different class of waste appears. A value pushed and
immediately discarded is the common one, and it is not a sign of a badly
written program: an expression statement leaves its value on the stack and the
compiler emits a pop, so a statement that only reads a variable compiles to a
load followed by a pop that together do nothing. A jump whose target is the
next instruction is another, produced naturally where an if has no else. And a
jump landing on another unconditional jump can go straight to the final
destination instead of arriving and immediately leaving again. This pass
removes all three, working on decoded instructions where a jump names its
target rather than a distance, which is what makes deletion safe at all.
The rule that keeps it correct is about jump targets: an instruction some jump
can land on must never be deleted, and neither may a pair be collapsed when
control can arrive between its halves, because either edit would move code out
from under a jump that still points at it. So every candidate is checked
against the set of live targets first. Two tempting rewrites are deliberately
absent, and both are cases where a rewrite that looks safe is not. A doubled
logical not looks removable but coerces its value to a boolean, so deleting
the pair would leave a number where the program expects true. And a global
load followed by a pop is not cancellable even though a local load is: reading
an undefined global raises, so that pair is not dead code but an error the
program is entitled to receive, and only loads that cannot fail are eligible.
That is why the list of cancellable pushes is exactly the instructions with no
way to go wrong. The pass repeats until a round changes nothing, since
removing one pair can expose another behind it.
"""

from __future__ import annotations

from dataclasses import dataclass

from ember.chunk import Chunk
from ember.instructions import Program, decode, encode
from ember.opcode import OpCode

_MAX_ROUNDS = 8

# Instructions that push exactly one value, have no other effect, and cannot
# fail. GET_GLOBAL is absent on purpose: it raises for an undefined name, so a
# global load followed by a pop is an error the program should still receive.
_PURE_PUSHES = (
    OpCode.CONSTANT,
    OpCode.NIL,
    OpCode.TRUE,
    OpCode.FALSE,
    OpCode.GET_LOCAL,
    OpCode.GET_UPVALUE,
    OpCode.CLOSURE,
)


@dataclass(frozen=True)
class PeepholeReport:
    rounds: int
    removed: int

    @property
    def changed(self) -> bool:
        return self.removed > 0


def _thread_jumps(program: Program) -> int:
    """Point each jump at the final destination rather than at another jump."""
    changed = 0
    count = len(program.instructions)
    for instruction in program.instructions:
        if instruction.target is None:
            continue
        seen: set[int] = set()
        target = instruction.target
        while target < count and target not in seen:
            landing = program.instructions[target]
            if landing.opcode != OpCode.JUMP or landing.target is None:
                break
            seen.add(target)
            target = landing.target
        if target != instruction.target:
            instruction.target = target
            changed += 1
    return changed


def _remove_indices(program: Program, doomed: set[int]) -> None:
    """Drop the named instructions and renumber every jump target around them."""
    if not doomed:
        return
    count = len(program.instructions)
    shift: list[int] = []
    removed = 0
    for index in range(count + 1):
        shift.append(index - removed)
        if index in doomed:
            removed += 1
    kept = [
        instruction
        for index, instruction in enumerate(program.instructions)
        if index not in doomed
    ]
    for instruction in kept:
        if instruction.target is not None:
            instruction.target = shift[instruction.target]
    program.instructions = kept


def _cancel_push_pop(program: Program) -> set[int]:
    doomed: set[int] = set()
    targets = program.targets()
    instructions = program.instructions
    for index in range(len(instructions) - 1):
        if index in doomed or index + 1 in doomed:
            continue
        first = instructions[index]
        second = instructions[index + 1]
        if first.opcode not in _PURE_PUSHES or second.opcode != OpCode.POP:
            continue
        # neither half may be a place a jump can arrive at, or the edit would
        # move code out from under a jump that still points there
        if index in targets or index + 1 in targets:
            continue
        doomed.add(index)
        doomed.add(index + 1)
    return doomed


def _remove_useless_jumps(program: Program) -> set[int]:
    doomed: set[int] = set()
    targets = program.targets()
    for index, instruction in enumerate(program.instructions):
        if instruction.opcode != OpCode.JUMP or instruction.target is None:
            continue
        if instruction.target != index + 1:
            continue
        if index in targets:
            continue
        doomed.add(index)
    return doomed


def _remove_unreachable(program: Program) -> set[int]:
    """Drop instructions after an unconditional transfer until something is landed on."""
    doomed: set[int] = set()
    targets = program.targets()
    instructions = program.instructions
    index = 0
    while index < len(instructions):
        opcode = instructions[index].opcode
        transfers = opcode == OpCode.RETURN or opcode in (OpCode.JUMP, OpCode.LOOP)
        if not transfers:
            index += 1
            continue
        following = index + 1
        while following < len(instructions) and following not in targets:
            doomed.add(following)
            following += 1
        index = following
    return doomed


def optimize_program(program: Program) -> PeepholeReport:
    rounds = 0
    removed = 0
    for _ in range(_MAX_ROUNDS):
        rounds += 1
        threaded = _thread_jumps(program)
        doomed = _cancel_push_pop(program)
        doomed |= _remove_useless_jumps(program)
        doomed |= _remove_unreachable(program)
        if not doomed and not threaded:
            break
        removed += len(doomed)
        _remove_indices(program, doomed)
    return PeepholeReport(rounds=rounds, removed=removed)


def optimize_chunk(chunk: Chunk) -> tuple[Chunk, PeepholeReport]:
    program = decode(chunk)
    report = optimize_program(program)
    if not report.changed:
        # nothing was removed, so the original chunk is returned untouched rather
        # than re-encoded, which keeps the no-op case exactly a no-op
        return chunk, report
    return encode(program), report


def optimize_function(function: object) -> PeepholeReport:
    """Optimize a function's chunk and every function nested in its constants."""
    chunk = getattr(function, "chunk", None)
    if chunk is None:
        return PeepholeReport(rounds=0, removed=0)
    tightened, report = optimize_chunk(chunk)
    function.chunk = tightened  # type: ignore[attr-defined]
    total = report.removed
    rounds = report.rounds
    for constant in tightened.constants:
        if hasattr(constant, "chunk"):
            nested = optimize_function(constant)
            total += nested.removed
            rounds = max(rounds, nested.rounds)
    return PeepholeReport(rounds=rounds, removed=total)
