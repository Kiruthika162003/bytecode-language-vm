"""Heaps: keeping the smallest thing findable without keeping everything sorted.

A binary heap is the data structure for the question what is the smallest thing here,
asked repeatedly while things are added and removed. It answers in constant time and
maintains itself in logarithmic time, which is what makes a priority queue possible, and
the reason it is worth having in a language whose lists are otherwise flat is that the
alternatives are both bad: sorting after every insertion costs more than the heap does,
and scanning for the minimum costs more per query than the heap costs per update.

A heap here is an ordinary list, not a new type, and that decision shapes the interface.
The invariant is a property of the list's contents, that each element is no larger than
its two children at twice its index plus one and two, so any list can be asked whether
it holds and any list can be made to hold it. The advantage is that a program can print
a heap, store it, serialise it to JSON, and pass it to anything that takes a list. The
cost is that nothing prevents a program from breaking the invariant by writing to the
list directly, and then the answers become wrong rather than refused. So the functions
that need the invariant check it, which turns a silent wrong answer into a refusal that
names the problem, and the check costs a full pass, which is why it happens on the
operations that would otherwise mislead rather than on every one.

Every operation returns a new list rather than modifying the one it was given. That is
the more expensive choice, copying the list on each push and pop where an in place heap
would not, and it is the right one for this language: assignment shares a list rather
than copying it, so a mutating push would change every binding that shares the list,
which is a class of bug that is very hard to find. Nothing here is ordered by a caller
supplied comparison, because natives cannot take a function in this language's calling
convention; a program needing to order by something other than the natural order pairs
each value with its key in a two element list, which orders by the key first.
"""

from __future__ import annotations

from typing import Any

from ember.errors import Arithmetic, TypeMismatch
from ember.valueops import type_name


def _list_of(value: Any, who: str) -> list[Any]:
    if not isinstance(value, list):
        raise TypeMismatch(f"{who} needs a list, not a {type_name(value)}")
    return value


def _comparable(values: list[Any], who: str) -> list[Any]:
    """Insist the values can be ordered against one another."""
    if len(values) < 2:
        return values
    first = values[0]
    for value in values[1:]:
        try:
            _ = value < first
        except TypeError as bad:
            raise TypeMismatch(
                f"{who} cannot order a {type_name(value)} against a {type_name(first)}"
            ) from bad
    return values


def holds_invariant(values: list[Any]) -> bool:
    """Whether every element is no larger than its children."""
    for parent in range(len(values)):
        for child in (2 * parent + 1, 2 * parent + 2):
            if child < len(values):
                try:
                    if values[child] < values[parent]:
                        return False
                except TypeError:
                    return False
    return True


def _demand_heap(values: list[Any], who: str) -> list[Any]:
    if not holds_invariant(values):
        raise Arithmetic(
            f"{who} was given a list that is not a heap, so its answer would be wrong "
            "rather than merely unsorted; pass it through heapify first"
        )
    return values


def _sift_down(values: list[Any], at: int) -> None:
    count = len(values)
    while True:
        smallest = at
        for child in (2 * at + 1, 2 * at + 2):
            if child < count and values[child] < values[smallest]:
                smallest = child
        if smallest == at:
            return
        values[at], values[smallest] = values[smallest], values[at]
        at = smallest


def _sift_up(values: list[Any], at: int) -> None:
    while at > 0:
        parent = (at - 1) // 2
        if not values[at] < values[parent]:
            return
        values[at], values[parent] = values[parent], values[at]
        at = parent


def _heapify(args: list[Any]) -> list[Any]:
    """Rearrange a list into a heap, working up from the last parent."""
    values = list(_comparable(_list_of(args[0], "heapify"), "heapify"))
    # starting at the last parent and sifting down is linear, where pushing each
    # element in turn would be logarithmic per element
    for at in range(len(values) // 2 - 1, -1, -1):
        _sift_down(values, at)
    return values


def _heap_push(args: list[Any]) -> list[Any]:
    values = list(_demand_heap(_list_of(args[0], "heapPush"), "heapPush"))
    values.append(args[1])
    _comparable(values, "heapPush")
    _sift_up(values, len(values) - 1)
    return values


def _heap_pop(args: list[Any]) -> list[Any]:
    """The heap with its smallest element removed, which is a list not the element."""
    values = list(_demand_heap(_list_of(args[0], "heapPop"), "heapPop"))
    if not values:
        raise Arithmetic("heapPop has nothing to remove, because the heap is empty")
    last = values.pop()
    if values:
        values[0] = last
        _sift_down(values, 0)
    return values


def _heap_peek(args: list[Any]) -> Any:
    values = _demand_heap(_list_of(args[0], "heapPeek"), "heapPeek")
    if not values:
        raise Arithmetic("heapPeek has nothing to show, because the heap is empty")
    return values[0]


def _heap_replace(args: list[Any]) -> list[Any]:
    """Remove the smallest and add a value in one pass, which is cheaper than both."""
    values = list(_demand_heap(_list_of(args[0], "heapReplace"), "heapReplace"))
    if not values:
        raise Arithmetic("heapReplace has nothing to replace, because the heap is empty")
    values[0] = args[1]
    _comparable(values, "heapReplace")
    _sift_down(values, 0)
    return values


def _is_heap(args: list[Any]) -> bool:
    return holds_invariant(_list_of(args[0], "isHeap"))


def _heap_sorted(args: list[Any]) -> list[Any]:
    """Every element in order, by emptying a heap one element at a time."""
    values = _heapify([_list_of(args[0], "heapSorted")])
    drawn: list[Any] = []
    while values:
        drawn.append(values[0])
        values = _heap_pop([values])
    return drawn


def _smallest(args: list[Any]) -> list[Any]:
    values = _list_of(args[0], "smallest")
    count = args[1]
    if isinstance(count, bool) or not isinstance(count, int):
        raise TypeMismatch(f"smallest needs a whole number count, not a {type_name(count)}")
    if count < 0:
        raise Arithmetic(f"smallest needs a count of zero or more, not {count}")
    return _heap_sorted([values])[:count]


def _largest(args: list[Any]) -> list[Any]:
    values = _list_of(args[0], "largest")
    count = args[1]
    if isinstance(count, bool) or not isinstance(count, int):
        raise TypeMismatch(f"largest needs a whole number count, not a {type_name(count)}")
    if count < 0:
        raise Arithmetic(f"largest needs a count of zero or more, not {count}")
    ordered = _heap_sorted([values])
    return list(reversed(ordered))[:count]


def _heap_merge(args: list[Any]) -> list[Any]:
    """One heap holding everything from two, built in one pass rather than by pushing."""
    left = _demand_heap(_list_of(args[0], "heapMerge"), "heapMerge")
    right = _demand_heap(_list_of(args[1], "heapMerge"), "heapMerge")
    return _heapify([[*left, *right]])


def _heap_size(args: list[Any]) -> int:
    return len(_list_of(args[0], "heapSize"))


def _heap_empty(args: list[Any]) -> bool:
    return not _list_of(args[0], "heapEmpty")


def _heap_depth(args: list[Any]) -> int:
    """How many levels the heap has, which bounds the cost of a push or a pop."""
    count = len(_list_of(args[0], "heapDepth"))
    depth = 0
    while (1 << depth) - 1 < count:
        depth += 1
    return depth


_REGISTRY: dict[str, tuple[int, Any]] = {
    "heapify": (1, _heapify),
    "heapPush": (2, _heap_push),
    "heapPop": (1, _heap_pop),
    "heapPeek": (1, _heap_peek),
    "heapReplace": (2, _heap_replace),
    "isHeap": (1, _is_heap),
    "heapSorted": (1, _heap_sorted),
    "smallest": (2, _smallest),
    "largest": (2, _largest),
    "heapMerge": (2, _heap_merge),
    "heapSize": (1, _heap_size),
    "heapEmpty": (1, _heap_empty),
    "heapDepth": (1, _heap_depth),
}


def install_heap_library(machine: Any) -> None:
    for name, (arity, handler) in _REGISTRY.items():
        machine.define_native(name, arity, handler)


def heap_names() -> list[str]:
    return sorted(_REGISTRY)
