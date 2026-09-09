"""Differences between two sequences: the longest common subsequence, and what it costs.

Comparing two versions of something means finding what they share, and the useful notion of
sharing is the longest common subsequence: the longest run of elements appearing in both in
the same order, though not necessarily adjacently. Everything not in it is an insertion or a
deletion, so the subsequence determines the difference completely, and finding it is the
whole problem.

The algorithm is the dynamic programming one, filling a table of the best match for every
pair of prefixes and then walking back through it to recover the choices. Its cost is the
product of the two lengths in both time and space, which is the honest limitation of this
module: two files of a thousand lines each need a table of a million entries, which is fine,
and two of a hundred thousand need ten billion, which is not. There are algorithms whose
cost depends on the size of the difference rather than the size of the inputs, and they are
substantially harder to be sure of; the table is obviously correct and its limit is stated
rather than discovered. A size limit refuses the cases it cannot handle instead of consuming
all available memory.

Checking this against the host's own sequence matcher was the first instinct and was
wrong, which is worth recording because the mistake is easy to repeat. That matcher does
not compute a longest common subsequence: it finds the longest contiguous matching block
and recurses on either side of it, which is a different and generally smaller answer. On
two seven element sequences it reported three shared elements where the true subsequence
has four, and taking it as an oracle would have meant changing correct code to match it.
An exhaustive search over every subsequence is the right oracle, it is only usable on
small inputs, and the tests use it on three hundred random small pairs.

Two decisions about the output. A difference is returned as a list of operations, each
saying keep, insert, or delete along with the element, because that is what both a person
reading a diff and a program applying one need; returning only the subsequence would make
every caller recompute the operations. And deletions come before insertions where both occur
at the same position, which is the conventional order and matters only for how the result
reads. The similarity ratio uses twice the shared length over the total length of both, so
identical sequences score one and disjoint ones score zero, which is the usual definition
and is worth naming because a ratio of shared over the longer input is also common and gives
different numbers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ember.errors import Arithmetic, TypeMismatch
from ember.valueops import type_name

KEEP = "keep"
INSERT = "insert"
DELETE = "delete"

_SIZE_LIMIT = 4_000_000


@dataclass(frozen=True)
class Operation:
    """One step of a difference: keep, insert, or delete this element."""

    kind: str
    value: Any

    def render(self) -> str:
        marker = {KEEP: " ", INSERT: "+", DELETE: "-"}[self.kind]
        return f"{marker} {self.value}"


@dataclass
class Difference:
    """The whole difference between two sequences, and what it amounts to."""

    operations: list[Operation] = field(default_factory=list)

    @property
    def kept(self) -> int:
        return sum(1 for one in self.operations if one.kind == KEEP)

    @property
    def inserted(self) -> int:
        return sum(1 for one in self.operations if one.kind == INSERT)

    @property
    def deleted(self) -> int:
        return sum(1 for one in self.operations if one.kind == DELETE)

    @property
    def identical(self) -> bool:
        return not self.inserted and not self.deleted

    def shared(self) -> list[Any]:
        return [one.value for one in self.operations if one.kind == KEEP]

    def ratio(self, left_length: int, right_length: int) -> float:
        """Twice the shared length over the total, so identical scores one."""
        total = left_length + right_length
        if total == 0:
            # two empty sequences are identical, which is a ratio of one
            return 1.0
        return 2 * self.kept / total

    def summary(self) -> str:
        return (
            f"{self.kept} kept, {self.inserted} inserted, {self.deleted} deleted"
        )

    def render(self) -> list[str]:
        return [one.render() for one in self.operations]

    def changed_only(self) -> list[Operation]:
        return [one for one in self.operations if one.kind != KEEP]


def _table(left: list[Any], right: list[Any]) -> list[list[int]]:
    """The length of the best match for every pair of prefixes."""
    height = len(left)
    width = len(right)
    grid = [[0] * (width + 1) for _ in range(height + 1)]
    for row in range(height - 1, -1, -1):
        for column in range(width - 1, -1, -1):
            if left[row] == right[column]:
                grid[row][column] = grid[row + 1][column + 1] + 1
            else:
                grid[row][column] = max(grid[row + 1][column], grid[row][column + 1])
    return grid


def _check_size(left: list[Any], right: list[Any]) -> None:
    if len(left) * len(right) > _SIZE_LIMIT:
        raise Arithmetic(
            f"comparing {len(left)} against {len(right)} elements needs a table of "
            f"{len(left) * len(right)} entries, past the limit of {_SIZE_LIMIT}; this "
            "algorithm costs the product of the two lengths and refuses rather than "
            "consuming everything available"
        )


def longest_common(left: list[Any], right: list[Any]) -> list[Any]:
    """The longest run of elements appearing in both, in order."""
    _check_size(left, right)
    grid = _table(left, right)
    shared: list[Any] = []
    row = column = 0
    while row < len(left) and column < len(right):
        if left[row] == right[column]:
            shared.append(left[row])
            row += 1
            column += 1
        elif grid[row + 1][column] >= grid[row][column + 1]:
            row += 1
        else:
            column += 1
    return shared


def difference(left: list[Any], right: list[Any]) -> Difference:
    """Every operation turning the first sequence into the second."""
    _check_size(left, right)
    grid = _table(left, right)
    found = Difference()
    row = column = 0
    while row < len(left) and column < len(right):
        if left[row] == right[column]:
            found.operations.append(Operation(KEEP, left[row]))
            row += 1
            column += 1
        elif grid[row + 1][column] >= grid[row][column + 1]:
            # a deletion is taken before an insertion at the same position, which is
            # the conventional order and affects only how the result reads
            found.operations.append(Operation(DELETE, left[row]))
            row += 1
        else:
            found.operations.append(Operation(INSERT, right[column]))
            column += 1
    while row < len(left):
        found.operations.append(Operation(DELETE, left[row]))
        row += 1
    while column < len(right):
        found.operations.append(Operation(INSERT, right[column]))
        column += 1
    return found


def similarity(left: list[Any], right: list[Any]) -> float:
    return difference(left, right).ratio(len(left), len(right))


def applied(left: list[Any], found: Difference) -> list[Any]:
    """Rebuild the second sequence from the first and a difference, as a check."""
    result: list[Any] = []
    at = 0
    for one in found.operations:
        if one.kind == KEEP:
            if at >= len(left) or left[at] != one.value:
                raise Arithmetic(
                    "this difference does not describe this sequence, so applying it "
                    "would produce something neither side asked for"
                )
            result.append(left[at])
            at += 1
        elif one.kind == DELETE:
            if at >= len(left) or left[at] != one.value:
                raise Arithmetic("this difference deletes something that is not there")
            at += 1
        else:
            result.append(one.value)
    if at != len(left):
        raise Arithmetic(
            f"this difference accounts for {at} of the {len(left)} elements it was given"
        )
    return result


def edit_distance(left: list[Any], right: list[Any]) -> int:
    """How many insertions and deletions separate the two."""
    found = difference(left, right)
    return found.inserted + found.deleted


def _list_of(value: Any, who: str) -> list[Any]:
    if not isinstance(value, list):
        raise TypeMismatch(f"{who} needs a list, not a {type_name(value)}")
    return value


def _shared(args: list[Any]) -> list[Any]:
    return longest_common(_list_of(args[0], "shared"), _list_of(args[1], "shared"))


def _diff(args: list[Any]) -> list[list[Any]]:
    """Each operation as a two element list, the kind and the value."""
    found = difference(_list_of(args[0], "diff"), _list_of(args[1], "diff"))
    return [[one.kind, one.value] for one in found.operations]


def _diff_lines(args: list[Any]) -> list[str]:
    found = difference(_list_of(args[0], "diffLines"), _list_of(args[1], "diffLines"))
    return found.render()


def _similarity(args: list[Any]) -> float:
    return similarity(_list_of(args[0], "similarity"), _list_of(args[1], "similarity"))


def _distance(args: list[Any]) -> int:
    return edit_distance(_list_of(args[0], "editDistance"), _list_of(args[1], "editDistance"))


def _unchanged(args: list[Any]) -> bool:
    left = _list_of(args[0], "unchanged")
    right = _list_of(args[1], "unchanged")
    return difference(left, right).identical


def _applied(args: list[Any]) -> list[Any]:
    left = _list_of(args[0], "applyDiff")
    steps = _list_of(args[1], "applyDiff")
    found = Difference()
    for step in steps:
        if not isinstance(step, list) or len(step) != 2:
            raise Arithmetic(
                "each step of a difference is a list of two values, the kind and the "
                f"value, and {step!r} is not"
            )
        if step[0] not in (KEEP, INSERT, DELETE):
            raise Arithmetic(f"{step[0]!r} is not one of keep, insert or delete")
        found.operations.append(Operation(step[0], step[1]))
    return applied(left, found)


_REGISTRY: dict[str, tuple[int, Any]] = {
    "shared": (2, _shared),
    "diff": (2, _diff),
    "diffLines": (2, _diff_lines),
    "similarity": (2, _similarity),
    "editDistance": (2, _distance),
    "unchanged": (2, _unchanged),
    "applyDiff": (2, _applied),
}


def install_diff_library(machine: Any) -> None:
    for name, (arity, handler) in _REGISTRY.items():
        machine.define_native(name, arity, handler)


def diff_names() -> list[str]:
    return sorted(_REGISTRY)
