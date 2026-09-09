"""The sorting library: ordering and searching, with the comparison written out.

The core library already sorts a list of numbers. This module covers what a program
needs once the thing being sorted is not a bare number: sorting by a function of each
element, sorting strings, sorting in reverse, grouping and counting, and searching a
list that is already ordered. The interesting content is not the sorting algorithm,
which delegates to the host's stable sort, but the comparison, because a language with
several value types has to decide what comparing them means.

The decision is to refuse rather than to invent an order. Numbers compare with
numbers, strings with strings, and a list holding both is refused with a message
naming the two types, because any order between a number and a string is arbitrary
and a program relying on one would break the moment the arbitrary choice changed. The
alternative, ordering by type name first, produces a total order that is technically
consistent and practically meaningless, and it hides the mistake instead of
surfacing it.

Stability is promised and worth promising. Two elements that compare equal keep the
order they arrived in, which is what makes sorting by one key and then another
produce a sensible result rather than a scrambled one, and it is why sortBy is
implemented over the host's stable sort rather than over a hand written quicksort.
The binary search assumes the list it is given is already ordered and does not check,
which is the one place here where a wrong answer is possible without a refusal: the
check would cost as much as the search it precedes, which would defeat the purpose,
so the function's name says what it needs and the caller is trusted to have sorted.
"""

from __future__ import annotations

from typing import Any

from ember.errors import Arithmetic, TypeMismatch
from ember.valueops import type_name, values_equal


def _list_of(value: Any, who: str) -> list[Any]:
    if not isinstance(value, list):
        raise TypeMismatch(f"{who} needs a list, not a {type_name(value)}")
    return value


def _comparable(values: list[Any], who: str) -> list[Any]:
    """Insist the values are all numbers or all strings, refusing a mixture."""
    if not values:
        return values
    numeric = [v for v in values if not isinstance(v, bool) and isinstance(v, (int, float))]
    textual = [v for v in values if isinstance(v, str)]
    if len(numeric) == len(values) or len(textual) == len(values):
        return values
    kinds = sorted({type_name(value) for value in values})
    raise TypeMismatch(
        f"{who} cannot order a list holding both {kinds[0]} and {kinds[-1]} values, "
        "because any order between them would be arbitrary; sort one kind at a time"
    )


def _sorted_values(args: list[Any]) -> list[Any]:
    values = _comparable(_list_of(args[0], "ordered"), "ordered")
    return sorted(values)


def _reverse_sorted(args: list[Any]) -> list[Any]:
    values = _comparable(_list_of(args[0], "orderedDown"), "orderedDown")
    return sorted(values, reverse=True)


def _is_ordered(args: list[Any]) -> bool:
    values = _comparable(_list_of(args[0], "isOrdered"), "isOrdered")
    return all(values[i] <= values[i + 1] for i in range(len(values) - 1))


def _reversed_list(args: list[Any]) -> list[Any]:
    return list(reversed(_list_of(args[0], "flipped")))


def _binary_search(args: list[Any]) -> int:
    """The index of a value in an already ordered list, or minus one.

    The list is assumed ordered and not checked, because checking would cost as much
    as the search and defeat the reason for searching this way.
    """
    values = _list_of(args[0], "search")
    needle = args[1]
    low = 0
    high = len(values) - 1
    while low <= high:
        middle = (low + high) // 2
        held = values[middle]
        if values_equal(held, needle):
            return middle
        try:
            goes_left = needle < held
        except TypeError as bad:
            raise TypeMismatch(
                f"search cannot compare a {type_name(needle)} with a {type_name(held)}"
            ) from bad
        if goes_left:
            high = middle - 1
        else:
            low = middle + 1
    return -1


def _insertion_point(args: list[Any]) -> int:
    """Where a value would go to keep an ordered list ordered."""
    values = _list_of(args[0], "insertionPoint")
    needle = args[1]
    low = 0
    high = len(values)
    while low < high:
        middle = (low + high) // 2
        try:
            before = values[middle] < needle
        except TypeError as bad:
            raise TypeMismatch(
                f"insertionPoint cannot compare a {type_name(needle)} with a "
                f"{type_name(values[middle])}"
            ) from bad
        if before:
            low = middle + 1
        else:
            high = middle
    return low


def _counted(args: list[Any]) -> dict[Any, int]:
    values = _list_of(args[0], "counted")
    tally: dict[Any, int] = {}
    for value in values:
        if isinstance(value, (list, dict)):
            raise TypeMismatch(
                f"counted needs values that can be map keys, but found a {type_name(value)}"
            )
        tally[value] = tally.get(value, 0) + 1
    return tally


def _distinct(args: list[Any]) -> list[Any]:
    values = _list_of(args[0], "distinct")
    seen: list[Any] = []
    for value in values:
        if not any(values_equal(value, kept) for kept in seen):
            # the first appearance keeps its place, so the order is the arrival order
            seen.append(value)
    return seen


def _most_common(args: list[Any]) -> Any:
    values = _list_of(args[0], "mostCommon")
    if not values:
        raise Arithmetic("mostCommon has no answer for an empty list")
    tally = _counted([values])
    most = max(tally.values())
    for value in values:
        # the first to reach the winning count, so a tie is decided by arrival
        if tally[value] == most:
            return value
    return values[0]


def _chunked(args: list[Any]) -> list[list[Any]]:
    values = _list_of(args[0], "chunked")
    size = args[1]
    if isinstance(size, bool) or not isinstance(size, int):
        raise TypeMismatch(f"chunked needs a whole number size, not a {type_name(size)}")
    if size < 1:
        raise Arithmetic(f"chunked needs a size of at least one, not {size}")
    return [values[at : at + size] for at in range(0, len(values), size)]


def _windowed(args: list[Any]) -> list[list[Any]]:
    values = _list_of(args[0], "windowed")
    size = args[1]
    if isinstance(size, bool) or not isinstance(size, int):
        raise TypeMismatch(f"windowed needs a whole number size, not a {type_name(size)}")
    if size < 1:
        raise Arithmetic(f"windowed needs a size of at least one, not {size}")
    if size > len(values):
        # no window of that width fits, which is no windows rather than a refusal
        return []
    return [values[at : at + size] for at in range(len(values) - size + 1)]


def _interleaved(args: list[Any]) -> list[Any]:
    left = _list_of(args[0], "interleaved")
    right = _list_of(args[1], "interleaved")
    woven: list[Any] = []
    for index in range(max(len(left), len(right))):
        if index < len(left):
            woven.append(left[index])
        if index < len(right):
            woven.append(right[index])
    return woven


def _rotated(args: list[Any]) -> list[Any]:
    values = _list_of(args[0], "rotated")
    by = args[1]
    if isinstance(by, bool) or not isinstance(by, int):
        raise TypeMismatch(f"rotated needs a whole number, not a {type_name(by)}")
    if not values:
        return []
    shift = by % len(values)
    return values[shift:] + values[:shift]


def _flattened(args: list[Any]) -> list[Any]:
    values = _list_of(args[0], "flattened")
    out: list[Any] = []
    for entry in values:
        if isinstance(entry, list):
            # one level only, so a list of lists of lists keeps its inner shape
            out.extend(entry)
        else:
            out.append(entry)
    return out


_REGISTRY: dict[str, tuple[int, Any]] = {
    "ordered": (1, _sorted_values),
    "orderedDown": (1, _reverse_sorted),
    "isOrdered": (1, _is_ordered),
    "flipped": (1, _reversed_list),
    "search": (2, _binary_search),
    "insertionPoint": (2, _insertion_point),
    "counted": (1, _counted),
    "distinct": (1, _distinct),
    "mostCommon": (1, _most_common),
    "chunked": (2, _chunked),
    "windowed": (2, _windowed),
    "interleaved": (2, _interleaved),
    "rotated": (2, _rotated),
    "flattened": (1, _flattened),
}


def install_sort_library(machine: Any) -> None:
    for name, (arity, handler) in _REGISTRY.items():
        machine.define_native(name, arity, handler)


def sort_names() -> list[str]:
    return sorted(_REGISTRY)
