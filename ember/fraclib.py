"""Exact fractions: arithmetic that does not accumulate the error floats do.

A third cannot be written as a float. What a float holds is a nearby value, and adding
three of them gives something that is not one, which is the standard demonstration and
also a real problem for any program that divides a quantity into parts and expects them
to add back up. A fraction holds the two integers instead and the arithmetic stays exact:
a third plus a third plus a third is one, precisely, because the denominators are combined
rather than approximated.

A fraction here is a two element list holding a numerator and a denominator, and it is
always kept in lowest terms with a positive denominator. Normalising on construction
rather than on comparison is the decision that makes everything else simple, because two
fractions are then equal exactly when their lists are equal, so the language's own
equality operator works on them and two halves written differently compare the same. The
alternative, of normalising lazily, would leave two representations of one half in
circulation and every comparison would have to know that. What normalising does not buy
is the ability to use a fraction as a map key, which was the first claim written here and
is wrong: this language refuses a list as a key whatever its contents, so a program
keying by fraction has to key by its printed form instead.

The sign convention follows from the same reasoning. A negative fraction carries its sign
in the numerator, so minus one half is minus one over two rather than one over minus two,
and a zero is zero over one rather than any of the other zeros. Without those rules there
would be several lists meaning the same number and equality would stop working.

Two things this deliberately does not do. It does not accept a float, because converting
one exactly gives a fraction with a denominator that is a large power of two, which is
correct and never what the caller meant: someone writing nought point one wants a tenth,
and the float they have is not a tenth. Converting from a decimal string is offered
instead, which is exact and says what it will do. And nothing here limits the size of the
integers, so a long chain of additions with unrelated denominators grows them without
bound; the arithmetic stays exact and the numbers get large, which is the honest trade
against a float's fixed size and drifting accuracy.
"""

from __future__ import annotations

from typing import Any

from ember.errors import Arithmetic, TypeMismatch
from ember.valueops import type_name


def _greatest_divisor(left: int, right: int) -> int:
    left, right = abs(left), abs(right)
    while right:
        left, right = right, left % right
    return left or 1


def normalise(numerator: int, denominator: int) -> list[int]:
    """Lowest terms, positive denominator, so equal fractions are identical lists."""
    if denominator == 0:
        raise Arithmetic(
            "a fraction cannot have a denominator of zero, because nothing is divided "
            "into no parts"
        )
    if denominator < 0:
        # the sign lives in the numerator, so there is one way to write a negative
        numerator, denominator = -numerator, -denominator
    shared = _greatest_divisor(numerator, denominator)
    return [numerator // shared, denominator // shared]


def _whole(value: Any, who: str, what: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        if isinstance(value, float):
            raise TypeMismatch(
                f"{who} needs a whole number for the {what}, and a float is refused "
                "because converting one exactly gives a denominator nobody meant; use "
                "fractionFromText for a decimal"
            )
        raise TypeMismatch(
            f"{who} needs a whole number for the {what}, not a {type_name(value)}"
        )
    return value


def _pair(value: Any, who: str) -> tuple[int, int]:
    if not isinstance(value, list) or len(value) != 2:
        raise TypeMismatch(
            f"{who} needs a fraction as a list of two whole numbers, not a "
            f"{type_name(value)}"
        )
    numerator = _whole(value[0], who, "numerator")
    denominator = _whole(value[1], who, "denominator")
    if denominator == 0:
        raise Arithmetic(f"{who} was given a fraction with a denominator of zero")
    return numerator, denominator


def _fraction(args: list[Any]) -> list[int]:
    numerator = _whole(args[0], "fraction", "numerator")
    denominator = _whole(args[1], "fraction", "denominator")
    return normalise(numerator, denominator)


def _add(args: list[Any]) -> list[int]:
    left = _pair(args[0], "fractionAdd")
    right = _pair(args[1], "fractionAdd")
    return normalise(
        left[0] * right[1] + right[0] * left[1],
        left[1] * right[1],
    )


def _subtract(args: list[Any]) -> list[int]:
    left = _pair(args[0], "fractionSubtract")
    right = _pair(args[1], "fractionSubtract")
    return normalise(
        left[0] * right[1] - right[0] * left[1],
        left[1] * right[1],
    )


def _multiply(args: list[Any]) -> list[int]:
    left = _pair(args[0], "fractionMultiply")
    right = _pair(args[1], "fractionMultiply")
    return normalise(left[0] * right[0], left[1] * right[1])


def _divide(args: list[Any]) -> list[int]:
    left = _pair(args[0], "fractionDivide")
    right = _pair(args[1], "fractionDivide")
    if right[0] == 0:
        raise Arithmetic("a fraction cannot be divided by zero")
    return normalise(left[0] * right[1], left[1] * right[0])


def _negate(args: list[Any]) -> list[int]:
    numerator, denominator = _pair(args[0], "fractionNegate")
    return normalise(-numerator, denominator)


def _reciprocal(args: list[Any]) -> list[int]:
    numerator, denominator = _pair(args[0], "fractionReciprocal")
    if numerator == 0:
        raise Arithmetic("zero has no reciprocal, because nothing divides into one")
    return normalise(denominator, numerator)


def _compare(args: list[Any]) -> int:
    """Minus one, zero or one, found by cross multiplying so nothing is approximated."""
    left = _pair(args[0], "fractionCompare")
    right = _pair(args[1], "fractionCompare")
    # both denominators are positive after normalising, so the cross products compare
    # the same way the fractions do
    first = left[0] * right[1]
    second = right[0] * left[1]
    if first < second:
        return -1
    return 1 if first > second else 0


def _equal(args: list[Any]) -> bool:
    return _compare(args) == 0


def _less(args: list[Any]) -> bool:
    return _compare(args) < 0


def _is_whole(args: list[Any]) -> bool:
    return normalise(*_pair(args[0], "fractionIsWhole"))[1] == 1


def _to_float(args: list[Any]) -> float:
    """The nearest float, which is where exactness ends and is asked for explicitly."""
    numerator, denominator = _pair(args[0], "fractionToFloat")
    return numerator / denominator


def _to_text(args: list[Any]) -> str:
    numerator, denominator = normalise(*_pair(args[0], "fractionToText"))
    if denominator == 1:
        return str(numerator)
    return f"{numerator}/{denominator}"


def _from_text(args: list[Any]) -> list[int]:
    text = args[0]
    if not isinstance(text, str):
        raise TypeMismatch(f"fractionFromText needs a string, not a {type_name(text)}")
    stripped = text.strip()
    if "/" in stripped:
        parts = stripped.split("/")
        if len(parts) != 2:
            raise Arithmetic(f"fractionFromText cannot read {text!r} as a fraction")
        try:
            return normalise(int(parts[0]), int(parts[1]))
        except ValueError as bad:
            raise Arithmetic(f"fractionFromText cannot read {text!r} as a fraction") from bad
    if "." in stripped:
        # a decimal is exact: the digits after the point become the denominator
        whole, _, decimals = stripped.partition(".")
        if not decimals or not decimals.isdigit():
            raise Arithmetic(f"fractionFromText cannot read {text!r} as a decimal")
        negative = whole.startswith("-")
        digits = whole.lstrip("+-") or "0"
        if not digits.isdigit():
            raise Arithmetic(f"fractionFromText cannot read {text!r} as a decimal")
        scale = 10 ** len(decimals)
        total = int(digits) * scale + int(decimals)
        return normalise(-total if negative else total, scale)
    try:
        return normalise(int(stripped), 1)
    except ValueError as bad:
        raise Arithmetic(f"fractionFromText cannot read {text!r} as a number") from bad


def _from_whole(args: list[Any]) -> list[int]:
    return normalise(_whole(args[0], "fractionFromWhole", "number"), 1)


def _simplify(args: list[Any]) -> list[int]:
    return normalise(*_pair(args[0], "fractionSimplify"))


def _mediant(args: list[Any]) -> list[int]:
    """The fraction between two others with the smallest denominator that fits."""
    left = _pair(args[0], "fractionMediant")
    right = _pair(args[1], "fractionMediant")
    return normalise(left[0] + right[0], left[1] + right[1])


def _sum_of(args: list[Any]) -> list[int]:
    values = args[0]
    if not isinstance(values, list):
        raise TypeMismatch(f"fractionSum needs a list, not a {type_name(values)}")
    total = [0, 1]
    for entry in values:
        total = _add([total, entry])
    return total


def _power(args: list[Any]) -> list[int]:
    numerator, denominator = _pair(args[0], "fractionPower")
    exponent = _whole(args[1], "fractionPower", "exponent")
    if exponent < 0:
        if numerator == 0:
            raise Arithmetic("zero cannot be raised to a negative power")
        return normalise(denominator ** -exponent, numerator ** -exponent)
    return normalise(numerator**exponent, denominator**exponent)


_REGISTRY: dict[str, tuple[int, Any]] = {
    "fraction": (2, _fraction),
    "fractionAdd": (2, _add),
    "fractionSubtract": (2, _subtract),
    "fractionMultiply": (2, _multiply),
    "fractionDivide": (2, _divide),
    "fractionNegate": (1, _negate),
    "fractionReciprocal": (1, _reciprocal),
    "fractionCompare": (2, _compare),
    "fractionEqual": (2, _equal),
    "fractionLess": (2, _less),
    "fractionIsWhole": (1, _is_whole),
    "fractionToFloat": (1, _to_float),
    "fractionToText": (1, _to_text),
    "fractionFromText": (1, _from_text),
    "fractionFromWhole": (1, _from_whole),
    "fractionSimplify": (1, _simplify),
    "fractionMediant": (2, _mediant),
    "fractionSum": (1, _sum_of),
    "fractionPower": (2, _power),
}


def install_fraction_library(machine: Any) -> None:
    for name, (arity, handler) in _REGISTRY.items():
        machine.define_native(name, arity, handler)


def fraction_names() -> list[str]:
    return sorted(_REGISTRY)
