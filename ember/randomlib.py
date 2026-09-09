"""Random numbers that are entirely determined by a seed, and never by anything else.

Every generator here is seeded explicitly and there is no way to seed one from the
clock or from the host's entropy. That is a deliberate restriction with a specific
purpose: a program using randomness should be reproducible, because a program that
behaves differently on every run cannot be debugged from a report of what it did. A
caller who wants a different sequence changes the seed, which is a visible act recorded
in the program, rather than an invisible one that happens because time passed.

The generator is written out rather than delegated to the host, and the reason is the
same reproducibility. The host's generator can change between versions, so a program
that produced one sequence today could produce another after an upgrade, and a seed
would no longer identify a run. The algorithm chosen is a xorshift over sixty four bits:
three shifts and three exclusive ors per value, which is fast, has a period of two to
the sixty four minus one, and passes the usual statistical batteries for the uses a
language like this puts randomness to, shuffling a list and picking a sample.

What it is not is cryptographic, and that needs saying plainly because the failure is
silent. The state is recoverable from a handful of outputs, so anything generated here
is predictable to anyone who has seen enough of the sequence. It must not be used for
keys, tokens, passwords or anything an adversary should not be able to guess, and since
there is no way for this module to detect such a use, the warning is all it can offer.
The seed is mixed before it becomes state, and that step exists because the first
version did not have it and was badly wrong in a way only measurement showed. Raw
xorshift starting from a small number produces small numbers for its first several
steps, since the shifts need a populated word to work with, and every function here
takes a fresh seed and uses its first output. Drawing between two values weighted three
to one, with the seeds one through four thousand, chose the heavier value four thousand
times out of four thousand: not biased, but total. Shuffling three values over six
thousand seeds was visibly lumpy for the same reason. Passing the seed through the
SplitMix64 mixing function first, which is three multiplications and three xor shifts,
fixes both, and the tests pin the distributions rather than trusting the algorithm.
Mixing also removes the one seed raw xorshift could not accept: zero is a fixed point of
the shifts and would have produced zero forever, so it used to be refused, and after
mixing it is an ordinary seed like any other.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ember.errors import Arithmetic, TypeMismatch
from ember.valueops import type_name

_MASK = (1 << 64) - 1


def mixed(seed: int) -> int:
    """SplitMix64's finalizer, which turns a small seed into a populated word.

    Without this a seed of one produces a first output near zero, so any function
    reading one number from a fresh seed was reading almost the same number every time.
    """
    value = (seed + 0x9E3779B97F4A7C15) & _MASK
    value = ((value ^ (value >> 30)) * 0xBF58476D1CE4E5B9) & _MASK
    value = ((value ^ (value >> 27)) * 0x94D049BB133111EB) & _MASK
    value ^= value >> 31
    # a mixed word can still land on zero, which xorshift cannot start from, so the
    # one forbidden state is replaced by another populated word rather than refused
    return value & _MASK or 0x9E3779B97F4A7C15


@dataclass
class Stream:
    """A xorshift generator: its whole future is its state, and its state is the seed."""

    state: int

    def __post_init__(self) -> None:
        self.state = mixed(self.state)

    def next_bits(self) -> int:
        """One step of xorshift64: three shifts and three exclusive ors."""
        value = self.state
        value ^= (value << 13) & _MASK
        value ^= value >> 7
        value ^= (value << 17) & _MASK
        self.state = value & _MASK
        return self.state

    def next_fraction(self) -> float:
        # the top 53 bits, which is exactly what a double can hold without rounding
        return (self.next_bits() >> 11) / (1 << 53)

    def below(self, limit: int) -> int:
        if limit < 1:
            raise Arithmetic(f"a whole number below {limit} does not exist")
        return self.next_bits() % limit

    def between(self, low: int, high: int) -> int:
        if high < low:
            raise Arithmetic(
                f"a range runs from a lower number to a higher one, so {low} to "
                f"{high} is empty"
            )
        return low + self.below(high - low + 1)


def _seed_of(value: Any, who: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeMismatch(f"{who} needs a whole number seed, not a {type_name(value)}")
    return value


def _whole(value: Any, who: str, what: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeMismatch(f"{who} needs a whole number {what}, not a {type_name(value)}")
    return value


def _list_of(value: Any, who: str) -> list[Any]:
    if not isinstance(value, list):
        raise TypeMismatch(f"{who} needs a list, not a {type_name(value)}")
    return value


def _stream(args: list[Any], who: str) -> Stream:
    return Stream(_seed_of(args[0], who))


def _random_bits(args: list[Any]) -> int:
    return _stream(args, "randomBits").next_bits()


def _random_fraction(args: list[Any]) -> float:
    return _stream(args, "randomFraction").next_fraction()


def _random_below(args: list[Any]) -> int:
    stream = _stream(args, "randomBelow")
    return stream.below(_whole(args[1], "randomBelow", "limit"))


def _random_between(args: list[Any]) -> int:
    stream = _stream(args, "randomBetween")
    low = _whole(args[1], "randomBetween", "lower bound")
    high = _whole(args[2], "randomBetween", "upper bound")
    return stream.between(low, high)


def _random_list(args: list[Any]) -> list[int]:
    """A run of numbers from one seed, which is what a caller usually wants."""
    stream = _stream(args, "randomList")
    count = _whole(args[1], "randomList", "count")
    limit = _whole(args[2], "randomList", "limit")
    if count < 0:
        raise Arithmetic(f"randomList needs a count of zero or more, not {count}")
    return [stream.below(limit) for _ in range(count)]


def _random_fractions(args: list[Any]) -> list[float]:
    stream = _stream(args, "randomFractions")
    count = _whole(args[1], "randomFractions", "count")
    if count < 0:
        raise Arithmetic(f"randomFractions needs a count of zero or more, not {count}")
    return [stream.next_fraction() for _ in range(count)]


def _pick(args: list[Any]) -> Any:
    stream = _stream(args, "pick")
    values = _list_of(args[1], "pick")
    if not values:
        raise Arithmetic("pick has nothing to choose from, because the list is empty")
    return values[stream.below(len(values))]


def _shuffled(args: list[Any]) -> list[Any]:
    """A Fisher and Yates shuffle, which gives every ordering the same chance."""
    stream = _stream(args, "shuffled")
    values = list(_list_of(args[1], "shuffled"))
    for index in range(len(values) - 1, 0, -1):
        # the swap partner is chosen from the unshuffled part only, which is the
        # detail that separates a fair shuffle from a subtly biased one
        other = stream.below(index + 1)
        values[index], values[other] = values[other], values[index]
    return values


def _sample(args: list[Any]) -> list[Any]:
    stream = _stream(args, "sample")
    values = list(_list_of(args[1], "sample"))
    count = _whole(args[2], "sample", "count")
    if count < 0:
        raise Arithmetic(f"sample needs a count of zero or more, not {count}")
    if count > len(values):
        raise Arithmetic(
            f"sample was asked for {count} values from a list of {len(values)}, and "
            "it never repeats a value; use randomList to draw with replacement"
        )
    for index in range(len(values) - 1, 0, -1):
        other = stream.below(index + 1)
        values[index], values[other] = values[other], values[index]
    return values[:count]


def _weighted_pick(args: list[Any]) -> Any:
    stream = _stream(args, "weightedPick")
    values = _list_of(args[1], "weightedPick")
    weights = _list_of(args[2], "weightedPick")
    if len(values) != len(weights):
        raise Arithmetic(
            f"weightedPick was given {len(values)} values and {len(weights)} weights, "
            "and it needs one weight for each value"
        )
    if not values:
        raise Arithmetic("weightedPick has nothing to choose from")
    total = 0
    for weight in weights:
        if isinstance(weight, bool) or not isinstance(weight, (int, float)):
            raise TypeMismatch(f"a weight must be a number, not a {type_name(weight)}")
        if weight < 0:
            raise Arithmetic(f"a weight cannot be negative, but one is {weight}")
        total += weight
    if total == 0:
        raise Arithmetic("every weight is zero, so no value can be chosen")
    landing = stream.next_fraction() * total
    running = 0.0
    for value, weight in zip(values, weights, strict=True):
        running += weight
        if landing < running:
            return value
    # floating point can leave the landing exactly at the total, so the last value
    # answers rather than the loop falling through to nothing
    return values[-1]


def _next_seed(args: list[Any]) -> int:
    """The state after one step, so a caller can carry a stream forward by hand."""
    return _stream(args, "nextSeed").next_bits()


def _dice(args: list[Any]) -> list[int]:
    stream = _stream(args, "dice")
    count = _whole(args[1], "dice", "count")
    sides = _whole(args[2], "dice", "number of sides")
    if count < 0:
        raise Arithmetic(f"dice needs a count of zero or more, not {count}")
    if sides < 1:
        raise Arithmetic(f"a die needs at least one side, not {sides}")
    return [stream.between(1, sides) for _ in range(count)]


_REGISTRY: dict[str, tuple[int, Any]] = {
    "randomBits": (1, _random_bits),
    "randomFraction": (1, _random_fraction),
    "randomBelow": (2, _random_below),
    "randomBetween": (3, _random_between),
    "randomList": (3, _random_list),
    "randomFractions": (2, _random_fractions),
    "pick": (2, _pick),
    "shuffled": (2, _shuffled),
    "sample": (3, _sample),
    "weightedPick": (3, _weighted_pick),
    "nextSeed": (1, _next_seed),
    "dice": (3, _dice),
}


def install_random_library(machine: Any) -> None:
    for name, (arity, handler) in _REGISTRY.items():
        machine.define_native(name, arity, handler)


def random_names() -> list[str]:
    return sorted(_REGISTRY)
