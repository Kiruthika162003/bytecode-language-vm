"""Printing a nested value so a person can read it, which the ordinary printing does not.

The language prints a value on one line, which is right for a number and wrong for a map of
lists of maps. Past a certain depth a single line stops being readable at all: the eye cannot
match a bracket to its partner, and the thing a reader wants to know, what shape is this, is
exactly what the line hides. This module prints the same values across several lines with the
nesting shown by indentation.

The interesting decision is when not to. A list of three numbers is more readable on one line
than on five, so a value is only broken across lines when it does not fit a width, and a value
that fits is printed exactly as the ordinary printing would print it. That makes the output
adaptive: the shallow parts of a structure stay compact and the deep parts open up, which is
what someone reading it actually wants. The rule is applied from the inside out, so a small map
inside a large one stays on its line while the map around it breaks.

Cycles have to be handled because a value can hold itself, and the choice is to print a marker
naming the depth at which the repeat was found rather than to refuse or to recurse for ever.
Refusing would make the function useless for exactly the structures that most need looking at,
and a marker tells a reader the thing they need to know, which is that the structure loops.

Two smaller decisions. Map keys are printed in the order the map holds them rather than sorted,
because that order is the insertion order and it usually carries meaning a sort would destroy;
a caller who wants them sorted can sort them. And the output never ends with a trailing comma
on its last entry, which costs a little care in the joining and means the result can be pasted
back into a program.
"""

from __future__ import annotations

from typing import Any

from ember.errors import Arithmetic, TypeMismatch
from ember.valueops import stringify, type_name

_NEWLINE = chr(10)
_DEFAULT_WIDTH = 72
_DEFAULT_INDENT = 2
_MAX_DEPTH = 40


def _width_of(value: Any, who: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeMismatch(f"{who} needs a whole number width, not a {type_name(value)}")
    if value < 1:
        raise Arithmetic(f"{who} needs a width of at least one, not {value}")
    return value


def _nested(value: Any) -> str:
    """One value as it appears inside a collection, where a string keeps its quotes.

    The language prints a bare string at the top level and a quoted one inside a
    list, and matching that matters: this printing is the same values laid out over
    several lines, so anything it shows differently from print would be misleading.
    """
    if isinstance(value, str):
        return chr(34) + value + chr(34)
    return stringify(value)


def _flat(value: Any, seen: frozenset[int], top: bool = False) -> str:
    """The one line form, which is what the ordinary printing produces."""
    if id(value) in seen and isinstance(value, (list, dict)):
        return "<repeats>"
    if isinstance(value, list):
        inner = frozenset({*seen, id(value)})
        return "[" + ", ".join(_flat(one, inner) for one in value) + "]"
    if isinstance(value, dict):
        inner = frozenset({*seen, id(value)})
        pieces = [
            f"{_flat(key, inner)}: {_flat(held, inner)}" for key, held in value.items()
        ]
        return "{" + ", ".join(pieces) + "}"
    return stringify(value) if top else _nested(value)


def _render(
    value: Any, width: int, step: int, depth: int, seen: frozenset[int]
) -> list[str]:
    if depth > _MAX_DEPTH:
        return ["<too deep>"]
    if isinstance(value, (list, dict)) and id(value) in seen:
        # a marker rather than a refusal: the reader needs to know it loops, and
        # refusing would be useless for exactly the structures worth looking at
        return [f"<repeats at depth {depth}>"]
    flat = _flat(value, seen)
    if len(flat) + depth * step <= width or not isinstance(value, (list, dict)):
        # what fits is printed as the ordinary printing would print it
        return [flat]
    inner = frozenset({*seen, id(value)})
    pad = " " * step
    if isinstance(value, list):
        lines = ["["]
        for index, one in enumerate(value):
            rendered = _render(one, width, step, depth + 1, inner)
            tail = "," if index < len(value) - 1 else ""
            lines.extend(pad + line for line in rendered[:-1])
            lines.append(pad + rendered[-1] + tail)
        lines.append("]")
        return lines
    lines = ["{"]
    entries = list(value.items())
    for index, (key, held) in enumerate(entries):
        rendered = _render(held, width, step, depth + 1, inner)
        tail = "," if index < len(entries) - 1 else ""
        opening = f"{pad}{_flat(key, inner)}: {rendered[0]}"
        if len(rendered) == 1:
            lines.append(opening + tail)
            continue
        lines.append(opening)
        lines.extend(pad + line for line in rendered[1:-1])
        lines.append(pad + rendered[-1] + tail)
    lines.append("}")
    return lines


def pretty(value: Any, width: int = _DEFAULT_WIDTH, step: int = _DEFAULT_INDENT) -> str:
    return _NEWLINE.join(_render(value, width, step, 0, frozenset()))


def _pretty(args: list[Any]) -> str:
    return pretty(args[0])


def _pretty_to(args: list[Any]) -> str:
    return pretty(args[0], _width_of(args[1], "prettyTo"))


def _pretty_lines(args: list[Any]) -> list[str]:
    return _render(args[0], _DEFAULT_WIDTH, _DEFAULT_INDENT, 0, frozenset())


def _fits(args: list[Any]) -> bool:
    """Whether a value prints on one line inside a width, which is why it may not break."""
    return len(_flat(args[0], frozenset())) <= _width_of(args[1], "fitsWidth")


def _one_line(args: list[Any]) -> str:
    return _flat(args[0], frozenset(), top=True)


def _depth_of(args: list[Any]) -> int:
    """How deeply a value nests, which says whether printing it flat will be readable."""
    def measure(one: Any, seen: frozenset[int]) -> int:
        if not isinstance(one, (list, dict)) or id(one) in seen:
            return 0
        inner = frozenset({*seen, id(one)})
        parts = list(one.values()) if isinstance(one, dict) else list(one)
        return 1 + max((measure(part, inner) for part in parts), default=0)

    return measure(args[0], frozenset())


def _counts(args: list[Any]) -> dict[str, int]:
    """How many values of each kind a structure holds, counted once each."""
    found: dict[str, int] = {}
    seen: set[int] = set()
    pending = [args[0]]
    while pending:
        one = pending.pop()
        if isinstance(one, (list, dict)):
            if id(one) in seen:
                continue
            seen.add(id(one))
            pending.extend(one if isinstance(one, list) else [*one.keys(), *one.values()])
        found[type_name(one)] = found.get(type_name(one), 0) + 1
    return found


def _has_cycle(args: list[Any]) -> bool:
    def walk(one: Any, path: frozenset[int]) -> bool:
        if not isinstance(one, (list, dict)):
            return False
        if id(one) in path:
            return True
        inner = frozenset({*path, id(one)})
        parts = list(one.values()) if isinstance(one, dict) else list(one)
        return any(walk(part, inner) for part in parts)

    return walk(args[0], frozenset())


_REGISTRY: dict[str, tuple[int, Any]] = {
    "pretty": (1, _pretty),
    "prettyTo": (2, _pretty_to),
    "prettyLines": (1, _pretty_lines),
    "fitsWidth": (2, _fits),
    "oneLine": (1, _one_line),
    "valueDepth": (1, _depth_of),
    "valueCounts": (1, _counts),
    "hasCycle": (1, _has_cycle),
}


def install_pretty_library(machine: Any) -> None:
    for name, (arity, handler) in _REGISTRY.items():
        machine.define_native(name, arity, handler)


def pretty_names() -> list[str]:
    return sorted(_REGISTRY)
