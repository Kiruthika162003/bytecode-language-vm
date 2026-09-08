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


def _whole_count(value: Any, who: str) -> int:
    """Require a non-negative integer, for the functions that take a quantity."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeMismatch(f"{who} needs an integer count, not a {type_name(value)}")
    if value < 0:
        raise IndexRange(f"{who} needs a count of zero or more")
    return value


def _take(args: list[Any]) -> list[Any]:
    items = _list(args[0], "take")
    # taking more than there is yields everything rather than failing, which is
    # what makes take usable on a list whose length the caller does not know
    return items[: _whole_count(args[1], "take")]


def _drop(args: list[Any]) -> list[Any]:
    items = _list(args[0], "drop")
    return items[_whole_count(args[1], "drop") :]


def _flatten(args: list[Any]) -> list[Any]:
    items = _list(args[0], "flatten")
    result: list[Any] = []
    for item in items:
        if isinstance(item, list):
            result.extend(item)
        else:
            result.append(item)
    # one level only, so a list of lists of lists keeps its innermost nesting;
    # flattening all the way would make the depth invisible to the caller
    return result


def _chunk(args: list[Any]) -> list[Any]:
    items = _list(args[0], "chunk")
    size = _whole_count(args[1], "chunk")
    if size == 0:
        raise IndexRange("chunk needs a size of at least one")
    return [items[start : start + size] for start in range(0, len(items), size)]


def _zip_lists(args: list[Any]) -> list[Any]:
    left = _list(args[0], "zip")
    right = _list(args[1], "zip")
    # stops at the shorter, so no position is invented to fill a gap
    return [[a, b] for a, b in zip(left, right, strict=False)]


def _repeat_list(args: list[Any]) -> list[Any]:
    items = _list(args[0], "repeat_list")
    return items * _whole_count(args[1], "repeat_list")


def _is_empty_list(args: list[Any]) -> bool:
    return not _list(args[0], "is_empty_list")


def _copy_list(args: list[Any]) -> list[Any]:
    return list(_list(args[0], "copy_list"))


def _insert(args: list[Any]) -> list[Any]:
    items = _list(args[0], "insert")
    at = args[1]
    if isinstance(at, bool) or not isinstance(at, int):
        raise TypeMismatch("insert needs an integer position")
    if not 0 <= at <= len(items):
        raise IndexRange(
            f"the position {at} is outside a list of length {len(items)}; a position "
            "equal to the length appends"
        )
    items.insert(at, args[2])
    return items


def _remove_at(args: list[Any]) -> Any:
    items = _list(args[0], "remove_at")
    at = args[1]
    if isinstance(at, bool) or not isinstance(at, int):
        raise TypeMismatch("remove_at needs an integer position")
    if not 0 <= at < len(items):
        raise IndexRange(f"the position {at} is outside a list of length {len(items)}")
    return items.pop(at)


_REGISTRY: dict[str, tuple[int, Any]] = {
    "take": (2, _take),
    "drop": (2, _drop),
    "flatten": (1, _flatten),
    "chunk": (2, _chunk),
    "zip": (2, _zip_lists),
    "repeat_list": (2, _repeat_list),
    "is_empty_list": (1, _is_empty_list),
    "copy_list": (1, _copy_list),
    "insert": (3, _insert),
    "remove_at": (2, _remove_at),
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
