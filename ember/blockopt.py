"""Two optimisations the graph makes safe: removing dead blocks and threading jumps.

The peephole pass looks at neighbouring instructions and so can only see what is adjacent.
These two need to see the shape of the whole function, which is what the control flow graph
provides, and they are worth having for a specific reason: they remove exactly the two
things every other analysis in this project has had to work around.

Dead block removal deletes instructions no path reaches. The verifier has been reporting
those since it was written, and the reports were correct: the compiler ends every function
with a nil-and-return epilogue that a body already returning on every path can never reach.
Every measurement since has had to say reachable blocks only, and after this pass there is
nothing unreachable left to exclude. Removing them is safe in a way that most bytecode
edits are not, because an instruction no path reaches cannot affect a run whatever it holds.

Jump threading redirects a jump whose target is itself an unconditional jump, so control
arrives where it was always going to end up rather than passing through an intermediate hop.
The motivation written here first was that such chains appear wherever a jump leaves a
nested construct, a break inside two loops passing through the inner exit on its way to the
outer one, and measuring found none of that: the compiler backpatches a break straight to
the loop it leaves, so a nested break produces no chain at all. Six nested shapes were
checked and five had nothing to thread. The one that does is a nested if with an else, where
the inner arm's jump over its own else lands on the outer arm's jump over the outer else,
and on the twenty two program corpus that shape never occurs, so the pass threads nothing
there. So this is a real optimisation that fires rarely, which is worth recording plainly
rather than leaving a claim about nested loops that the bytecode does not support. The chain
is followed with a limit, because a jump to itself is a cycle a loop would never leave; this
compiler cannot emit one, so the limit guards against a hand written chunk rather than
against anything the compiler does.

Both passes are checked rather than trusted. The verifier runs over the result, the
differential tester compares output against the unoptimised form, and the traces record
both. That matters more here than for the tree level passes: an edit to a jump that lands
one instruction out produces a program that runs and is wrong, which is the hardest kind of
bug to find and the easiest kind for a pass like this to introduce.
"""

from __future__ import annotations

from dataclasses import dataclass

from ember.cfg import build_graph
from ember.function import Function
from ember.instructions import Instruction, Program, decode, encode
from ember.opcode import OpCode

_CHAIN_LIMIT = 100


@dataclass
class Report:
    """What the passes changed, so a caller can say whether they were worth running."""

    blocks_removed: int = 0
    instructions_removed: int = 0
    jumps_threaded: int = 0

    @property
    def changed(self) -> bool:
        return bool(self.blocks_removed or self.jumps_threaded)

    def render(self) -> str:
        return (
            f"{self.instructions_removed} instructions in {self.blocks_removed} "
            f"unreachable blocks removed, {self.jumps_threaded} jumps threaded"
        )


def _final_target(program: Program, start: int) -> int:
    """Follow a chain of unconditional jumps to where control actually ends up."""
    at = start
    for _ in range(_CHAIN_LIMIT):
        if at >= len(program.instructions):
            return at
        instruction = program.instructions[at]
        if instruction.opcode != OpCode.JUMP or instruction.target is None:
            return at
        if instruction.target == at:
            # a jump to itself is a cycle; this compiler cannot emit one, so the
            # guard exists so a hand written chunk cannot spin the pass for ever
            return at
        at = instruction.target
    return at


def thread_jumps(program: Program) -> int:
    """Point every jump at where control really goes, and say how many moved."""
    moved = 0
    for instruction in program.instructions:
        if instruction.target is None:
            continue
        if instruction.opcode == OpCode.LOOP:
            # a backward jump's target is a loop header, and following it forward
            # would leave the loop rather than shortening the path into it
            continue
        settled = _final_target(program, instruction.target)
        if settled != instruction.target:
            instruction.target = settled
            moved += 1
    return moved


def remove_unreachable(program: Program) -> tuple[int, int]:
    """Drop every block no path reaches, renumbering the targets that survive."""
    graph = build_graph(program)
    if not graph.blocks:
        return (0, 0)
    live = graph.reachable()
    dead = [block for block in graph.blocks if block.index not in live]
    if not dead:
        return (0, 0)
    doomed: set[int] = set()
    for block in dead:
        doomed.update(range(block.start, block.end))
    kept: list[Instruction] = []
    # where each surviving instruction ends up, so a target can be rewritten
    moved: dict[int, int] = {}
    for index, instruction in enumerate(program.instructions):
        if index in doomed:
            continue
        moved[index] = len(kept)
        kept.append(instruction)
    for instruction in kept:
        if instruction.target is not None:
            if instruction.target in moved:
                instruction.target = moved[instruction.target]
            elif instruction.target >= len(program.instructions):
                instruction.target = len(kept)
    program.instructions[:] = kept
    return (len(dead), len(doomed))


def optimise_program(program: Program) -> Report:
    """Thread the jumps, then remove what threading made unreachable."""
    report = Report()
    report.jumps_threaded = thread_jumps(program)
    # threading first, because a jump that no longer passes through an intermediate
    # block can leave that block with nothing reaching it
    blocks, instructions = remove_unreachable(program)
    report.blocks_removed = blocks
    report.instructions_removed = instructions
    return report


def optimise_function(function: Function) -> Report:
    """Replace one function's chunk, leaving its nested functions alone."""
    program = decode(function.chunk)
    report = optimise_program(program)
    if report.changed:
        # the chunk is replaced rather than edited in place, which keeps the case
        # where nothing changed exactly a no-op
        function.chunk = encode(program)
    return report


def _gathered(into: Report, from_one: Report) -> None:
    into.blocks_removed += from_one.blocks_removed
    into.instructions_removed += from_one.instructions_removed
    into.jumps_threaded += from_one.jumps_threaded


def optimise_deeply(function: Function) -> Report:
    """Every function in the tree, which is what a whole program needs."""
    total = Report()
    _gathered(total, optimise_function(function))
    for constant in function.chunk.constants:
        if isinstance(constant, Function):
            _gathered(total, optimise_deeply(constant))
    return total
