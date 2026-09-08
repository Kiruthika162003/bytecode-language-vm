"""The list library: native operations that treat a list as a whole rather than one slot.

A program can already read and write a list a slot at a time, but the
common shapes of list work, take a slice, reverse it, sort it, sum it,
find an item, drop duplicates, are awkward and slow to spell out element
by element, so this module supplies them natively. The design line drawn
here is between operations that read and operations that change. The
functions that transform, slice and reversed and sorted and unique and
concat, return a brand new list and leave the argument untouched, because
a caller that wrote sorted(a) and found a itself reordered would be
justly surprised; the mutating helpers that already exist, push and pop,
are the deliberate exception and are named as actions for that reason.
The reading functions, sum and first and last and index_of and count and
contains, return a value and change nothing. Two honest constraints keep
the library predictable. Sorting and summing require the elements to be
numbers, since ordering and addition across mixed types are not defined
in this language, and a list with a non-number raises a type mismatch
rather than guessing an order. And every function validates that it was
given a list at all, so passing a map to reverse reports the mismatch
plainly instead of failing deep in the host. These are first-order
operations only; the higher-order map and filter that take a function
belong with the call machinery and are left for a later addition.
"""

from __future__ import annotations

from typing import Any

from ember.errors import IndexRange, TypeMismatch
from ember.valueops import type_name, values_equal


def _list(value: Any, who: str) -> list[Any]:
    if not isinstance(value, list):
        raise TypeMismatch(f"{who} needs a list, not a {type_name(value)}")
    return value


def _numbers(values: list[Any], who: str) -> None:
    for value in values:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise TypeMismatch(f"{who} needs every element to be a number")


def _first(args: list[Any]) -> Any:
    items = _list(args[0], "first")
    if not items:
        raise IndexRange("first needs a non-empty list")
    return items[0]


def _last(args: list[Any]) -> Any:
    items = _list(args[0], "last")
    if not items:
        raise IndexRange("last needs a non-empty list")
    return items[-1]


def _slice(args: list[Any]) -> list[Any]:
    items = _list(args[0], "slice")
    start, end = args[1], args[2]
    for value in (start, end):
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeMismatch("slice needs integer start and end positions")
    if start < 0 or end > len(items) or start > end:
        raise IndexRange(
            f"the range {start} to {end} is not valid for a list of length "
            f"{len(items)}"
        )
    return items[start:end]


def _reversed(args: list[Any]) -> list[Any]:
    return list(reversed(_list(args[0], "reversed")))


def _sorted(args: list[Any]) -> list[Any]:
    items = _list(args[0], "sorted")
    _numbers(items, "sorted")
    return sorted(items)


def _unique(args: list[Any]) -> list[Any]:
    items = _list(args[0], "unique")
    result: list[Any] = []
    for item in items:
        if not any(values_equal(item, seen) for seen in result):
            result.append(item)
    return result


def _concat(args: list[Any]) -> list[Any]:
    left = _list(args[0], "concat")
    right = _list(args[1], "concat")
    return left + right


def _sum(args: list[Any]) -> Any:
    items = _list(args[0], "sum")
    _numbers(items, "sum")
    total: Any = 0
    for item in items:
        total = total + item
    return total


def _list_index_of(args: list[Any]) -> int:
    items = _list(args[0], "list_index_of")
    target = args[1]
    for index, item in enumerate(items):
        if values_equal(item, target):
            return index
    return -1


def _count(args: list[Any]) -> int:
    items = _list(args[0], "count")
    target = args[1]
    return sum(1 for item in items if values_equal(item, target))


_REGISTRY: dict[str, tuple[int, Any]] = {
    "first": (1, _first),
    "last": (1, _last),
    "slice": (3, _slice),
    "reversed": (1, _reversed),
    "sorted": (1, _sorted),
    "unique": (1, _unique),
    "concat": (2, _concat),
    "sum": (1, _sum),
    "list_index_of": (2, _list_index_of),
    "count": (2, _count),
}


def install_list_library(machine: Any) -> None:
    for name, (arity, handler) in _REGISTRY.items():
        machine.define_native(name, arity, handler)


def list_names() -> list[str]:
    return sorted(_REGISTRY)
