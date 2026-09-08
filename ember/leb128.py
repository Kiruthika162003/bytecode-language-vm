"""LEB128: encode an integer in as few bytes as its magnitude actually needs.

A serialized bytecode file is full of integers whose typical values are
tiny and whose worst case is not: a constant-pool index, a code length, a
line number, a repeat count. Giving each a fixed four or eight bytes wastes
most of them on leading zeros, and giving each a single byte breaks the
moment a program is large. LEB128 resolves this by spending one byte per
seven bits of value, using each byte's top bit as a continuation flag: set
means another byte follows, clear means this was the last. So a value under
128 costs one byte, one under 16384 costs two, and an arbitrarily large
value still encodes correctly, which is what lets the format stay compact
on the common case without imposing a ceiling. Signed values need a second
scheme, because the unsigned encoding would spend many bytes on the sign
extension of a small negative number; the signed variant instead
sign-extends within the seven-bit groups and stops when the remaining bits
are all copies of the sign, so minus one costs one byte rather than ten.
The decoder is where a format like this earns its trust or loses it, so
this one refuses a truncated stream, whose last byte still asks for a
continuation, rather than returning a plausible half-decoded number. The
honest cost of the scheme is that decoding is inherently sequential: a
value's length is only known by reading it, so nothing can be seeked to by
arithmetic and a reader must walk the stream from a known point.
"""

from __future__ import annotations

from ember.errors import Compile

_CONTINUATION = 0x80
_PAYLOAD = 0x7F
_GROUP_BITS = 7
_SIGN_BIT = 0x40


def encode_unsigned(value: int) -> bytes:
    if value < 0:
        raise Compile(
            f"cannot encode the negative value {value} as an unsigned varint; "
            "use the signed encoding instead"
        )
    out = bytearray()
    while True:
        group = value & _PAYLOAD
        value >>= _GROUP_BITS
        if value:
            out.append(group | _CONTINUATION)
        else:
            out.append(group)
            return bytes(out)


def decode_unsigned(data: bytes, offset: int = 0) -> tuple[int, int]:
    result = 0
    shift = 0
    cursor = offset
    while True:
        if cursor >= len(data):
            raise Compile(
                "the varint stream ends mid-value; the last byte still asks for "
                "a continuation, so the data is truncated"
            )
        byte = data[cursor]
        cursor += 1
        result |= (byte & _PAYLOAD) << shift
        if not byte & _CONTINUATION:
            return result, cursor
        shift += _GROUP_BITS


def encode_signed(value: int) -> bytes:
    out = bytearray()
    while True:
        group = value & _PAYLOAD
        value >>= _GROUP_BITS
        # stop once the remaining bits are all copies of the sign and the group
        # itself carries that sign, otherwise one more byte is needed
        done = (value == 0 and not group & _SIGN_BIT) or (
            value == -1 and group & _SIGN_BIT
        )
        if done:
            out.append(group)
            return bytes(out)
        out.append(group | _CONTINUATION)


def decode_signed(data: bytes, offset: int = 0) -> tuple[int, int]:
    result = 0
    shift = 0
    cursor = offset
    while True:
        if cursor >= len(data):
            raise Compile(
                "the varint stream ends mid-value; the last byte still asks for "
                "a continuation, so the data is truncated"
            )
        byte = data[cursor]
        cursor += 1
        result |= (byte & _PAYLOAD) << shift
        shift += _GROUP_BITS
        if not byte & _CONTINUATION:
            if byte & _SIGN_BIT:
                result -= 1 << shift
            return result, cursor
