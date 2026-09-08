"""The map library: operations on a map as a whole rather than one key at a time.

Indexing reaches a single entry and raises when the key is absent, which is the
right behaviour for a lookup the program believes must succeed and the wrong one
for a lookup that might not. So the first function here is get, which takes the
value to use when the key is missing and turns an absent entry from a fault into
an ordinary answer. Around that sit the operations that treat the whole map as a
value: asking whether a key is present without fetching it, removing an entry,
merging two maps, and converting between a map and a list of key-value pairs,
which is what lets a map be sorted or filtered by the list functions and then
rebuilt. The design line is the same one the list library draws. Nothing here
mutates its argument except remove, which is named as an action for that reason;
merge and invert and the conversions all return new values, because a caller who
wrote merge and found one of the inputs changed would be justly surprised. Two
honest notes. Merging is left-biased in the sense that the second map wins a
collision, which is the convention that makes merge useful for defaults, and the
choice is stated here because either answer is defensible and a reader should not
have to test to find out. And inverting a map whose values repeat loses entries,
since two keys cannot both survive as one, so the function reports how many rather
than pretending the result is the same size.
"""

from __future__ import annotations

from typing import Any

from ember.errors import IndexRange, TypeMismatch
from ember.valueops import type_name


def _map(value: Any, who: str) -> dict[Any, Any]:
    if not isinstance(value, dict):
        raise TypeMismatch(f"{who} needs a map, not a {type_name(value)}")
    return value


def _usable_key(value: Any, who: str) -> Any:
    if isinstance(value, (list, dict)):
        raise TypeMismatch(
            f"a {type_name(value)} cannot be a map key in {who}; keys must be "
            "numbers, strings, or booleans"
        )
    return value


def _has(args: list[Any]) -> bool:
    target = _map(args[0], "has")
    return _usable_key(args[1], "has") in target


def _get_or(args: list[Any]) -> Any:
    target = _map(args[0], "get")
    key = _usable_key(args[1], "get")
    # an absent key is an ordinary answer here, unlike indexing, which raises
    return target.get(key, args[2])


def _remove(args: list[Any]) -> Any:
    target = _map(args[0], "remove")
    key = _usable_key(args[1], "remove")
    if key not in target:
        raise IndexRange(f"the key {key!r} is not present, so it cannot be removed")
    return target.pop(key)


def _merge(args: list[Any]) -> dict[Any, Any]:
    first = _map(args[0], "merge")
    second = _map(args[1], "merge")
    # the second wins a collision, the convention that makes merge useful for
    # filling defaults under a caller's overrides
    combined = dict(first)
    combined.update(second)
    return combined


def _entries(args: list[Any]) -> list[list[Any]]:
    target = _map(args[0], "entries")
    return [[key, value] for key, value in target.items()]


def _from_entries(args: list[Any]) -> dict[Any, Any]:
    pairs = args[0]
    if not isinstance(pairs, list):
        raise TypeMismatch(f"from_entries needs a list, not a {type_name(pairs)}")
    result: dict[Any, Any] = {}
    for index, pair in enumerate(pairs):
        if not isinstance(pair, list) or len(pair) != 2:
            raise TypeMismatch(
                f"entry {index} is not a two-element list, so it cannot become a "
                "key and a value"
            )
        result[_usable_key(pair[0], "from_entries")] = pair[1]
    return result


def _invert(args: list[Any]) -> dict[Any, Any]:
    target = _map(args[0], "invert")
    result: dict[Any, Any] = {}
    for key, value in target.items():
        result[_usable_key(value, "invert")] = key
    return result


def _is_empty(args: list[Any]) -> bool:
    return not _map(args[0], "is_empty")


def _copy(args: list[Any]) -> dict[Any, Any]:
    return dict(_map(args[0], "copy_map"))


_REGISTRY: dict[str, tuple[int, Any]] = {
    "has": (2, _has),
    "get": (3, _get_or),
    "remove": (2, _remove),
    "merge": (2, _merge),
    "entries": (1, _entries),
    "from_entries": (1, _from_entries),
    "invert": (1, _invert),
    "is_empty": (1, _is_empty),
    "copy_map": (1, _copy),
}


def install_map_library(machine: Any) -> None:
    for name, (arity, handler) in _REGISTRY.items():
        machine.define_native(name, arity, handler)


def map_names() -> list[str]:
    return sorted(_REGISTRY)
