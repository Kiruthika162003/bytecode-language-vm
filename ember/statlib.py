"""The statistics library: summarising a list of numbers without lying about it.

Summary statistics are where a language quietly makes decisions on the programmer's
behalf, and the ones this module makes are worth stating because reasonable people
choose differently. The mean of an empty list is refused rather than returned as
zero, because zero is a real answer to a different question and a program averaging
an empty list has a bug the library should surface rather than absorb. The median of
an even-length list is the mean of the two middle values, which is the common
convention and does mean the median of a list of integers can be a float. The mode
returns the smallest of the values that tie for most frequent rather than refusing or
returning a list, because a single value is what callers reach for and picking the
smallest at least makes the choice deterministic; a caller who needs to know a tie
happened can count the values themselves.

Variance is the decision that matters most. This module computes the sample variance,
dividing by one less than the count, because the overwhelmingly common case is a list
of observations standing in for a larger population, and dividing by the count would
understate the spread. The consequence is that variance of a single value is refused
rather than zero, since there is no spread to estimate from one observation, and that
refusal has caught more mistakes than it has caused. The population form is available
separately for callers who really do have the whole population. Summation uses a
compensated running total, so adding many small floats does not drift the way naive
addition does, which is the one place here where the obvious implementation is
measurably worse rather than merely less careful.
"""

from __future__ import annotations

from typing import Any

from ember.errors import Arithmetic, TypeMismatch
from ember.valueops import type_name


def _numbers(value: Any, who: str) -> list[float]:
    if not isinstance(value, list):
        raise TypeMismatch(f"{who} needs a list, not a {type_name(value)}")
    found: list[float] = []
    for entry in value:
        if isinstance(entry, bool) or not isinstance(entry, (int, float)):
            raise TypeMismatch(f"{who} needs a list of numbers, but found a {type_name(entry)}")
        found.append(entry)
    return found


def _demand_some(values: list[float], who: str) -> list[float]:
    if not values:
        raise Arithmetic(f"{who} has no answer for an empty list; check the list is not empty")
    return values


def compensated_sum(values: list[float]) -> float:
    """A running total that keeps the error term, so many small floats do not drift.

    This is Neumaier's variant rather than the more familiar Kahan one, and the
    difference is not academic. Kahan compensation assumes the running total is the
    larger of the two operands and only recovers the part of the addend that fell off
    the end, so a large value followed by a small one and then the large value negated
    loses the small one completely: summing a huge number, one, and the negated huge
    number gives zero rather than one. Neumaier's version tests which operand is
    larger and takes the lost part from whichever it was, which costs one comparison
    per value and gets that case right.
    """
    total = 0.0
    compensation = 0.0
    for value in values:
        raised = total + value
        if abs(total) >= abs(value):
            # the total is the larger, so what fell off came from the value
            compensation += (total - raised) + value
        else:
            compensation += (value - raised) + total
        total = raised
    return total + compensation


def _mean_of(values: list[float]) -> float:
    return compensated_sum(values) / len(values)


def _mean(args: list[Any]) -> float:
    return _mean_of(_demand_some(_numbers(args[0], "mean"), "mean"))


def _median(args: list[Any]) -> float:
    values = sorted(_demand_some(_numbers(args[0], "median"), "median"))
    middle = len(values) // 2
    if len(values) % 2 == 1:
        return values[middle]
    # the convention: the mean of the two middle values, which may be a float
    return (values[middle - 1] + values[middle]) / 2


def _mode(args: list[Any]) -> float:
    values = _demand_some(_numbers(args[0], "mode"), "mode")
    counts: dict[float, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    most = max(counts.values())
    # the smallest of the values that tie, so the answer does not depend on order
    return min(value for value, count in counts.items() if count == most)


def _variance(args: list[Any]) -> float:
    values = _numbers(args[0], "variance")
    if len(values) < 2:
        raise Arithmetic(
            "variance needs at least two values, because there is no spread to "
            "estimate from one observation; use pvariance for a whole population"
        )
    centre = _mean_of(values)
    return compensated_sum([(value - centre) ** 2 for value in values]) / (len(values) - 1)


def _pvariance(args: list[Any]) -> float:
    values = _demand_some(_numbers(args[0], "pvariance"), "pvariance")
    centre = _mean_of(values)
    return compensated_sum([(value - centre) ** 2 for value in values]) / len(values)


def _stdev(args: list[Any]) -> float:
    return _variance(args) ** 0.5


def _pstdev(args: list[Any]) -> float:
    return _pvariance(args) ** 0.5


def _spread(args: list[Any]) -> float:
    values = _demand_some(_numbers(args[0], "spread"), "spread")
    return max(values) - min(values)


def _percentile(args: list[Any]) -> float:
    values = sorted(_demand_some(_numbers(args[0], "percentile"), "percentile"))
    fraction = args[1]
    if isinstance(fraction, bool) or not isinstance(fraction, (int, float)):
        raise TypeMismatch(
            f"percentile needs a number for the fraction, not a {type_name(fraction)}"
        )
    if not 0 <= fraction <= 100:
        raise Arithmetic(f"percentile needs a fraction from 0 to 100, not {fraction}")
    if len(values) == 1:
        return values[0]
    position = (len(values) - 1) * (fraction / 100)
    below = int(position)
    above = min(below + 1, len(values) - 1)
    weight = position - below
    # linear interpolation between the two straddling values
    return values[below] * (1 - weight) + values[above] * weight


def _quartiles(args: list[Any]) -> list[float]:
    values = _numbers(args[0], "quartiles")
    return [
        _percentile([values, 25]),
        _percentile([values, 50]),
        _percentile([values, 75]),
    ]


def _normalised(args: list[Any]) -> list[float]:
    values = _demand_some(_numbers(args[0], "normalised"), "normalised")
    low = min(values)
    high = max(values)
    if low == high:
        # every value the same means no scale to normalise against, so they are all
        # equally placed rather than the division being attempted
        return [0.0 for _ in values]
    return [(value - low) / (high - low) for value in values]


def _cumulative(args: list[Any]) -> list[float]:
    values = _numbers(args[0], "cumulative")
    running: list[float] = []
    total: float = 0
    for value in values:
        total = total + value
        running.append(total)
    return running


def _covariance(args: list[Any]) -> float:
    left = _numbers(args[0], "covariance")
    right = _numbers(args[1], "covariance")
    if len(left) != len(right):
        raise Arithmetic(
            f"covariance needs two lists of the same length, but they hold "
            f"{len(left)} and {len(right)} values"
        )
    if len(left) < 2:
        raise Arithmetic("covariance needs at least two pairs of values")
    left_centre = _mean_of(left)
    right_centre = _mean_of(right)
    products = [
        (first - left_centre) * (second - right_centre)
        for first, second in zip(left, right, strict=True)
    ]
    return compensated_sum(products) / (len(left) - 1)


def _correlation(args: list[Any]) -> float:
    left = _numbers(args[0], "correlation")
    right = _numbers(args[1], "correlation")
    left_spread = _stdev([left])
    right_spread = _stdev([right])
    if left_spread == 0 or right_spread == 0:
        raise Arithmetic(
            "correlation has no answer when one list never varies, because a "
            "constant has no direction to correlate with"
        )
    return _covariance([left, right]) / (left_spread * right_spread)


_REGISTRY: dict[str, tuple[int, Any]] = {
    "mean": (1, _mean),
    "median": (1, _median),
    "mode": (1, _mode),
    "variance": (1, _variance),
    "pvariance": (1, _pvariance),
    "stdev": (1, _stdev),
    "pstdev": (1, _pstdev),
    "spread": (1, _spread),
    "percentile": (2, _percentile),
    "quartiles": (1, _quartiles),
    "normalised": (1, _normalised),
    "cumulative": (1, _cumulative),
    "covariance": (2, _covariance),
    "correlation": (2, _correlation),
}


def install_stat_library(machine: Any) -> None:
    for name, (arity, handler) in _REGISTRY.items():
        machine.define_native(name, arity, handler)


def stat_names() -> list[str]:
    return sorted(_REGISTRY)
