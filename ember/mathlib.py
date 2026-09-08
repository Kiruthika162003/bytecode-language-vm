"""The math library: numeric functions beyond the arithmetic the operators provide.

The operators cover the four arithmetic operations and remainder, but a
program that does real numeric work needs more: raising to a power,
logarithms, the transcendental functions, rounding in its several senses,
and a few integer routines like greatest common divisor and factorial.
This module supplies them as native functions over the language's number
types. The design choices are mostly about types and domains. Functions
that are inherently real, sqrt and log and the trigonometric ones, return
a float even when handed an integer, because their results generally are
not whole and pretending otherwise would mislead. Functions that round,
round and trunc, return an integer, since that is what rounding is for.
The integer-only routines, gcd and factorial, refuse a float rather than
silently truncating it, because a caller who passed 4.5 to factorial made
a mistake worth reporting. Domain errors are raised in the language's own
voice: a logarithm of a non-positive number and a factorial of a negative
one have no defined result here and say so, rather than returning a host
infinity or raising a host exception. The honest limitation is precision:
these delegate to the host's double-precision floating point, so the
usual caveats apply, a sum of decimals may not be exact and a very large
factorial is an exact big integer while a very large power may overflow
to a float infinity, and the library does not paper over that reality.
"""

from __future__ import annotations

import math
from typing import Any

from ember.errors import Arithmetic, TypeMismatch
from ember.valueops import type_name


def _number(value: Any, who: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeMismatch(f"{who} needs a number, not a {type_name(value)}")
    return value


def _integer(value: Any, who: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeMismatch(f"{who} needs an integer, not a {type_name(value)}")
    return value


def _power(args: list[Any]) -> Any:
    base = _number(args[0], "pow")
    exponent = _number(args[1], "pow")
    result = base ** exponent
    if isinstance(result, complex):
        raise Arithmetic("pow produced a complex result, which this language has no type for")
    return result


def _log(args: list[Any]) -> float:
    value = _number(args[0], "log")
    if value <= 0:
        raise Arithmetic("log needs a positive number")
    return math.log(value)


def _exp(args: list[Any]) -> float:
    return math.exp(_number(args[0], "exp"))


def _sin(args: list[Any]) -> float:
    return math.sin(_number(args[0], "sin"))


def _cos(args: list[Any]) -> float:
    return math.cos(_number(args[0], "cos"))


def _tan(args: list[Any]) -> float:
    return math.tan(_number(args[0], "tan"))


def _round(args: list[Any]) -> int:
    value = _number(args[0], "round")
    return math.floor(value + 0.5) if value >= 0 else math.ceil(value - 0.5)


def _trunc(args: list[Any]) -> int:
    return math.trunc(_number(args[0], "trunc"))


def _sign(args: list[Any]) -> int:
    value = _number(args[0], "sign")
    if value > 0:
        return 1
    if value < 0:
        return -1
    return 0


def _clamp(args: list[Any]) -> Any:
    value = _number(args[0], "clamp")
    low = _number(args[1], "clamp")
    high = _number(args[2], "clamp")
    if low > high:
        raise Arithmetic(f"clamp was given a low bound {low} above its high bound {high}")
    return max(low, min(value, high))


def _gcd(args: list[Any]) -> int:
    a = _integer(args[0], "gcd")
    b = _integer(args[1], "gcd")
    return math.gcd(a, b)


def _factorial(args: list[Any]) -> int:
    n = _integer(args[0], "factorial")
    if n < 0:
        raise Arithmetic("factorial has no defined result for a negative number")
    return math.factorial(n)


_REGISTRY: dict[str, tuple[int, Any]] = {
    "pow": (2, _power),
    "log": (1, _log),
    "exp": (1, _exp),
    "sin": (1, _sin),
    "cos": (1, _cos),
    "tan": (1, _tan),
    "round": (1, _round),
    "trunc": (1, _trunc),
    "sign": (1, _sign),
    "clamp": (3, _clamp),
    "gcd": (2, _gcd),
    "factorial": (1, _factorial),
}


def install_math_library(machine: Any) -> None:
    for name, (arity, handler) in _REGISTRY.items():
        machine.define_native(name, arity, handler)


def math_names() -> list[str]:
    return sorted(_REGISTRY)
