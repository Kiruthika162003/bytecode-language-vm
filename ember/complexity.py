"""Complexity: counting the paths through a function, and what the count is worth.

Cyclomatic complexity counts the independent paths through a function, and it comes
out of the control flow graph by arithmetic on edges and nodes. A function with no
branches has one path and scores one; each branch adds a node with two ways out where
there was one way, so each adds one to the score. Computing it from the graph rather
than from the syntax tree is deliberate, because the graph is what the machine will
actually follow and the tree can suggest branches the compiler folded away. The exact
arithmetic is not quite the textbook subtraction, and the reason is recorded on the
function that does it, because getting it wrong produced scores below one.

The number is useful and routinely oversold, so what it does and does not measure is
worth stating. It counts paths, which correlates with how many cases a test suite
needs, and that is its honest use: a function scoring eight needs eight tests to cover
its paths, and one scoring one needs one. It does not measure how hard a function is
to understand. A flat dispatch over ten cases scores eleven and is trivial to read; a
function scoring three whose three paths each mutate shared state can be genuinely
hard. Anyone treating the number as a difficulty score will end up splitting the
readable function and leaving the confusing one alone, so this module reports the count
and the paths it stands for and offers no threshold above which code is called bad.

Measuring from the graph has one consequence worth knowing. A condition the folding
pass evaluated at compile time is no longer a branch in the graph, so the same source
scores differently before and after optimisation, and the unoptimised figure is the one
that matches the source a person reads. Both are available, and the difference between
them is itself informative: it says how many of a function's apparent decisions were
never really decisions at all.
"""

from __future__ import annotations

from dataclasses import dataclass

from ember.cfg import Graph, graph_of
from ember.dominators import deepest_nesting, loops
from ember.function import Function
from ember.interpreter import build


def edge_count(graph: Graph) -> int:
    """Edges between blocks control can actually reach."""
    live = graph.reachable()
    return sum(
        1
        for block in graph.blocks
        if block.index in live
        for successor in block.successors
        if successor in live
    )


def node_count(graph: Graph) -> int:
    """Blocks control can reach, which is not every block the graph holds."""
    return len(graph.reachable())


def exit_count(graph: Graph) -> int:
    live = graph.reachable()
    return sum(1 for block in graph.blocks if block.index in live and not block.successors)


def complexity_of(graph: Graph) -> int:
    """The number of independent paths through the graph.

    The textbook form of this is edges minus nodes plus two, and writing it that way
    gave a function with one branch and two returns a score of zero. Two corrections
    were needed. The formula assumes a single exit, and a function returning from more
    than one place has several, so a virtual sink is added with an edge from each exit:
    that turns the count into edges minus nodes plus exits plus one. And the count must
    range over reachable blocks only, because the compiler leaves an unreachable
    nil-and-return epilogue behind a body that always returns, and counting those
    inflated the node total while contributing no edges, pushing the score below one.
    """
    if not graph.blocks:
        # nothing to walk is one path, the empty one, rather than a negative score
        return 1
    return edge_count(graph) - node_count(graph) + exit_count(graph) + 1


@dataclass(frozen=True)
class Measurement:
    """What one function's shape amounts to."""

    name: str
    paths: int
    blocks: int
    edges: int
    loops: int
    nesting: int

    def render(self) -> str:
        paths = "path" if self.paths == 1 else "paths"
        blocks = "block" if self.blocks == 1 else "blocks"
        loops = "loop" if self.loops == 1 else "loops"
        return (
            f"{self.name}: {self.paths} {paths} through {self.blocks} {blocks}, "
            f"{self.loops} {loops}, nested {self.nesting} deep"
        )

    def tests_needed(self) -> int:
        """The honest use of the number: how many tests cover every path once."""
        return self.paths


def measure_function(function: Function, name: str | None = None) -> Measurement:
    graph = graph_of(function)
    return Measurement(
        name=name or function.name or "<script>",
        paths=complexity_of(graph),
        blocks=node_count(graph),
        edges=edge_count(graph),
        loops=len(loops(graph)),
        nesting=deepest_nesting(graph),
    )


def measure_all(function: Function) -> list[Measurement]:
    """The script and every function nested in it, outermost first."""
    found = [measure_function(function)]
    for constant in function.chunk.constants:
        if isinstance(constant, Function):
            found.extend(measure_all(constant))
    return found


def measure_source(
    source: str, optimize: bool = False, peephole: bool = False
) -> list[Measurement]:
    return measure_all(build(source, optimize=optimize, peephole=peephole))


def most_complex(source: str) -> Measurement | None:
    found = measure_source(source)
    return max(found, key=lambda one: one.paths) if found else None


def total_paths(source: str) -> int:
    return sum(one.paths for one in measure_source(source))


def folding_removed(source: str) -> int:
    """How many apparent decisions were never decisions, which folding reveals."""
    before = total_paths(source)
    after = sum(one.paths for one in measure_source(source, optimize=True))
    return before - after


def report(source: str) -> list[str]:
    found = measure_source(source)
    lines = [one.render() for one in found]
    total = sum(one.paths for one in found)
    lines.append(f"{total} {'path' if total == 1 else 'paths'} in the program altogether")
    removed = folding_removed(source)
    if removed:
        lines.append(
            f"folding removes {removed} of them, which were decisions the program "
            "never actually had to make"
        )
    return lines
