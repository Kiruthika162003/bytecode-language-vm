"""Dominance: which blocks are guaranteed to have run by the time another one does.

One block dominates another when every path from the entry to the second passes
through the first, and that single relation answers a surprising number of
questions. It says where a computation can be hoisted to, because a block that
dominates every use of a value is a place the value can be computed once. It says
which blocks form a loop, because a backward edge to a block that dominates its
source is exactly what a loop is. And it says where a value must be defined for a
use to be safe. The algorithm here is the iterative one: start by assuming every
block is dominated by all of them, then repeatedly narrow each block's set to the
intersection of its predecessors' sets plus itself, until nothing changes. It is
not the fastest known method and the choice is deliberate. The near linear
algorithms are considerably harder to read and to be sure of, the graphs here have
tens of blocks rather than thousands, and a dominance computation that is subtly
wrong would corrupt every pass built on it while looking plausible. Iteration to a
fixed point is slower and obviously correct.

Loop detection is where the payoff shows. A backward edge whose destination
dominates its source identifies a loop, and the loop's body is everything that can
reach the edge's source without leaving the destination, which is a backward walk
from the source stopping at the header. Nesting then falls out of containment
rather than needing separate tracking: a loop inside another has a body that is a
subset of the outer body, so sorting by size and asking which contains which
recovers the nesting the source code had. What this does not detect is a loop with
two entry points, because such a loop has no single dominating header. The compiler
cannot produce one, since every loop it emits comes from a while or a for with one
way in, so the gap is real but unreachable from Ember source; it would only appear
in bytecode assembled by hand.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ember.cfg import Graph


@dataclass
class Loop:
    """A header block and every block that can reach back to it."""

    header: int
    latch: int
    body: set[int] = field(default_factory=set)

    @property
    def size(self) -> int:
        return len(self.body)

    def contains(self, other: Loop) -> bool:
        return other.header != self.header and other.body <= self.body

    def describe(self) -> str:
        listed = ", ".join(str(block) for block in sorted(self.body))
        return f"loop headed at block {self.header} covering {listed}"


def dominators(graph: Graph) -> dict[int, set[int]]:
    """For each block, every block that must have run before it."""
    if not graph.blocks:
        return {}
    reachable = graph.reachable()
    everything = set(reachable)
    found: dict[int, set[int]] = {}
    for block in graph.blocks:
        if block.index not in reachable:
            continue
        found[block.index] = {block.index} if block.index == 0 else set(everything)
    changed = True
    while changed:
        changed = False
        for block in graph.blocks:
            if block.index == 0 or block.index not in reachable:
                continue
            incoming = [
                found[predecessor]
                for predecessor in block.predecessors
                if predecessor in found
            ]
            if incoming:
                narrowed = set(incoming[0])
                for candidate in incoming[1:]:
                    narrowed &= candidate
            else:
                # unreachable except through nothing, so it dominates only itself
                narrowed = set()
            narrowed.add(block.index)
            if narrowed != found[block.index]:
                found[block.index] = narrowed
                changed = True
    return found


def dominates(graph: Graph, earlier: int, later: int) -> bool:
    found = dominators(graph)
    return earlier in found.get(later, set())


def immediate_dominator(graph: Graph, block: int) -> int | None:
    """The closest block that dominates this one, which is its parent in the tree."""
    found = dominators(graph)
    candidates = found.get(block, set()) - {block}
    if not candidates:
        return None
    # the immediate one is the candidate dominated by every other candidate
    for candidate in candidates:
        others = candidates - {candidate}
        if all(other in found.get(candidate, set()) for other in others):
            return candidate
    return None


def dominator_tree(graph: Graph) -> dict[int, list[int]]:
    """Each block mapped to the blocks it immediately dominates."""
    tree: dict[int, list[int]] = {block.index: [] for block in graph.blocks}
    for block in graph.blocks:
        parent = immediate_dominator(graph, block.index)
        if parent is not None:
            tree[parent].append(block.index)
    return tree


def back_edges(graph: Graph) -> list[tuple[int, int]]:
    """Edges pointing at a block that dominates their source, which are loops."""
    found = dominators(graph)
    edges: list[tuple[int, int]] = []
    for block in graph.blocks:
        for successor in block.successors:
            if successor in found.get(block.index, set()):
                edges.append((block.index, successor))
    return edges


def _body_of(graph: Graph, latch: int, header: int) -> set[int]:
    body = {header, latch}
    pending = [latch]
    while pending:
        current = pending.pop()
        if current == header:
            continue
        for predecessor in graph.blocks[current].predecessors:
            if predecessor not in body:
                body.add(predecessor)
                pending.append(predecessor)
    return body


def loops(graph: Graph) -> list[Loop]:
    """Every loop in the graph, largest first so nesting reads outward in."""
    found = [
        Loop(header=header, latch=latch, body=_body_of(graph, latch, header))
        for latch, header in back_edges(graph)
    ]
    return sorted(found, key=lambda loop: (-loop.size, loop.header))


def loop_depth(graph: Graph) -> dict[int, int]:
    """How many loops each block sits inside, which is its nesting depth."""
    found = loops(graph)
    depth = {block.index: 0 for block in graph.blocks}
    for loop in found:
        for block in loop.body:
            depth[block] = depth.get(block, 0) + 1
    return depth


def deepest_nesting(graph: Graph) -> int:
    depth = loop_depth(graph)
    return max(depth.values()) if depth else 0
