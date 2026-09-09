"""Queues and stacks over lists, and the one operation a list makes expensive.

A list already serves as a stack: pushing and popping at the end are both cheap, because
neither moves anything else. What a list does badly is the other end. Removing the first
element means shifting every remaining element down one, so a queue built by pushing at the
end and removing at the front costs the length of the queue per removal, and draining a queue
of a thousand elements does half a million element moves rather than a thousand.

This module offers two answers to that, and the interesting part is that they are answers to
different situations. The first is a two list queue: a front list to take from and a back list
to add to, with the back carried over to the front whenever the front runs out. Each element is
handled exactly twice however long it waits, once when it is carried over and once when it is
taken, so a sequence of operations costs a constant amount each on average even though one
particular removal can cost the length. That is the right structure for a queue whose size is
not known and which is drained as it is filled. The second is a ring: a list of fixed size with
a position and a count, where adding and removing move nothing at all, and adding to a full ring
either refuses or overwrites the oldest depending on which was asked for. That is the right
structure for a buffer of the last so many things, where the size is known and bounded.

The carrying over does not reverse, and that was a bug before it was a decision. The classic
form of this queue reverses the back list, and the first version here did too, which made the
queue return its elements newest first: a queue that behaved as a stack, which the first test
of the ordering caught immediately. The reversal in the classic form is there because that form
prepends to the back list, since prepending is the cheap operation in the languages it comes
from, so the back accumulates newest first and reversing restores arrival order. Here appending
is the cheap operation, so the back is already in arrival order and reversing it destroys the
order rather than restoring it. The same three lines of code are correct or exactly backwards
depending on which end the list grows at, which is worth writing down.

Both are lists rather than new types, as everywhere else here, so they print and serialise. A
two list queue is a list holding the front and the back; a ring is a list holding its
contents, its start position and its count. The shapes are documented rather than hidden
because a program will look at them, and a shape a caller can read is a shape a caller can
break, so every operation checks what it was given rather than assuming.

The cost of never modifying anything is real and is paid here as elsewhere: every operation
returns a new queue, so a loop draining one allocates once per step. Sharing means a mutating
operation would change every binding that shares the structure, which is a much worse
problem than allocation, so the trade is made the same way throughout this library.
"""

from __future__ import annotations

from typing import Any

from ember.errors import Arithmetic, TypeMismatch
from ember.valueops import type_name


def _list_of(value: Any, who: str) -> list[Any]:
    if not isinstance(value, list):
        raise TypeMismatch(f"{who} needs a list, not a {type_name(value)}")
    return value


def _whole(value: Any, who: str, what: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeMismatch(f"{who} needs a whole number {what}, not a {type_name(value)}")
    return value


def _queue_of(value: Any, who: str) -> tuple[list[Any], list[Any]]:
    """A queue is a list of two lists: the front to take from, the back to add to."""
    outer = _list_of(value, who)
    if len(outer) != 2:
        raise Arithmetic(
            f"{who} needs a queue, which is a list of two lists, the front and the "
            f"back, and this list holds {len(outer)} entries"
        )
    return _list_of(outer[0], who), _list_of(outer[1], who)


def _empty_queue(args: list[Any]) -> list[list[Any]]:
    del args
    return [[], []]


def _queue_from(args: list[Any]) -> list[list[Any]]:
    return [list(_list_of(args[0], "queueFrom")), []]


def _enqueue(args: list[Any]) -> list[list[Any]]:
    front, back = _queue_of(args[0], "enqueue")
    return [list(front), [*back, args[1]]]


def _queue_front(args: list[Any]) -> Any:
    front, back = _queue_of(args[0], "queueFront")
    if front:
        return front[0]
    if back:
        # the back grows by appending, so it is already in arrival order and the
        # oldest waiting element is at its near end
        return back[0]
    raise Arithmetic("queueFront has nothing to show, because the queue is empty")


def _dequeue(args: list[Any]) -> list[list[Any]]:
    front, back = _queue_of(args[0], "dequeue")
    if front:
        return [front[1:], list(back)]
    if not back:
        raise Arithmetic("dequeue has nothing to remove, because the queue is empty")
    # the back is carried over once, so each element is handled exactly twice; it is
    # not reversed, because appending already left it in arrival order
    return [list(back[1:]), []]


def _queue_size(args: list[Any]) -> int:
    front, back = _queue_of(args[0], "queueSize")
    return len(front) + len(back)


def _queue_empty(args: list[Any]) -> bool:
    front, back = _queue_of(args[0], "queueEmpty")
    return not front and not back


def _queue_to_list(args: list[Any]) -> list[Any]:
    """Every element in the order they would come out."""
    front, back = _queue_of(args[0], "queueToList")
    return [*front, *back]


def _ring_of(value: Any, who: str) -> tuple[list[Any], int, int]:
    """A ring is a list of three: its contents, its start position and its count."""
    outer = _list_of(value, who)
    if len(outer) != 3:
        raise Arithmetic(
            f"{who} needs a ring, which is a list of its contents, its start and its "
            f"count, and this list holds {len(outer)} entries"
        )
    contents = _list_of(outer[0], who)
    start = _whole(outer[1], who, "start")
    count = _whole(outer[2], who, "count")
    if not contents:
        raise Arithmetic(f"{who} needs a ring with room in it, and this one has none")
    if not 0 <= start < len(contents):
        raise Arithmetic(
            f"{who} was given a start of {start} in a ring of {len(contents)} places"
        )
    if not 0 <= count <= len(contents):
        raise Arithmetic(
            f"{who} was given a count of {count} in a ring of {len(contents)} places"
        )
    return contents, start, count


def _new_ring(args: list[Any]) -> list[Any]:
    size = _whole(args[0], "newRing", "size")
    if size < 1:
        raise Arithmetic(f"a ring needs at least one place, not {size}")
    return [[None] * size, 0, 0]


def _ring_capacity(args: list[Any]) -> int:
    contents, _, _ = _ring_of(args[0], "ringCapacity")
    return len(contents)


def _ring_size(args: list[Any]) -> int:
    _, _, count = _ring_of(args[0], "ringSize")
    return count


def _ring_full(args: list[Any]) -> bool:
    contents, _, count = _ring_of(args[0], "ringFull")
    return count == len(contents)


def _ring_empty(args: list[Any]) -> bool:
    _, _, count = _ring_of(args[0], "ringEmpty")
    return count == 0


def _ring_push(args: list[Any]) -> list[Any]:
    """Add to a ring, refusing when it is full rather than losing anything."""
    contents, start, count = _ring_of(args[0], "ringPush")
    if count == len(contents):
        raise Arithmetic(
            f"this ring holds {len(contents)} and is full; use ringOverwrite to drop "
            "the oldest instead"
        )
    made = list(contents)
    made[(start + count) % len(contents)] = args[1]
    return [made, start, count + 1]


def _ring_overwrite(args: list[Any]) -> list[Any]:
    """Add to a ring, dropping the oldest when it is full, which is asked for by name."""
    contents, start, count = _ring_of(args[0], "ringOverwrite")
    made = list(contents)
    made[(start + count) % len(contents)] = args[1]
    if count == len(contents):
        return [made, (start + 1) % len(contents), count]
    return [made, start, count + 1]


def _ring_oldest(args: list[Any]) -> Any:
    contents, start, count = _ring_of(args[0], "ringOldest")
    if count == 0:
        raise Arithmetic("ringOldest has nothing to show, because the ring is empty")
    return contents[start]


def _ring_newest(args: list[Any]) -> Any:
    contents, start, count = _ring_of(args[0], "ringNewest")
    if count == 0:
        raise Arithmetic("ringNewest has nothing to show, because the ring is empty")
    return contents[(start + count - 1) % len(contents)]


def _ring_pop(args: list[Any]) -> list[Any]:
    contents, start, count = _ring_of(args[0], "ringPop")
    if count == 0:
        raise Arithmetic("ringPop has nothing to remove, because the ring is empty")
    made = list(contents)
    made[start] = None
    return [made, (start + 1) % len(contents), count - 1]


def _ring_to_list(args: list[Any]) -> list[Any]:
    contents, start, count = _ring_of(args[0], "ringToList")
    return [contents[(start + offset) % len(contents)] for offset in range(count)]


def _stack_push(args: list[Any]) -> list[Any]:
    """A list is already a stack, and these name the operations for what they are."""
    return [*_list_of(args[0], "stackPush"), args[1]]


def _stack_pop(args: list[Any]) -> list[Any]:
    values = _list_of(args[0], "stackPop")
    if not values:
        raise Arithmetic("stackPop has nothing to remove, because the stack is empty")
    return values[:-1]


def _stack_top(args: list[Any]) -> Any:
    values = _list_of(args[0], "stackTop")
    if not values:
        raise Arithmetic("stackTop has nothing to show, because the stack is empty")
    return values[-1]


def _stack_empty(args: list[Any]) -> bool:
    return not _list_of(args[0], "stackEmpty")


_REGISTRY: dict[str, tuple[int, Any]] = {
    "newQueue": (1, _empty_queue),
    "queueFrom": (1, _queue_from),
    "enqueue": (2, _enqueue),
    "dequeue": (1, _dequeue),
    "queueFront": (1, _queue_front),
    "queueSize": (1, _queue_size),
    "queueEmpty": (1, _queue_empty),
    "queueToList": (1, _queue_to_list),
    "newRing": (1, _new_ring),
    "ringPush": (2, _ring_push),
    "ringOverwrite": (2, _ring_overwrite),
    "ringPop": (1, _ring_pop),
    "ringOldest": (1, _ring_oldest),
    "ringNewest": (1, _ring_newest),
    "ringSize": (1, _ring_size),
    "ringCapacity": (1, _ring_capacity),
    "ringFull": (1, _ring_full),
    "ringEmpty": (1, _ring_empty),
    "ringToList": (1, _ring_to_list),
    "stackPush": (2, _stack_push),
    "stackPop": (1, _stack_pop),
    "stackTop": (1, _stack_top),
    "stackEmpty": (1, _stack_empty),
}


def install_queue_library(machine: Any) -> None:
    for name, (arity, handler) in _REGISTRY.items():
        machine.define_native(name, arity, handler)


def queue_names() -> list[str]:
    return sorted(_REGISTRY)
