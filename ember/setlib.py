"""Set operations over lists, because the language has no set type and deliberately so.

A set is a list whose elements are distinct, and that is the whole of the model
here. Adding a real set type would mean a new runtime value, a new type name, a
new printed form, a new equality rule, and a new entry in every place the machine
switches on what a value is, and all of that to gain what these functions provide
over lists a program already knows how to build, print, and iterate. So the
decision is to keep the value model small and supply the operations instead:
union, intersection, difference, symmetric difference, and the three containment
questions. Every function returns a fresh list with distinct elements and never
mutates an argument. The honest cost is complexity, and it is worth naming
plainly rather than hiding. Membership in a list is a scan, so union and
intersection are quadratic in the sizes involved where a hash-backed set would be
linear; for the tens of elements these are usually asked about that is invisible,
and for tens of thousands it would not be. The other cost is that element order is
preserved rather than arbitrary, which is nicer to read and to test but means
these are not sets in the mathematical sense of unordered collections; two results
that are equal as sets can differ as lists, so comparing them with equality
compares order too, and is_subset in both directions is the way to ask the
question a mathematician would.
"""

from __future__ import annotations

from typing import Any

from ember.errors import TypeMismatch
from ember.valueops import type_name, values_equal


def _list(value: Any, who: str) -> list[Any]:
    if not isinstance(value, list):
        raise TypeMismatch(f"{who} needs a list, not a {type_name(value)}")
    return value


def _contains(items: list[Any], candidate: Any) -> bool:
    return any(values_equal(existing, candidate) for existing in items)


def _distinct(items: list[Any]) -> list[Any]:
    result: list[Any] = []
    for item in items:
        if not _contains(result, item):
            result.append(item)
    return result


def _union(args: list[Any]) -> list[Any]:
    left = _list(args[0], "union")
    right = _list(args[1], "union")
    return _distinct(left + right)


def _intersect(args: list[Any]) -> list[Any]:
    left = _list(args[0], "intersect")
    right = _list(args[1], "intersect")
    return [item for item in _distinct(left) if _contains(right, item)]


def _difference(args: list[Any]) -> list[Any]:
    left = _list(args[0], "difference")
    right = _list(args[1], "difference")
    return [item for item in _distinct(left) if not _contains(right, item)]


def _symmetric_difference(args: list[Any]) -> list[Any]:
    left = _list(args[0], "symmetric_difference")
    right = _list(args[1], "symmetric_difference")
    only_left = [item for item in _distinct(left) if not _contains(right, item)]
    only_right = [item for item in _distinct(right) if not _contains(left, item)]
    return only_left + only_right


def _is_subset(args: list[Any]) -> bool:
    left = _list(args[0], "is_subset")
    right = _list(args[1], "is_subset")
    return all(_contains(right, item) for item in left)


def _is_superset(args: list[Any]) -> bool:
    left = _list(args[0], "is_superset")
    right = _list(args[1], "is_superset")
    return all(_contains(left, item) for item in right)


def _is_disjoint(args: list[Any]) -> bool:
    left = _list(args[0], "is_disjoint")
    right = _list(args[1], "is_disjoint")
    return not any(_contains(right, item) for item in left)


def _as_set(args: list[Any]) -> list[Any]:
    return _distinct(_list(args[0], "as_set"))


_REGISTRY: dict[str, tuple[int, Any]] = {
    "union": (2, _union),
    "intersect": (2, _intersect),
    "difference": (2, _difference),
    "symmetric_difference": (2, _symmetric_difference),
    "is_subset": (2, _is_subset),
    "is_superset": (2, _is_superset),
    "is_disjoint": (2, _is_disjoint),
    "as_set": (1, _as_set),
}


def install_set_library(machine: Any) -> None:
    for name, (arity, handler) in _REGISTRY.items():
        machine.define_native(name, arity, handler)


def set_names() -> list[str]:
    return sorted(_REGISTRY)
