"""Encodings: turning text into a form that survives being carried somewhere else.

Every function here converts between text and a representation that some transport can
handle, and each is written out rather than delegated. Base sixty four, hexadecimal, and
percent encoding for a web address are the three that matter, plus the character and code
point conversions the others are built from.

Base sixty four is the one with real content. Three bytes become four characters by
regrouping twenty four bits into six bit pieces, and the awkward part is what to do when
the input is not a multiple of three: the standard answer is to pad with equals signs to
keep the length a multiple of four, so a decoder knows how many bytes the last group holds.
That padding is written and required on the way back, because an unpadded encoding is
ambiguous about its final byte in exactly the situation nobody tests. Text is converted to
bytes as UTF-8 first, so anything outside the ASCII range survives the round trip, and the
alphabet is the standard one rather than the URL safe variant, with the variant offered
separately rather than chosen by a flag nobody remembers to pass.

Percent encoding is where the decisions are least obvious. The unreserved set, the letters,
digits, and the four punctuation marks that need no encoding, is what stays literal, and
everything else becomes a percent and two hexadecimal digits. A space becomes percent
twenty rather than a plus sign, because the plus convention belongs to form submission
rather than to addresses, and a decoder that guessed which convention was in use would
sometimes turn a real plus into a space. That distinction is the one that produces wrong
data most often, so the form encoding is a separate function that says what it does.

Nothing here is encryption and nothing here is a hash. Every one of these is reversible by
anyone, which is the point: they are for carrying data, not hiding it, and a program that
used base sixty four to conceal something would be mistaken in a way this module cannot
detect and so says here.
"""

from __future__ import annotations

from typing import Any

from ember.errors import Arithmetic, TypeMismatch
from ember.valueops import type_name

_STANDARD = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/"
_URL_SAFE = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_"
_PAD = "="
_HEX = "0123456789abcdef"
_UNRESERVED = (
    "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~"
)


def _text(value: Any, who: str) -> str:
    if not isinstance(value, str):
        raise TypeMismatch(f"{who} needs a string, not a {type_name(value)}")
    return value


def _whole(value: Any, who: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeMismatch(f"{who} needs a whole number, not a {type_name(value)}")
    return value


def encode_base64(text: str, alphabet: str = _STANDARD) -> str:
    """Three bytes to four characters, padded so the last group is unambiguous."""
    raw = text.encode("utf-8")
    pieces: list[str] = []
    for at in range(0, len(raw), 3):
        group = raw[at : at + 3]
        # the group is padded to three bytes with zeros, and the padding characters
        # then record how many of the four output characters were real
        packed = group[0] << 16
        if len(group) > 1:
            packed |= group[1] << 8
        if len(group) > 2:
            packed |= group[2]
        pieces.append(alphabet[(packed >> 18) & 63])
        pieces.append(alphabet[(packed >> 12) & 63])
        pieces.append(alphabet[(packed >> 6) & 63] if len(group) > 1 else _PAD)
        pieces.append(alphabet[packed & 63] if len(group) > 2 else _PAD)
    return "".join(pieces)


def decode_base64(text: str, alphabet: str = _STANDARD) -> str:
    if len(text) % 4 != 0:
        raise Arithmetic(
            f"base64 text comes in groups of four characters, and this is {len(text)} "
            "long; the padding is required because without it the last byte is ambiguous"
        )
    raw = bytearray()
    for at in range(0, len(text), 4):
        group = text[at : at + 4]
        padding = group.count(_PAD)
        if padding and not group.endswith(_PAD * padding):
            raise Arithmetic("base64 padding can only appear at the very end")
        values: list[int] = []
        for character in group:
            if character == _PAD:
                values.append(0)
                continue
            where = alphabet.find(character)
            if where < 0:
                raise Arithmetic(f"the character {character!r} is not in the base64 alphabet")
            values.append(where)
        packed = (values[0] << 18) | (values[1] << 12) | (values[2] << 6) | values[3]
        raw.append((packed >> 16) & 255)
        if padding < 2:
            raw.append((packed >> 8) & 255)
        if padding < 1:
            raw.append(packed & 255)
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as bad:
        raise Arithmetic(
            "the decoded bytes are not text this language can hold, which usually "
            "means the encoded data was not text to begin with"
        ) from bad


def _to_base64(args: list[Any]) -> str:
    return encode_base64(_text(args[0], "toBase64"))


def _from_base64(args: list[Any]) -> str:
    return decode_base64(_text(args[0], "fromBase64"))


def _to_base64_url(args: list[Any]) -> str:
    return encode_base64(_text(args[0], "toBase64Url"), _URL_SAFE)


def _from_base64_url(args: list[Any]) -> str:
    return decode_base64(_text(args[0], "fromBase64Url"), _URL_SAFE)


def _to_hex_text(args: list[Any]) -> str:
    raw = _text(args[0], "toHexText").encode("utf-8")
    return "".join(_HEX[byte >> 4] + _HEX[byte & 15] for byte in raw)


def _from_hex_text(args: list[Any]) -> str:
    text = _text(args[0], "fromHexText").lower()
    if len(text) % 2 != 0:
        raise Arithmetic(
            f"hexadecimal text comes in pairs, one per byte, and this is {len(text)} long"
        )
    raw = bytearray()
    for at in range(0, len(text), 2):
        high = _HEX.find(text[at])
        low = _HEX.find(text[at + 1])
        if high < 0 or low < 0:
            raise Arithmetic(f"{text[at : at + 2]!r} is not a pair of hexadecimal digits")
        raw.append(high * 16 + low)
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as bad:
        raise Arithmetic("the decoded bytes are not text this language can hold") from bad


def _encoded_for_url(args: list[Any]) -> str:
    text = _text(args[0], "urlEncoded")
    pieces: list[str] = []
    for byte in text.encode("utf-8"):
        character = chr(byte)
        if character in _UNRESERVED:
            pieces.append(character)
        else:
            # a space becomes its percent form, not a plus: the plus convention
            # belongs to form submission and guessing between them loses real data
            pieces.append("%" + _HEX[byte >> 4].upper() + _HEX[byte & 15].upper())
    return "".join(pieces)


def _decoded_from_url(args: list[Any]) -> str:
    text = _text(args[0], "urlDecoded")
    raw = bytearray()
    at = 0
    while at < len(text):
        character = text[at]
        if character == "%":
            pair = text[at + 1 : at + 3]
            if len(pair) != 2:
                raise Arithmetic(f"a percent escape at position {at} is incomplete")
            high = _HEX.find(pair[0].lower())
            low = _HEX.find(pair[1].lower())
            if high < 0 or low < 0:
                raise Arithmetic(f"{pair!r} is not a pair of hexadecimal digits")
            raw.append(high * 16 + low)
            at += 3
            continue
        raw.append(ord(character) if ord(character) < 128 else 63)
        at += 1
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as bad:
        raise Arithmetic("the decoded bytes are not text this language can hold") from bad


def _encoded_for_form(args: list[Any]) -> str:
    """The form convention, where a space is a plus, offered separately and named."""
    return _encoded_for_url(args).replace("%20", "+")


def _decoded_from_form(args: list[Any]) -> str:
    text = _text(args[0], "formDecoded")
    return _decoded_from_url([text.replace("+", "%20")])


def _code_point(args: list[Any]) -> int:
    text = _text(args[0], "codePoint")
    if len(text) != 1:
        raise Arithmetic(
            f"codePoint reads one character, and this string holds {len(text)}"
        )
    return ord(text)


def _from_code_point(args: list[Any]) -> str:
    value = _whole(args[0], "fromCodePoint")
    if not 0 <= value <= 0x10FFFF:
        raise Arithmetic(f"{value} is not a character code point")
    return chr(value)


def _code_points(args: list[Any]) -> list[int]:
    return [ord(character) for character in _text(args[0], "codePoints")]


def _from_code_points(args: list[Any]) -> str:
    values = args[0]
    if not isinstance(values, list):
        raise TypeMismatch(f"fromCodePoints needs a list, not a {type_name(values)}")
    return "".join(_from_code_point([value]) for value in values)


def _byte_length(args: list[Any]) -> int:
    """How many bytes the text takes as UTF-8, which is not its character count."""
    return len(_text(args[0], "byteLength").encode("utf-8"))


def _is_ascii(args: list[Any]) -> bool:
    return all(ord(character) < 128 for character in _text(args[0], "isAscii"))


_REGISTRY: dict[str, tuple[int, Any]] = {
    "toBase64": (1, _to_base64),
    "fromBase64": (1, _from_base64),
    "toBase64Url": (1, _to_base64_url),
    "fromBase64Url": (1, _from_base64_url),
    "toHexText": (1, _to_hex_text),
    "fromHexText": (1, _from_hex_text),
    "urlEncoded": (1, _encoded_for_url),
    "urlDecoded": (1, _decoded_from_url),
    "formEncoded": (1, _encoded_for_form),
    "formDecoded": (1, _decoded_from_form),
    "codePoint": (1, _code_point),
    "fromCodePoint": (1, _from_code_point),
    "codePoints": (1, _code_points),
    "fromCodePoints": (1, _from_code_points),
    "byteLength": (1, _byte_length),
    "isAscii": (1, _is_ascii),
}


def install_encode_library(machine: Any) -> None:
    for name, (arity, handler) in _REGISTRY.items():
        machine.define_native(name, arity, handler)


def encode_names() -> list[str]:
    return sorted(_REGISTRY)
