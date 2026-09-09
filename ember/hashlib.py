"""Hashes for spreading values out, and the loud warning that none of them hide anything.

These are the small non cryptographic hashes: FNV, the one Dan Bernstein published, the
polynomial one Java uses, and a cyclic redundancy check. Each turns text into a number, and
what they are for is spreading values evenly over buckets and noticing accidental corruption,
which are the two jobs a hash actually does in an ordinary program.

None of them is secure and the difference is not a matter of degree. A cryptographic hash is
built so that finding two inputs with one output is infeasible; these are built so that
similar inputs land far apart, which is a much weaker property and easy to satisfy. Anyone who
wants a collision with one of these can construct one in seconds. So none of these may be used
for a password, a token, a signature, or anything where an adversary benefits from a collision,
and since this module cannot detect such a use, saying so plainly here is the whole of the
defence. The redundancy check is the sharpest case: it detects the bit flips a transmission
error produces and offers no resistance at all to a change someone made on purpose.

What each is good at differs enough to be worth stating. FNV and Bernstein's are fast, spread
well, and are what a hash table wants. The polynomial hash is here because so much data in the
world was bucketed with it that reproducing a bucket assignment sometimes requires it, and it
is a poor hash: short strings cluster and it multiplies by thirty one, which is small enough
that the high bits of a long string barely move. The redundancy check is slower, spreads worse,
and detects corruption far better, which is the trade it exists to make.

Everything works on the UTF-8 bytes of the text rather than on its characters, so a hash here
matches what another implementation would compute for the same text, and everything is
computed within thirty two bits with the wrapping written out, because this language's integers
do not overflow and a hash that grew without bound would agree with nothing.
"""

from __future__ import annotations

from typing import Any

from ember.errors import Arithmetic, TypeMismatch
from ember.valueops import type_name

_MASK = 0xFFFFFFFF
_FNV_OFFSET = 0x811C9DC5
_FNV_PRIME = 0x01000193
_CRC_POLYNOMIAL = 0xEDB88320


def _text(value: Any, who: str) -> str:
    if not isinstance(value, str):
        raise TypeMismatch(f"{who} needs a string, not a {type_name(value)}")
    return value


def _bytes_of(value: Any, who: str) -> bytes:
    return _text(value, who).encode("utf-8")


def fnv1a(raw: bytes) -> int:
    """FNV in its 1a form, which mixes before multiplying rather than after."""
    value = _FNV_OFFSET
    for byte in raw:
        value ^= byte
        # the wrapping is written out because this language's integers do not overflow
        value = (value * _FNV_PRIME) & _MASK
    return value


def fnv1(raw: bytes) -> int:
    """The original order, multiplying before mixing, kept for comparison."""
    value = _FNV_OFFSET
    for byte in raw:
        value = (value * _FNV_PRIME) & _MASK
        value ^= byte
    return value


def djb2(raw: bytes) -> int:
    """Bernstein's: five bits of shift and an add, which is a multiply by thirty three."""
    value = 5381
    for byte in raw:
        value = ((value * 33) + byte) & _MASK
    return value


def sdbm(raw: bytes) -> int:
    value = 0
    for byte in raw:
        value = (byte + (value << 6) + (value << 16) - value) & _MASK
    return value


def polynomial(raw: bytes) -> int:
    """The multiply by thirty one hash, which is poor and sometimes required."""
    value = 0
    for byte in raw:
        value = ((value * 31) + byte) & _MASK
    return value


def _crc_table() -> tuple[int, ...]:
    """One entry per byte, each the remainder of that byte shifted eight times."""
    entries: list[int] = []
    for index in range(256):
        value = index
        for _ in range(8):
            value = (value >> 1) ^ (_CRC_POLYNOMIAL if value & 1 else 0)
        entries.append(value)
    return tuple(entries)


_CRC_TABLE = _crc_table()


def crc32(raw: bytes) -> int:
    """A cyclic redundancy check, table driven, for noticing accidental corruption."""
    value = _MASK
    for byte in raw:
        value = _CRC_TABLE[(value ^ byte) & 0xFF] ^ (value >> 8)
    return value ^ _MASK


def _fnv1a(args: list[Any]) -> int:
    return fnv1a(_bytes_of(args[0], "fnv1a"))


def _fnv1(args: list[Any]) -> int:
    return fnv1(_bytes_of(args[0], "fnv1"))


def _djb2(args: list[Any]) -> int:
    return djb2(_bytes_of(args[0], "djb2"))


def _sdbm(args: list[Any]) -> int:
    return sdbm(_bytes_of(args[0], "sdbm"))


def _polynomial(args: list[Any]) -> int:
    return polynomial(_bytes_of(args[0], "polynomialHash"))


def _crc32(args: list[Any]) -> int:
    return crc32(_bytes_of(args[0], "crc32"))


def _bucket_of(args: list[Any]) -> int:
    """Which of a number of buckets a value falls into, which is what a hash is for."""
    text = _text(args[0], "bucketOf")
    count = args[1]
    if isinstance(count, bool) or not isinstance(count, int):
        raise TypeMismatch(
            f"bucketOf needs a whole number of buckets, not a {type_name(count)}"
        )
    if count < 1:
        raise Arithmetic(f"bucketOf needs at least one bucket, not {count}")
    return fnv1a(text.encode("utf-8")) % count


def _checksum_matches(args: list[Any]) -> bool:
    text = _text(args[0], "checksumMatches")
    expected = args[1]
    if isinstance(expected, bool) or not isinstance(expected, int):
        raise TypeMismatch(
            f"checksumMatches needs a whole number checksum, not a {type_name(expected)}"
        )
    return crc32(text.encode("utf-8")) == expected


def _spread_of(args: list[Any]) -> list[int]:
    """How many of a list of strings land in each bucket, for judging a hash."""
    values = args[0]
    if not isinstance(values, list):
        raise TypeMismatch(f"spreadOf needs a list, not a {type_name(values)}")
    count = args[1]
    if isinstance(count, bool) or not isinstance(count, int):
        raise TypeMismatch(
            f"spreadOf needs a whole number of buckets, not a {type_name(count)}"
        )
    if count < 1:
        raise Arithmetic(f"spreadOf needs at least one bucket, not {count}")
    tally = [0] * count
    for value in values:
        tally[fnv1a(_text(value, "spreadOf").encode("utf-8")) % count] += 1
    return tally


_REGISTRY: dict[str, tuple[int, Any]] = {
    "fnv1a": (1, _fnv1a),
    "fnv1": (1, _fnv1),
    "djb2": (1, _djb2),
    "sdbm": (1, _sdbm),
    "polynomialHash": (1, _polynomial),
    "crc32": (1, _crc32),
    "bucketOf": (2, _bucket_of),
    "checksumMatches": (2, _checksum_matches),
    "spreadOf": (2, _spread_of),
}


def install_hash_library(machine: Any) -> None:
    for name, (arity, handler) in _REGISTRY.items():
        machine.define_native(name, arity, handler)


def hash_names() -> list[str]:
    return sorted(_REGISTRY)
