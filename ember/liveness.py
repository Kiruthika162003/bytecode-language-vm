"""Liveness: which local slots still hold a value someone is going to read.

A local is live at a point if some path from there reads it before writing it
again, and the question is answered backwards for a reason worth stating plainly.
Whether a slot matters at an instruction does not depend on what came before, only
on what comes after, so the analysis flows from the exits towards the entry, which
is the opposite direction from the verifier's stack walk in the same graph. Each
block gets two sets computed from its instructions alone: the slots it reads before
writing, and the slots it writes. Those never change. Then liveness at a block's
entry is what it reads, plus whatever is live after it and it did not overwrite,
and iterating that until nothing moves gives the answer for every block at once.

The peak figure this produces was expected to be exact and is not, and measuring it
is what showed why. Declaring a local does not emit a store: the initialiser leaves
its value on the stack at exactly the offset the slot names, so the slot is written
by arithmetic rather than by an instruction. An analysis reading instructions
therefore cannot see where a local begins, only where it is read, so it treats
every declared local as live from the function's entry. On a body that computes one
local from another and returns the last, which needs two slots at once at most, the
answer came back as three: all of them, live throughout. The figure is an upper
bound rather than a measurement, and it is reported as one. Slots the compiler does
write to explicitly, reassignments, do get tracked properly, which is why a
function that assigns to a local in both arms of a branch gives a tighter answer
than one that only declares.

Dead stores are the other result, and they stay sound because they are only ever
claimed about writes the analysis can actually see. This is where the graph's
imprecision has to be respected: the handler edge records a throw as leaving only
from the instruction that pushed the handler, so a slot written inside a try block
and read only in the catch clause can look dead when it is not. Reporting such a
store as removable would be a miscompilation, so nothing inside a protected region
is ever called dead, and the reason is recorded here rather than left for whoever
later wonders why the pass goes quiet around exceptions.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ember.cfg import Graph, graph_of
from ember.opcode import OpCode

_READS = (OpCode.GET_LOCAL,)
_WRITES = (OpCode.SET_LOCAL,)


@dataclass
class BlockFacts:
    """What one block needs on entry and what it overwrites, computed once."""

    index: int
    reads: set[int] = field(default_factory=set)
    writes: set[int] = field(default_factory=set)

    def describe(self) -> str:
        needed = ", ".join(str(slot) for slot in sorted(self.reads)) or "nothing"
        return f"block {self.index} needs {needed} on entry"


def _slot_of(instruction: object) -> int | None:
    operands = instruction.operands  # type: ignore[attr-defined]
    return operands[0] if operands else None


def facts_for(graph: Graph) -> dict[int, BlockFacts]:
    """The reads-before-writes and writes of each block, which never change."""
    if graph.program is None:
        return {}
    instructions = graph.program.instructions
    found: dict[int, BlockFacts] = {}
    for block in graph.blocks:
        facts = BlockFacts(index=block.index)
        for index in range(block.start, block.end):
            instruction = instructions[index]
            slot = _slot_of(instruction)
            if slot is None:
                continue
            if instruction.opcode in _READS and slot not in facts.writes:
                # a read the block did not satisfy itself, so it needs it on entry
                facts.reads.add(slot)
            elif instruction.opcode in _WRITES:
                facts.writes.add(slot)
        found[block.index] = facts
    return found


def live_in(graph: Graph) -> dict[int, set[int]]:
    """The slots live at the entry of each block, found by iterating backwards."""
    facts = facts_for(graph)
    if not facts:
        return {}
    entering: dict[int, set[int]] = {block.index: set() for block in graph.blocks}
    changed = True
    while changed:
        changed = False
        for block in reversed(graph.blocks):
            after: set[int] = set()
            for successor in block.successors:
                after |= entering[successor]
            here = facts[block.index].reads | (after - facts[block.index].writes)
            if here != entering[block.index]:
                entering[block.index] = here
                changed = True
    return entering


def live_out(graph: Graph) -> dict[int, set[int]]:
    """The slots live where each block ends, which is the union of its successors."""
    entering = live_in(graph)
    return {
        block.index: set().union(*(entering[s] for s in block.successors))
        if block.successors
        else set()
        for block in graph.blocks
    }


def live_at(graph: Graph, instruction_index: int) -> set[int]:
    """The slots live just before one instruction runs."""
    block = graph.block_at(instruction_index)
    if block is None or graph.program is None:
        return set()
    instructions = graph.program.instructions
    live = set(live_out(graph)[block.index])
    for index in range(block.end - 1, instruction_index - 1, -1):
        instruction = instructions[index]
        slot = _slot_of(instruction)
        if slot is None:
            continue
        if instruction.opcode in _WRITES:
            live.discard(slot)
        elif instruction.opcode in _READS:
            live.add(slot)
    return live


def peak_pressure(graph: Graph) -> int:
    """An upper bound on how many slots are live at once.

    It is a bound and not a measurement because a local declaration writes its slot
    without an instruction, so a declared local looks live from the entry.
    """
    if graph.program is None:
        return 0
    counts = [
        len(live_at(graph, index)) for index in range(len(graph.program.instructions))
    ]
    return max(counts) if counts else 0


def slots_used(graph: Graph) -> set[int]:
    """Every slot the code touches, read or written."""
    facts = facts_for(graph)
    touched: set[int] = set()
    for entry in facts.values():
        touched |= entry.reads | entry.writes
    return touched


def _protected(graph: Graph) -> set[int]:
    """Blocks reachable from a handler push, where a throw makes liveness coarse."""
    if graph.program is None:
        return set()
    instructions = graph.program.instructions
    opening = [
        block.index
        for block in graph.blocks
        if instructions[block.end - 1].opcode == OpCode.PUSH_HANDLER
    ]
    if not opening:
        return set()
    covered: set[int] = set()
    pending = list(opening)
    while pending:
        current = pending.pop()
        for successor in graph.blocks[current].successors:
            if successor not in covered:
                covered.add(successor)
                pending.append(successor)
    return covered


@dataclass(frozen=True)
class DeadStore:
    index: int
    slot: int

    def render(self) -> str:
        return f"instruction {self.index} writes slot {self.slot}, which no read can see"


def dead_stores(graph: Graph) -> list[DeadStore]:
    """Writes whose value is never read, skipping anything a handler could see."""
    if graph.program is None:
        return []
    instructions = graph.program.instructions
    unsafe = _protected(graph)
    found: list[DeadStore] = []
    for block in graph.blocks:
        if block.index in unsafe:
            # a catch clause may read what looks unread here, so say nothing
            continue
        live = set(live_out(graph)[block.index])
        for index in range(block.end - 1, block.start - 1, -1):
            instruction = instructions[index]
            slot = _slot_of(instruction)
            if slot is None:
                continue
            if instruction.opcode in _WRITES:
                if slot not in live:
                    found.append(DeadStore(index=index, slot=slot))
                live.discard(slot)
            elif instruction.opcode in _READS:
                live.add(slot)
    return sorted(found, key=lambda store: store.index)


def report(function: object) -> list[str]:
    """A readable summary of what a function's frame is doing."""
    graph = graph_of(function)
    lines = [
        f"{len(slots_used(graph))} slots touched",
        f"{peak_pressure(graph)} live at the busiest point",
    ]
    lines.extend(store.render() for store in dead_stores(graph))
    return lines
