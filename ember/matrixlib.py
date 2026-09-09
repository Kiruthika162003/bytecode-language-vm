"""Matrices as lists of rows: the operations that need care, and where they refuse.

A matrix here is a list of rows, each row a list of numbers, all rows the same length.
Nothing new is introduced to hold one, for the same reason the heap library introduces
nothing: a list of lists prints, serialises, and passes to anything expecting a list,
where a new type would need conversions at every boundary. The cost is that the shape has
to be checked rather than guaranteed, and every function here checks it, because the
alternative is an operation that half succeeds on a ragged input and produces a matrix
whose rows mean different things.

The refusals are where most of the thought went. Multiplication requires the width of the
first to equal the height of the second, and the message says both numbers, because that
is the mistake people actually make and a bare shape error leaves them counting rows.
Inversion and the determinant require a square matrix and say so. A singular matrix has no
inverse, and that is refused rather than approximated: returning something enormous where
an inverse does not exist is how a program ends up with numbers that look like an answer.

The determinant is computed by elimination rather than by expanding minors, and the reason
is worth stating because the naive method is the one people write first. Expanding minors
costs a factorial in the size, so a matrix of ten rows takes millions of operations where
elimination takes hundreds; the same recursion is also where an implementation usually
gets its signs wrong. Elimination with partial pivoting, choosing the largest available
pivot at each step, is both faster and better behaved on floats.

What this cannot do is be exact. Elimination divides, so a matrix of integers generally has
a float determinant and a float inverse, and the usual float caveats then apply: an inverse
multiplied by its matrix gives something very close to the identity rather than the
identity. The comparison functions here therefore take a tolerance rather than testing
equality, and a caller who needs exactness has the fraction library and can do the
arithmetic there.
"""

from __future__ import annotations

from typing import Any

from ember.errors import Arithmetic, TypeMismatch
from ember.valueops import type_name

_TOLERANCE = 1e-9


def _number(value: Any, who: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeMismatch(f"{who} needs numbers, and found a {type_name(value)}")
    return value


def _matrix(value: Any, who: str) -> list[list[float]]:
    """A list of equal length rows of numbers, checked rather than assumed."""
    if not isinstance(value, list):
        raise TypeMismatch(f"{who} needs a matrix as a list of rows, not a {type_name(value)}")
    if not value:
        raise Arithmetic(f"{who} was given a matrix with no rows")
    rows: list[list[float]] = []
    width: int | None = None
    for number, row in enumerate(value, start=1):
        if not isinstance(row, list):
            raise TypeMismatch(
                f"{who} needs each row to be a list, but row {number} is a {type_name(row)}"
            )
        if width is None:
            width = len(row)
        elif len(row) != width:
            raise Arithmetic(
                f"{who} needs every row the same length, but row 1 has {width} and "
                f"row {number} has {len(row)}"
            )
        rows.append([_number(entry, who) for entry in row])
    if width == 0:
        raise Arithmetic(f"{who} was given rows with no entries")
    return rows


def _square(value: Any, who: str) -> list[list[float]]:
    rows = _matrix(value, who)
    if len(rows) != len(rows[0]):
        raise Arithmetic(
            f"{who} needs a square matrix, and this one has {len(rows)} rows and "
            f"{len(rows[0])} columns"
        )
    return rows


def _shape(args: list[Any]) -> list[int]:
    rows = _matrix(args[0], "shape")
    return [len(rows), len(rows[0])]


def _identity(args: list[Any]) -> list[list[float]]:
    size = args[0]
    if isinstance(size, bool) or not isinstance(size, int):
        raise TypeMismatch(f"identity needs a whole number size, not a {type_name(size)}")
    if size < 1:
        raise Arithmetic(f"identity needs a size of at least one, not {size}")
    return [[1 if row == column else 0 for column in range(size)] for row in range(size)]


def _filled(args: list[Any]) -> list[list[float]]:
    height = args[0]
    width = args[1]
    for name, value in (("height", height), ("width", width)):
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeMismatch(f"filled needs a whole number {name}, not a {type_name(value)}")
        if value < 1:
            raise Arithmetic(f"filled needs a {name} of at least one, not {value}")
    entry = _number(args[2], "filled")
    return [[entry for _ in range(width)] for _ in range(height)]


def _transposed(args: list[Any]) -> list[list[float]]:
    rows = _matrix(args[0], "transposed")
    return [[row[column] for row in rows] for column in range(len(rows[0]))]


def _add(args: list[Any]) -> list[list[float]]:
    left = _matrix(args[0], "matrixAdd")
    right = _matrix(args[1], "matrixAdd")
    if (len(left), len(left[0])) != (len(right), len(right[0])):
        raise Arithmetic(
            f"matrixAdd needs two matrices of the same shape, and these are "
            f"{len(left)} by {len(left[0])} and {len(right)} by {len(right[0])}"
        )
    return [
        [first + second for first, second in zip(row, other, strict=True)]
        for row, other in zip(left, right, strict=True)
    ]


def _subtract(args: list[Any]) -> list[list[float]]:
    left = _matrix(args[0], "matrixSubtract")
    right = _matrix(args[1], "matrixSubtract")
    if (len(left), len(left[0])) != (len(right), len(right[0])):
        raise Arithmetic(
            f"matrixSubtract needs two matrices of the same shape, and these are "
            f"{len(left)} by {len(left[0])} and {len(right)} by {len(right[0])}"
        )
    return [
        [first - second for first, second in zip(row, other, strict=True)]
        for row, other in zip(left, right, strict=True)
    ]


def _scaled(args: list[Any]) -> list[list[float]]:
    rows = _matrix(args[0], "scaled")
    factor = _number(args[1], "scaled")
    return [[entry * factor for entry in row] for row in rows]


def _multiply(args: list[Any]) -> list[list[float]]:
    left = _matrix(args[0], "matrixMultiply")
    right = _matrix(args[1], "matrixMultiply")
    if len(left[0]) != len(right):
        raise Arithmetic(
            f"matrixMultiply needs the width of the first to equal the height of the "
            f"second, and the first is {len(left)} by {len(left[0])} while the second "
            f"is {len(right)} by {len(right[0])}"
        )
    width = len(right[0])
    inner = len(right)
    return [
        [sum(row[at] * right[at][column] for at in range(inner)) for column in range(width)]
        for row in left
    ]


def _power(args: list[Any]) -> list[list[float]]:
    rows = _square(args[0], "matrixPower")
    times = args[1]
    if isinstance(times, bool) or not isinstance(times, int):
        raise TypeMismatch(f"matrixPower needs a whole number, not a {type_name(times)}")
    if times < 0:
        raise Arithmetic(f"matrixPower needs a power of zero or more, not {times}")
    result = _identity([len(rows)])
    for _ in range(times):
        result = _multiply([result, rows])
    return result


def _eliminate(rows: list[list[float]]) -> tuple[list[list[float]], float, int]:
    """Row reduce a copy, returning it with the determinant and the rank.

    Partial pivoting, taking the largest available pivot, is what keeps this from
    dividing by something tiny and losing precision on a matrix that is merely
    awkward rather than singular.
    """
    working = [list(row) for row in rows]
    size = len(working)
    width = len(working[0])
    determinant = 1.0
    rank = 0
    for column in range(min(size, width)):
        best = max(range(rank, size), key=lambda at: abs(working[at][column]))
        if abs(working[best][column]) < _TOLERANCE:
            determinant = 0.0
            continue
        if best != rank:
            working[rank], working[best] = working[best], working[rank]
            # a row swap flips the sign of the determinant
            determinant = -determinant
        pivot = working[rank][column]
        determinant *= pivot
        for at in range(size):
            if at == rank:
                continue
            factor = working[at][column] / pivot
            working[at] = [
                entry - factor * above
                for entry, above in zip(working[at], working[rank], strict=True)
            ]
        working[rank] = [entry / pivot for entry in working[rank]]
        rank += 1
    return working, determinant, rank


def _determinant(args: list[Any]) -> float:
    rows = _square(args[0], "determinant")
    return _eliminate(rows)[1]


def _rank(args: list[Any]) -> int:
    return _eliminate(_matrix(args[0], "matrixRank"))[2]


def _is_singular(args: list[Any]) -> bool:
    rows = _square(args[0], "isSingular")
    return abs(_eliminate(rows)[1]) < _TOLERANCE


def _inverse(args: list[Any]) -> list[list[float]]:
    rows = _square(args[0], "inverse")
    size = len(rows)
    if abs(_eliminate(rows)[1]) < _TOLERANCE:
        raise Arithmetic(
            "this matrix has no inverse, because its determinant is zero; returning "
            "something enormous instead would look like an answer and not be one"
        )
    beside = _identity([size])
    widened = [row + other for row, other in zip(rows, beside, strict=True)]
    reduced, _, _ = _eliminate(widened)
    return [row[size:] for row in reduced]


def _trace_of(args: list[Any]) -> float:
    rows = _square(args[0], "matrixTrace")
    return sum(rows[at][at] for at in range(len(rows)))


def _row_of(args: list[Any]) -> list[float]:
    rows = _matrix(args[0], "matrixRow")
    at = args[1]
    if isinstance(at, bool) or not isinstance(at, int):
        raise TypeMismatch(f"matrixRow needs a whole number index, not a {type_name(at)}")
    if not 0 <= at < len(rows):
        raise Arithmetic(f"matrixRow was asked for row {at} of a matrix with {len(rows)}")
    return list(rows[at])


def _column_of(args: list[Any]) -> list[float]:
    rows = _matrix(args[0], "matrixColumn")
    at = args[1]
    if isinstance(at, bool) or not isinstance(at, int):
        raise TypeMismatch(f"matrixColumn needs a whole number index, not a {type_name(at)}")
    if not 0 <= at < len(rows[0]):
        raise Arithmetic(
            f"matrixColumn was asked for column {at} of a matrix with {len(rows[0])}"
        )
    return [row[at] for row in rows]


def _close_enough(args: list[Any]) -> bool:
    """Whether two matrices agree within tolerance, since elimination divides."""
    left = _matrix(args[0], "matrixClose")
    right = _matrix(args[1], "matrixClose")
    if (len(left), len(left[0])) != (len(right), len(right[0])):
        return False
    return all(
        abs(first - second) < _TOLERANCE
        for row, other in zip(left, right, strict=True)
        for first, second in zip(row, other, strict=True)
    )


def _is_symmetric(args: list[Any]) -> bool:
    rows = _square(args[0], "isSymmetric")
    return _close_enough([rows, _transposed([rows])])


_REGISTRY: dict[str, tuple[int, Any]] = {
    "shape": (1, _shape),
    "identity": (1, _identity),
    "filled": (3, _filled),
    "transposed": (1, _transposed),
    "matrixAdd": (2, _add),
    "matrixSubtract": (2, _subtract),
    "scaled": (2, _scaled),
    "matrixMultiply": (2, _multiply),
    "matrixPower": (2, _power),
    "determinant": (1, _determinant),
    "matrixRank": (1, _rank),
    "isSingular": (1, _is_singular),
    "inverse": (1, _inverse),
    "matrixTrace": (1, _trace_of),
    "matrixRow": (2, _row_of),
    "matrixColumn": (2, _column_of),
    "matrixClose": (2, _close_enough),
    "isSymmetric": (1, _is_symmetric),
}


def install_matrix_library(machine: Any) -> None:
    for name, (arity, handler) in _REGISTRY.items():
        machine.define_native(name, arity, handler)


def matrix_names() -> list[str]:
    return sorted(_REGISTRY)
