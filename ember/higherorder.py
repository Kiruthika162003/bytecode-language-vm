"""Higher-order library: natives that take a function and call it back into the runtime.

Every native written so far computes from plain values, which keeps it
entirely on the host side of the boundary. These are different: map, filter,
reduce and their companions receive an Ember function as an argument and have
to invoke it, which means host code calling back into the language it is
implementing. Both backends expose one method for this, so the functions here
are written once against that method and work under either, and each is
registered as needing the machine so the call site hands it over. The
re-entrancy is where the two backends diverge sharply and instructively. The
tree-walker needs nothing at all, because evaluating a call is already a
recursive descent through the host's own stack. The bytecode machine has to
push the callee and arguments exactly as compiled code would, then re-enter
its dispatch loop with a floor at the current frame depth so the loop stops
when that one call returns instead of running to the end of the program. What
these functions buy is expressiveness that first-order natives cannot reach:
a program can now say what to do with each element rather than writing the
loop and the index arithmetic every time. The honest cost is a call per
element, which for the compiled backend means a frame pushed and popped each
time, so map over a large list is measurably more expensive than the
equivalent loop; the reason to use it is clarity, not speed. Each function
validates that it was handed something callable before it starts, so a
mistyped argument is reported once rather than on the first element.
"""

from __future__ import annotations

from typing import Any

from ember.errors import IndexRange, TypeMismatch
from ember.valueops import is_truthy, type_name, values_equal

_CALLABLE_ATTRIBUTES = ("arity",)


def _check_list(value: Any, who: str) -> list[Any]:
    if not isinstance(value, list):
        raise TypeMismatch(f"{who} needs a list, not a {type_name(value)}")
    return value


def _check_callable(value: Any, who: str) -> Any:
    if not all(hasattr(value, name) for name in _CALLABLE_ATTRIBUTES):
        raise TypeMismatch(
            f"{who} needs a function as its second argument, not a {type_name(value)}"
        )
    return value


def _map(machine: Any, args: list[Any]) -> list[Any]:
    items = _check_list(args[0], "map")
    function = _check_callable(args[1], "map")
    return [machine.call_value(function, [item]) for item in items]


def _filter(machine: Any, args: list[Any]) -> list[Any]:
    items = _check_list(args[0], "filter")
    function = _check_callable(args[1], "filter")
    return [item for item in items if is_truthy(machine.call_value(function, [item]))]


def _reduce(machine: Any, args: list[Any]) -> Any:
    items = _check_list(args[0], "reduce")
    function = _check_callable(args[1], "reduce")
    total = args[2]
    for item in items:
        total = machine.call_value(function, [total, item])
    return total


def _find(machine: Any, args: list[Any]) -> Any:
    items = _check_list(args[0], "find")
    function = _check_callable(args[1], "find")
    for item in items:
        if is_truthy(machine.call_value(function, [item])):
            return item
    # nil rather than a fault: not finding something is an ordinary outcome
    return None


def _every(machine: Any, args: list[Any]) -> bool:
    items = _check_list(args[0], "every")
    function = _check_callable(args[1], "every")
    # short-circuits: all stops at the first falsehood, so a later element's
    # callback is never invoked once the answer is settled
    return all(is_truthy(machine.call_value(function, [item])) for item in items)


def _some(machine: Any, args: list[Any]) -> bool:
    items = _check_list(args[0], "some")
    function = _check_callable(args[1], "some")
    return any(is_truthy(machine.call_value(function, [item])) for item in items)


def _count_matching(machine: Any, args: list[Any]) -> int:
    items = _check_list(args[0], "count_where")
    function = _check_callable(args[1], "count_where")
    return sum(1 for item in items if is_truthy(machine.call_value(function, [item])))


def _index_where(machine: Any, args: list[Any]) -> int:
    items = _check_list(args[0], "index_where")
    function = _check_callable(args[1], "index_where")
    for index, item in enumerate(items):
        if is_truthy(machine.call_value(function, [item])):
            return index
    return -1


def _sort_by(machine: Any, args: list[Any]) -> list[Any]:
    items = _check_list(args[0], "sort_by")
    function = _check_callable(args[1], "sort_by")
    keyed = [(machine.call_value(function, [item]), position, item)
             for position, item in enumerate(items)]
    for key, _, _ in keyed:
        if isinstance(key, bool) or not isinstance(key, (int, float)):
            raise TypeMismatch(
                f"sort_by needs its function to return a number, not a {type_name(key)}"
            )
    # the original position breaks ties, so equal keys keep their input order
    keyed.sort(key=lambda entry: (entry[0], entry[1]))
    return [item for _, _, item in keyed]


def _partition(machine: Any, args: list[Any]) -> list[Any]:
    items = _check_list(args[0], "partition")
    function = _check_callable(args[1], "partition")
    matching: list[Any] = []
    rest: list[Any] = []
    for item in items:
        target = matching if is_truthy(machine.call_value(function, [item])) else rest
        target.append(item)
    return [matching, rest]


def _remove_all(args: list[Any]) -> list[Any]:
    items = _check_list(args[0], "remove_all")
    target = args[1]
    return [item for item in items if not values_equal(item, target)]


def _repeat_call(machine: Any, args: list[Any]) -> list[Any]:
    count = args[0]
    function = _check_callable(args[1], "times")
    if isinstance(count, bool) or not isinstance(count, int):
        raise TypeMismatch(f"times needs an integer count, not a {type_name(count)}")
    if count < 0:
        raise IndexRange("times needs a count of zero or more")
    return [machine.call_value(function, [index]) for index in range(count)]


_REGISTRY: dict[str, tuple[int, Any, bool]] = {
    "map": (2, _map, True),
    "filter": (2, _filter, True),
    "reduce": (3, _reduce, True),
    "find": (2, _find, True),
    "every": (2, _every, True),
    "some": (2, _some, True),
    "count_where": (2, _count_matching, True),
    "index_where": (2, _index_where, True),
    "sort_by": (2, _sort_by, True),
    "partition": (2, _partition, True),
    "remove_all": (2, _remove_all, False),
    "times": (2, _repeat_call, True),
}


def install_higher_order(machine: Any) -> None:
    for name, (arity, handler, needs_machine) in _REGISTRY.items():
        machine.define_native(name, arity, handler, needs_machine)


def higher_order_names() -> list[str]:
    return sorted(_REGISTRY)
