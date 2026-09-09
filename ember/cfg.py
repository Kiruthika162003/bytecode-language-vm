"""The control flow graph: group instructions into blocks that always run together.

A list of instructions with jumps in it hides the shape of the program. Every
question worth asking about that shape, whether one instruction always runs before
another, whether a loop exists, whether a value is still needed, is awkward to
answer instruction by instruction and straightforward to answer over blocks. So
this module builds the graph once and lets the passes that follow share it. A block
is a run of instructions with exactly one way in at the top and exactly one way out
at the bottom, which means the whole run either executes or does not, and finding
them comes down to finding the boundaries: an instruction starts a block if it is
the entry, if some jump lands on it, or if the instruction before it ended one.
That third rule is the reason a jump, a return and a throw are treated the same
here even though they behave differently at runtime, because what matters to the
graph is only whether control continues to the next instruction.

The handler edge is modelled deliberately and imperfectly, and the imprecision is
worth naming rather than hiding. A thrown value can leave a try block from any
instruction inside it, so a faithful graph would give every one of those
instructions an edge to the catch clause. This graph instead puts a single edge
from the PUSH_HANDLER that opened the region, which is enough for reachability and
for asking which blocks a handler protects, and not enough to prove a value is dead
inside a try block, since an analysis walking these edges would miss that the catch
clause may read it. Every pass built on this graph therefore treats a try region
conservatively, and that choice belongs here where the edges are made rather than
scattered across the passes that consume them.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ember.instructions import Instruction, Program, decode
from ember.opcode import OpCode
from ember.stackeffect import TERMINAL

# Each of these closes the block it sits in, because control either stops or forks
# there. PUSH_HANDLER belongs in the list for the second reason and was left out of
# the first draft, which made the whole of a try block look unreachable: successors
# are read from a block's last instruction, so a fork in the middle of one is a fork
# that never gets edges.
_ENDS_A_BLOCK = (
    *TERMINAL,
    OpCode.JUMP_IF_FALSE,
    OpCode.JUMP_IF_TRUE,
    OpCode.PUSH_HANDLER,
)


@dataclass
class Block:
    """A run of instructions that always execute together, in order."""

    index: int
    start: int
    end: int
    successors: list[int] = field(default_factory=list)
    predecessors: list[int] = field(default_factory=list)

    @property
    def length(self) -> int:
        return self.end - self.start

    def covers(self, instruction_index: int) -> bool:
        return self.start <= instruction_index < self.end

    def describe(self) -> str:
        going = ", ".join(str(successor) for successor in self.successors) or "nothing"
        return f"block {self.index} holds {self.start}..{self.end - 1} and goes to {going}"


@dataclass
class Graph:
    blocks: list[Block] = field(default_factory=list)
    program: Program | None = None

    @property
    def count(self) -> int:
        return len(self.blocks)

    def block_at(self, instruction_index: int) -> Block | None:
        for block in self.blocks:
            if block.covers(instruction_index):
                return block
        return None

    def entry(self) -> Block | None:
        return self.blocks[0] if self.blocks else None

    def exits(self) -> list[Block]:
        """Blocks control leaves the function from, having no successor."""
        return [block for block in self.blocks if not block.successors]

    def reachable(self) -> set[int]:
        if not self.blocks:
            return set()
        seen: set[int] = {0}
        pending = [0]
        while pending:
            block = self.blocks[pending.pop()]
            for successor in block.successors:
                if successor not in seen:
                    seen.add(successor)
                    pending.append(successor)
        return seen

    def unreachable(self) -> list[int]:
        found = self.reachable()
        return [block.index for block in self.blocks if block.index not in found]

    def describe(self) -> list[str]:
        return [block.describe() for block in self.blocks]


def _boundaries(program: Program) -> list[int]:
    """Every instruction index that begins a block."""
    instructions = program.instructions
    if not instructions:
        return []
    starts = {0}
    for index, instruction in enumerate(instructions):
        if instruction.target is not None:
            starts.add(instruction.target)
        if instruction.opcode in _ENDS_A_BLOCK and index + 1 < len(instructions):
            starts.add(index + 1)
    return sorted(start for start in starts if start < len(instructions))


def _successors_of(instruction: Instruction, next_index: int) -> list[int]:
    opcode = instruction.opcode
    if opcode == OpCode.PUSH_HANDLER:
        # one edge for the protected path and one for the catch clause, which is
        # coarse: a throw can leave from anywhere inside the region, not only here
        if instruction.target is None:
            return [next_index]
        return [next_index, instruction.target]
    if opcode in (OpCode.JUMP, OpCode.LOOP):
        return [instruction.target] if instruction.target is not None else []
    if opcode in (OpCode.JUMP_IF_FALSE, OpCode.JUMP_IF_TRUE):
        going = [next_index]
        if instruction.target is not None:
            going.append(instruction.target)
        return going
    if opcode in TERMINAL:
        return []
    return [next_index]


def build_graph(program: Program) -> Graph:
    """Group a decoded program into blocks and join them with edges."""
    instructions = program.instructions
    starts = _boundaries(program)
    if not starts:
        return Graph(blocks=[], program=program)
    graph = Graph(program=program)
    owner: dict[int, int] = {}
    for position, start in enumerate(starts):
        end = starts[position + 1] if position + 1 < len(starts) else len(instructions)
        graph.blocks.append(Block(index=position, start=start, end=end))
        owner[start] = position
    for block in graph.blocks:
        last = instructions[block.end - 1]
        for target in _successors_of(last, block.end):
            if target >= len(instructions):
                # falling off the end is the verifier's complaint, not the graph's
                continue
            successor = owner[target]
            if successor not in block.successors:
                block.successors.append(successor)
            if block.index not in graph.blocks[successor].predecessors:
                graph.blocks[successor].predecessors.append(block.index)
    return graph


def graph_of(function: object) -> Graph:
    """Build the graph for a function, decoding its chunk first."""
    chunk = function.chunk  # type: ignore[attr-defined]
    return build_graph(decode(chunk))
