"""Intervals: arithmetic on ranges, which is how a measurement's uncertainty travels.

A measured quantity is not a number, it is a range, and arithmetic on ranges is not the
arithmetic on numbers with the uncertainty carried along afterwards. It is its own arithmetic,
and the difference matters: adding two quantities each known to within one gives a result
known to within two, and multiplying two ranges that both straddle zero gives a range whose
ends come from two different pairs of the four products. Doing this by hand is where programs
that track uncertainty go wrong.

An interval here is a list of two numbers, the low end and the high end, with the low end no
greater than the high. A single number is the interval from it to itself, which makes an exact
quantity a special case of an uncertain one rather than a separate thing, and means the same
functions handle both.

The multiplication rule is the one worth stating. The product of two intervals is bounded by
the smallest and largest of the four products of their ends, and taking only the product of the
lows and the product of the highs is wrong whenever a negative is involved: minus two to one
times minus two to one runs from minus two to four, and the four comes from multiplying the two
low ends together. Division follows the same rule and refuses a divisor that contains zero,
because the result would be unbounded and there is no interval for that; a caller who needs to
divide by a range straddling zero has to split it.

Two decisions about comparison. One interval is definitely less than another only when its high
end is below the other's low end, so two overlapping intervals are neither less nor greater nor
equal, and a function asking which is smaller has to answer that it does not know. That is the
honest answer and it means intervals cannot be sorted, which is a real limitation and better
than an order that claims more than the data supports. And two intervals are equal when their
ends match, which is equality of the ranges rather than of the quantities they describe: two
measurements of the same thing with the same uncertainty are equal here even though the
quantities may differ.

Nothing here widens an interval to account for floating point error in the arithmetic itself.
A rigorous interval library rounds each end outwards so the true result is guaranteed to lie
inside, and this one does not, so a long chain of operations can produce a range very slightly
narrower than the truth. That is the honest limit of what this offers.
"""

from __future__ import annotations

from typing import Any

from ember.errors import Arithmetic, TypeMismatch
from ember.valueops import type_name


def _number(value: Any, who: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeMismatch(f"{who} needs numbers, and found a {type_name(value)}")
    return value


def _interval(value: Any, who: str) -> tuple[float, float]:
    """A list of two numbers, or a bare number meaning the interval from it to itself."""
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value, value
    if not isinstance(value, list) or len(value) != 2:
        raise TypeMismatch(
            f"{who} needs an interval as a list of two numbers, or a single number, "
            f"not a {type_name(value)}"
        )
    low = _number(value[0], who)
    high = _number(value[1], who)
    if low > high:
        raise Arithmetic(
            f"an interval runs from its low end to its high end, so {low} to {high} "
            "is not one; swap them"
        )
    return low, high


def _made(args: list[Any]) -> list[float]:
    low = _number(args[0], "interval")
    high = _number(args[1], "interval")
    if low > high:
        raise Arithmetic(f"an interval runs upwards, so {low} to {high} is not one")
    return [low, high]


def _exactly(args: list[Any]) -> list[float]:
    value = _number(args[0], "exactly")
    return [value, value]


def _within(args: list[Any]) -> list[float]:
    """A quantity known to within a tolerance, which is how a measurement arrives."""
    middle = _number(args[0], "within")
    slack = _number(args[1], "within")
    if slack < 0:
        raise Arithmetic(f"a tolerance cannot be negative, and {slack} is")
    return [middle - slack, middle + slack]


def _add(args: list[Any]) -> list[float]:
    left = _interval(args[0], "intervalAdd")
    right = _interval(args[1], "intervalAdd")
    return [left[0] + right[0], left[1] + right[1]]


def _subtract(args: list[Any]) -> list[float]:
    left = _interval(args[0], "intervalSubtract")
    right = _interval(args[1], "intervalSubtract")
    # the widest difference pairs the low end of one with the high end of the other
    return [left[0] - right[1], left[1] - right[0]]


def _multiply(args: list[Any]) -> list[float]:
    left = _interval(args[0], "intervalMultiply")
    right = _interval(args[1], "intervalMultiply")
    # all four products, because with a negative involved the extremes can come from
    # any pair of ends and taking low times low and high times high is simply wrong
    products = (
        left[0] * right[0],
        left[0] * right[1],
        left[1] * right[0],
        left[1] * right[1],
    )
    return [min(products), max(products)]


def _divide(args: list[Any]) -> list[float]:
    left = _interval(args[0], "intervalDivide")
    right = _interval(args[1], "intervalDivide")
    if right[0] <= 0 <= right[1]:
        raise Arithmetic(
            f"dividing by the interval {right[0]} to {right[1]} has no bounded answer, "
            "because that range contains zero; split it and divide by each part"
        )
    quotients = (
        left[0] / right[0],
        left[0] / right[1],
        left[1] / right[0],
        left[1] / right[1],
    )
    return [min(quotients), max(quotients)]


def _negate(args: list[Any]) -> list[float]:
    low, high = _interval(args[0], "intervalNegate")
    return [-high, -low]


def _width(args: list[Any]) -> float:
    low, high = _interval(args[0], "intervalWidth")
    return high - low


def _middle(args: list[Any]) -> float:
    low, high = _interval(args[0], "intervalMiddle")
    return (low + high) / 2


def _is_exact(args: list[Any]) -> bool:
    low, high = _interval(args[0], "intervalExact")
    return low == high


def _contains(args: list[Any]) -> bool:
    low, high = _interval(args[0], "intervalContains")
    value = _number(args[1], "intervalContains")
    return low <= value <= high


def _overlaps(args: list[Any]) -> bool:
    left = _interval(args[0], "intervalOverlaps")
    right = _interval(args[1], "intervalOverlaps")
    return left[0] <= right[1] and right[0] <= left[1]


def _encloses(args: list[Any]) -> bool:
    outer = _interval(args[0], "intervalEncloses")
    inner = _interval(args[1], "intervalEncloses")
    return outer[0] <= inner[0] and inner[1] <= outer[1]


def _intersection(args: list[Any]) -> list[float] | None:
    """What both intervals cover, or nil when they cover nothing in common."""
    left = _interval(args[0], "intervalIntersection")
    right = _interval(args[1], "intervalIntersection")
    low = max(left[0], right[0])
    high = min(left[1], right[1])
    if low > high:
        # nothing in common, which is nil rather than an interval running backwards
        return None
    return [low, high]


def _union(args: list[Any]) -> list[float]:
    """The smallest interval covering both, which may include what neither covers."""
    left = _interval(args[0], "intervalUnion")
    right = _interval(args[1], "intervalUnion")
    return [min(left[0], right[0]), max(left[1], right[1])]


def _definitely_less(args: list[Any]) -> bool:
    """True only when every value of the first is below every value of the second."""
    left = _interval(args[0], "definitelyLess")
    right = _interval(args[1], "definitelyLess")
    return left[1] < right[0]


def _definitely_greater(args: list[Any]) -> bool:
    left = _interval(args[0], "definitelyGreater")
    right = _interval(args[1], "definitelyGreater")
    return left[0] > right[1]


def _comparison_known(args: list[Any]) -> bool:
    """Whether the two can be ordered at all, which overlapping intervals cannot."""
    return _definitely_less(args) or _definitely_greater(args)


def _same_interval(args: list[Any]) -> bool:
    left = _interval(args[0], "sameInterval")
    right = _interval(args[1], "sameInterval")
    return left == right


def _interval_text(args: list[Any]) -> str:
    low, high = _interval(args[0], "intervalToText")
    if low == high:
        return f"exactly {low}"
    return f"{low} to {high}"


def _power(args: list[Any]) -> list[float]:
    low, high = _interval(args[0], "intervalPower")
    times = args[1]
    if isinstance(times, bool) or not isinstance(times, int):
        raise TypeMismatch(f"intervalPower needs a whole number, not a {type_name(times)}")
    if times < 0:
        raise Arithmetic(f"intervalPower needs a power of zero or more, not {times}")
    if times == 0:
        return [1, 1]
    result = [low, high]
    for _ in range(times - 1):
        result = _multiply([result, [low, high]])
    return result


_REGISTRY: dict[str, tuple[int, Any]] = {
    "interval": (2, _made),
    "exactly": (1, _exactly),
    "within": (2, _within),
    "intervalAdd": (2, _add),
    "intervalSubtract": (2, _subtract),
    "intervalMultiply": (2, _multiply),
    "intervalDivide": (2, _divide),
    "intervalNegate": (1, _negate),
    "intervalPower": (2, _power),
    "intervalWidth": (1, _width),
    "intervalMiddle": (1, _middle),
    "intervalExact": (1, _is_exact),
    "intervalContains": (2, _contains),
    "intervalOverlaps": (2, _overlaps),
    "intervalEncloses": (2, _encloses),
    "intervalIntersection": (2, _intersection),
    "intervalUnion": (2, _union),
    "definitelyLess": (2, _definitely_less),
    "definitelyGreater": (2, _definitely_greater),
    "comparisonKnown": (2, _comparison_known),
    "sameInterval": (2, _same_interval),
    "intervalToText": (1, _interval_text),
}


def install_interval_library(machine: Any) -> None:
    for name, (arity, handler) in _REGISTRY.items():
        machine.define_native(name, arity, handler)


def interval_names() -> list[str]:
    return sorted(_REGISTRY)
