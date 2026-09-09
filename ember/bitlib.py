"""Bit manipulation: operations on the binary shape of a whole number.

The operators cover the six bitwise operations, and this library covers what a program
needs once it is treating a number as a row of bits rather than as a quantity: counting
the ones, finding the highest set bit, rotating within a fixed width, reading and
writing individual positions, and converting to and from the written binary and
hexadecimal forms.

Two decisions run through all of it. Every function refuses a float, because a bit at
position three of two and a half is not a question with an answer, and truncating
silently would let a program that computed a fraction by mistake keep running with a
number nobody chose. And every operation that needs a width takes it explicitly rather
than assuming one, because this language's integers do not have a width: they are
arbitrary precision, so there is no natural number of bits to rotate within or to
complement against. A rotate needs to know whether it is working in eight bits or
thirty two, and a caller who did not say cannot be guessed at. That makes the
signatures longer than they would be in a language with fixed width integers, and it
means a rotate here is exact rather than approximately what the caller meant.

Negative numbers are the sharp edge, and the treatment is deliberate. A negative
integer has no finite binary representation without a chosen width, so the functions
that read a number's bits refuse a negative value rather than assuming two's complement
at some width the caller never named. The ones that work within a stated width do
accept negatives and interpret them as two's complement at that width, which is the
only reading that makes sense once a width exists. Anywhere the two rules could be
confused, the message says which one applies.
"""

from __future__ import annotations

from typing import Any

from ember.errors import Arithmetic, TypeMismatch
from ember.valueops import type_name

_MAX_WIDTH = 256


def _whole(value: Any, who: str, what: str = "number") -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeMismatch(
            f"{who} needs a whole {what}, not a {type_name(value)}; a bit position "
            "in a fraction is not a question with an answer"
        )
    return value


def _not_negative(value: int, who: str) -> int:
    if value < 0:
        raise Arithmetic(
            f"{who} was given {value}, and a negative number has no binary form "
            "without a chosen width; use a function that takes a width"
        )
    return value


def _width(value: Any, who: str) -> int:
    width = _whole(value, who, "width")
    if width < 1:
        raise Arithmetic(f"{who} needs a width of at least one bit, not {width}")
    if width > _MAX_WIDTH:
        raise Arithmetic(f"{who} works up to {_MAX_WIDTH} bits, so {width} is too wide")
    return width


def _position(value: Any, who: str) -> int:
    position = _whole(value, who, "bit position")
    if position < 0:
        raise Arithmetic(f"{who} counts bit positions from zero, so {position} has no meaning")
    return position


def _ones(args: list[Any]) -> int:
    """How many bits are set, which is the population count."""
    value = _not_negative(_whole(args[0], "countOnes"), "countOnes")
    total = 0
    while value:
        # clearing the lowest set bit each time, so the loop runs once per one
        value &= value - 1
        total += 1
    return total


def _bit_length(args: list[Any]) -> int:
    value = _not_negative(_whole(args[0], "bitLength"), "bitLength")
    return value.bit_length()


def _highest_bit(args: list[Any]) -> int:
    value = _not_negative(_whole(args[0], "highestBit"), "highestBit")
    if value == 0:
        raise Arithmetic("highestBit has no answer for zero, which has no bits set")
    return value.bit_length() - 1


def _lowest_bit(args: list[Any]) -> int:
    value = _not_negative(_whole(args[0], "lowestBit"), "lowestBit")
    if value == 0:
        raise Arithmetic("lowestBit has no answer for zero, which has no bits set")
    return (value & -value).bit_length() - 1


def _test_bit(args: list[Any]) -> bool:
    value = _not_negative(_whole(args[0], "testBit"), "testBit")
    return bool(value >> _position(args[1], "testBit") & 1)


def _set_bit(args: list[Any]) -> int:
    value = _not_negative(_whole(args[0], "setBit"), "setBit")
    return value | (1 << _position(args[1], "setBit"))


def _clear_bit(args: list[Any]) -> int:
    value = _not_negative(_whole(args[0], "clearBit"), "clearBit")
    return value & ~(1 << _position(args[1], "clearBit"))


def _flip_bit(args: list[Any]) -> int:
    value = _not_negative(_whole(args[0], "flipBit"), "flipBit")
    return value ^ (1 << _position(args[1], "flipBit"))


def _is_power_of_two(args: list[Any]) -> bool:
    value = _not_negative(_whole(args[0], "isPowerOfTwo"), "isPowerOfTwo")
    return value != 0 and value & (value - 1) == 0


def _next_power_of_two(args: list[Any]) -> int:
    value = _not_negative(_whole(args[0], "nextPowerOfTwo"), "nextPowerOfTwo")
    if value <= 1:
        return 1
    return 1 << (value - 1).bit_length()


def _mask_of(args: list[Any]) -> int:
    """A run of ones that many bits wide, which is what masking needs."""
    return (1 << _width(args[0], "mask")) - 1


def _low_bits(args: list[Any]) -> int:
    value = _whole(args[0], "lowBits")
    width = _width(args[1], "lowBits")
    # a negative value is read as two's complement at this width, which is the only
    # reading that makes sense once a width has been named
    return value & ((1 << width) - 1)


def _rotate_left(args: list[Any]) -> int:
    width = _width(args[2], "rotateLeft")
    mask = (1 << width) - 1
    value = _whole(args[0], "rotateLeft") & mask
    by = _whole(args[1], "rotateLeft", "rotation") % width
    return ((value << by) | (value >> (width - by))) & mask


def _rotate_right(args: list[Any]) -> int:
    width = _width(args[2], "rotateRight")
    mask = (1 << width) - 1
    value = _whole(args[0], "rotateRight") & mask
    by = _whole(args[1], "rotateRight", "rotation") % width
    return ((value >> by) | (value << (width - by))) & mask


def _complement(args: list[Any]) -> int:
    width = _width(args[1], "complement")
    value = _whole(args[0], "complement") & ((1 << width) - 1)
    return value ^ ((1 << width) - 1)


def _reverse_bits(args: list[Any]) -> int:
    width = _width(args[1], "reverseBits")
    value = _whole(args[0], "reverseBits") & ((1 << width) - 1)
    turned = 0
    for _ in range(width):
        turned = (turned << 1) | (value & 1)
        value >>= 1
    return turned


def _to_binary(args: list[Any]) -> str:
    value = _not_negative(_whole(args[0], "toBinary"), "toBinary")
    return format(value, "b")


def _to_binary_width(args: list[Any]) -> str:
    width = _width(args[1], "toBinaryWidth")
    value = _whole(args[0], "toBinaryWidth") & ((1 << width) - 1)
    return format(value, "0" + str(width) + "b")


def _from_binary(args: list[Any]) -> int:
    text = args[0]
    if not isinstance(text, str):
        raise TypeMismatch(f"fromBinary needs a string, not a {type_name(text)}")
    if not text or any(character not in "01" for character in text):
        raise Arithmetic(f"fromBinary reads only ones and zeros, so it cannot read {text!r}")
    return int(text, 2)


def _to_hex(args: list[Any]) -> str:
    value = _not_negative(_whole(args[0], "toHex"), "toHex")
    return format(value, "x")


def _from_hex(args: list[Any]) -> int:
    text = args[0]
    if not isinstance(text, str):
        raise TypeMismatch(f"fromHex needs a string, not a {type_name(text)}")
    try:
        return int(text, 16)
    except ValueError as bad:
        raise Arithmetic(f"fromHex cannot read {text!r} as hexadecimal") from bad


def _parity(args: list[Any]) -> int:
    """Zero when an even number of bits are set, one when odd."""
    return _ones(args) % 2


def _hamming(args: list[Any]) -> int:
    """How many bit positions two numbers differ in."""
    left = _not_negative(_whole(args[0], "hammingDistance"), "hammingDistance")
    right = _not_negative(_whole(args[1], "hammingDistance"), "hammingDistance")
    return _ones([left ^ right])


def _bits_of(args: list[Any]) -> list[int]:
    """The bits as a list, highest first, so a program can walk them."""
    width = _width(args[1], "bitsOf")
    value = _whole(args[0], "bitsOf") & ((1 << width) - 1)
    return [(value >> position) & 1 for position in range(width - 1, -1, -1)]


def _from_bits(args: list[Any]) -> int:
    values = args[0]
    if not isinstance(values, list):
        raise TypeMismatch(f"fromBits needs a list, not a {type_name(values)}")
    total = 0
    for entry in values:
        if entry not in (0, 1) or isinstance(entry, bool):
            raise Arithmetic(f"fromBits reads a list of ones and zeros, but found {entry!r}")
        total = (total << 1) | entry
    return total


_REGISTRY: dict[str, tuple[int, Any]] = {
    "countOnes": (1, _ones),
    "bitLength": (1, _bit_length),
    "highestBit": (1, _highest_bit),
    "lowestBit": (1, _lowest_bit),
    "testBit": (2, _test_bit),
    "setBit": (2, _set_bit),
    "clearBit": (2, _clear_bit),
    "flipBit": (2, _flip_bit),
    "isPowerOfTwo": (1, _is_power_of_two),
    "nextPowerOfTwo": (1, _next_power_of_two),
    "mask": (1, _mask_of),
    "lowBits": (2, _low_bits),
    "rotateLeft": (3, _rotate_left),
    "rotateRight": (3, _rotate_right),
    "complement": (2, _complement),
    "reverseBits": (2, _reverse_bits),
    "toBinary": (1, _to_binary),
    "toBinaryWidth": (2, _to_binary_width),
    "fromBinary": (1, _from_binary),
    "toHex": (1, _to_hex),
    "fromHex": (1, _from_hex),
    "parity": (1, _parity),
    "hammingDistance": (2, _hamming),
    "bitsOf": (2, _bits_of),
    "fromBits": (1, _from_bits),
}


def install_bit_library(machine: Any) -> None:
    for name, (arity, handler) in _REGISTRY.items():
        machine.define_native(name, arity, handler)


def bit_names() -> list[str]:
    return sorted(_REGISTRY)
