"""Rendering the analyses as graph text, so the shapes can be looked at rather than read.

Every graph in this project is currently a list of numbered blocks with lists of successors,
which is exactly right for a program to walk and nearly useless for a person to hold in their
head. A control flow graph of eleven blocks is not hard, and following its edges by eye through
a printed list is. This module writes those graphs in the format the graphviz tools read, so a
person can look at the picture instead.

Nothing here draws anything. Producing an image would mean either depending on a drawing
library, which this project does not do, or implementing graph layout, which is a large piece of
real work with nothing to do with a bytecode machine. Writing the text is a dozen lines and
hands the layout to a tool built for it, and a caller with no such tool still gets a listing
that is readable in itself. That is the whole design: emit the description, let something else
draw it.

What is put on each node matters more than it seems. A block labelled only by its number tells a
reader nothing, so a block carries the instructions it holds, truncated, which turns the picture
into something that can be read against the source. An unreachable block is marked, because
those are what a reader is usually looking for, and a loop header is marked, because the shape
of a loop is hard to see from edges alone once there are more than a few.

The escaping is defensive rather than necessary, which is worth being accurate about. A label
holding a quote or a backslash would produce a file the tools refuse, and no label this module
builds can hold either: a label carries opcode names and numeric operands, and a function name
comes from an identifier. Checking that was how the overclaim in this paragraph got corrected.
The escaping stays because a label that later showed a constant's value would need it, and
because the newline escaping it sits beside is genuinely required, since the instructions inside
a node are separated by newlines that the format reads as the end of the line.

Prefixing the node names when several functions are drawn together needed care and did not get
it the first time. Each function is emitted as its own cluster, and every node name has to be
made unique across the document, so a prefix goes on. Doing that by replacing the first name on
each line worked for the node declarations and quietly broke every edge, because an edge line
names two nodes and only the first was renamed: the picture drew, and its arrows pointed at
whichever nodes happened to have those names in the first cluster. The renaming is done where
the names are built now, rather than by editing the text afterwards.
"""

from __future__ import annotations

from ember.cfg import Graph, graph_of
from ember.dominators import loops
from ember.function import Function
from ember.instructions import Instruction

_NEWLINE = chr(10)
_QUOTE = chr(34)
_BACKSLASH = chr(92)
_MAX_LINES = 6


def _escaped(text: str) -> str:
    """Escape what the graph format would otherwise read as syntax."""
    return (
        text.replace(_BACKSLASH, _BACKSLASH + _BACKSLASH)
        .replace(_QUOTE, _BACKSLASH + _QUOTE)
        .replace(_NEWLINE, _BACKSLASH + "n")
    )


def _instruction_text(instruction: Instruction) -> str:
    if instruction.target is not None:
        return f"{instruction.opcode.name} -> {instruction.target}"
    if instruction.operands:
        listed = " ".join(str(operand) for operand in instruction.operands)
        return f"{instruction.opcode.name} {listed}"
    return instruction.opcode.name


def _label_of(graph: Graph, index: int) -> str:
    block = graph.blocks[index]
    if graph.program is None:
        return f"block {index}"
    instructions = graph.program.instructions[block.start : block.end]
    lines = [f"block {index}"]
    for instruction in instructions[:_MAX_LINES]:
        lines.append(_instruction_text(instruction))
    if len(instructions) > _MAX_LINES:
        lines.append(f"... {len(instructions) - _MAX_LINES} more")
    return _NEWLINE.join(lines)


def _body_of(graph: Graph, prefix: str) -> list[str]:
    """The nodes and edges of one graph, with every name carrying the prefix."""
    unreachable = set(graph.unreachable())
    headers = {found.header for found in loops(graph)}
    lines: list[str] = []
    for block in graph.blocks:
        label = _escaped(_label_of(graph, block.index))
        marks = []
        if block.index in unreachable:
            # what a reader is usually looking for
            marks.append("style=dashed")
        if block.index in headers:
            marks.append("peripheries=2")
        extra = ", " + ", ".join(marks) if marks else ""
        lines.append(f'  {prefix}b{block.index} [label="{label}"{extra}];')
    for block in graph.blocks:
        for successor in block.successors:
            # both ends carry the prefix: renaming only the first left every edge
            # pointing at whatever node held that name in another cluster
            lines.append(f"  {prefix}b{block.index} -> {prefix}b{successor};")
    return lines


def to_dot(graph: Graph, name: str = "cfg") -> str:
    """The graph as text the graphviz tools read, with the interesting blocks marked."""
    lines = [f"digraph {name} {{", "  node [shape=box];"]
    lines.extend(_body_of(graph, ""))
    lines.append("}")
    return _NEWLINE.join(lines)


def function_to_dot(function: Function, name: str = "cfg") -> str:
    return to_dot(graph_of(function), name)


def program_to_dot(function: Function) -> str:
    """Every function in a program, each as its own cluster, in one document."""
    lines = ["digraph program {", "  node [shape=box];"]
    for number, one in enumerate(_walk(function)):
        label = _escaped(one.name or "<script>")
        lines.append(f"  subgraph cluster_{number} {{")
        lines.append(f'    label="{label}";')
        # the prefix is built into the names rather than edited in afterwards
        lines.extend("  " + line for line in _body_of(graph_of(one), f"f{number}"))
        lines.append("  }")
    lines.append("}")
    return _NEWLINE.join(lines)


def _walk(function: Function) -> list[Function]:
    found = [function]
    for constant in function.chunk.constants:
        if isinstance(constant, Function):
            found.extend(_walk(constant))
    return found


def summary_of(graph: Graph) -> list[str]:
    """A plain listing for a reader with no drawing tool to hand."""
    unreachable = set(graph.unreachable())
    headers = {found.header for found in loops(graph)}
    lines: list[str] = []
    for block in graph.blocks:
        marks = []
        if block.index in unreachable:
            marks.append("unreachable")
        if block.index in headers:
            marks.append("loop header")
        note = " (" + ", ".join(marks) + ")" if marks else ""
        going = ", ".join(str(one) for one in block.successors) or "nothing"
        lines.append(f"block {block.index}{note} goes to {going}")
    return lines
