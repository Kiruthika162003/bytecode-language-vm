"""The string library: native text operations a program cannot build from indexing alone.

Indexing gives a program one character at a time, but real work with text
needs whole operations: splitting on a separator, joining a list back
together, changing case, trimming surrounding space, testing a prefix,
finding a substring. Those cannot be written efficiently, or at all, in
terms of single-character access, so this module supplies them as native
functions that operate on the host's string type directly. Each one
validates that it received a string where it expects one and reports a
type mismatch in the language's voice otherwise, so a program that passes
a number to upper learns what it did wrong rather than seeing a host
error. Two conventions keep the surface predictable. Every function is
pure, returning a new string or value and never mutating its argument,
because strings in this language are immutable and a function that
appeared to change one in place would be lying about the model. And
indices follow the same rule as the indexing operator, counting from
zero and reporting a position of minus one for a search that found
nothing, so a caller tests the result the same way everywhere. The
honest boundary is Unicode: these operate on code points, matching the
rest of the runtime, so case folding is the host's simple mapping and a
character that needs locale-aware or multi-code-point folding is not
special-cased, which is a limitation this small library states rather
than hides.
"""

from __future__ import annotations

from typing import Any

from ember.errors import IndexRange, TypeMismatch
from ember.valueops import type_name


def _string(value: Any, who: str) -> str:
    if not isinstance(value, str):
        raise TypeMismatch(f"{who} needs a string, not a {type_name(value)}")
    return value


def _upper(args: list[Any]) -> str:
    return _string(args[0], "upper").upper()


def _lower(args: list[Any]) -> str:
    return _string(args[0], "lower").lower()


def _trim(args: list[Any]) -> str:
    return _string(args[0], "trim").strip()


def _split(args: list[Any]) -> list[str]:
    text = _string(args[0], "split")
    separator = _string(args[1], "split")
    if separator == "":
        return list(text)
    return text.split(separator)


def _join(args: list[Any]) -> str:
    parts = args[0]
    separator = _string(args[1], "join")
    if not isinstance(parts, list):
        raise TypeMismatch(f"join needs a list of strings, not a {type_name(parts)}")
    for part in parts:
        if not isinstance(part, str):
            raise TypeMismatch(
                f"join needs every element to be a string, not a {type_name(part)}"
            )
    return separator.join(parts)


def _replace(args: list[Any]) -> str:
    text = _string(args[0], "replace")
    target = _string(args[1], "replace")
    with_text = _string(args[2], "replace")
    if target == "":
        raise IndexRange("replace needs a non-empty target to search for")
    return text.replace(target, with_text)


def _starts_with(args: list[Any]) -> bool:
    return _string(args[0], "starts_with").startswith(_string(args[1], "starts_with"))


def _ends_with(args: list[Any]) -> bool:
    return _string(args[0], "ends_with").endswith(_string(args[1], "ends_with"))


def _index_of(args: list[Any]) -> int:
    return _string(args[0], "index_of").find(_string(args[1], "index_of"))


def _substring(args: list[Any]) -> str:
    text = _string(args[0], "substring")
    start = args[1]
    end = args[2]
    for value in (start, end):
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeMismatch("substring needs integer start and end positions")
    if start < 0 or end > len(text) or start > end:
        raise IndexRange(
            f"the range {start} to {end} is not valid for a string of length "
            f"{len(text)}"
        )
    return text[start:end]


def _repeat(args: list[Any]) -> str:
    text = _string(args[0], "repeat")
    count = args[1]
    if isinstance(count, bool) or not isinstance(count, int):
        raise TypeMismatch("repeat needs an integer count")
    if count < 0:
        raise IndexRange("repeat needs a count of zero or more")
    return text * count


def _chars(args: list[Any]) -> list[str]:
    return list(_string(args[0], "chars"))


def _code_at(args: list[Any]) -> int:
    text = _string(args[0], "code_at")
    index = args[1]
    if isinstance(index, bool) or not isinstance(index, int):
        raise TypeMismatch("code_at needs an integer index")
    if not 0 <= index < len(text):
        raise IndexRange(f"the index {index} is outside a string of length {len(text)}")
    return ord(text[index])


def _from_code(args: list[Any]) -> str:
    code = args[0]
    if isinstance(code, bool) or not isinstance(code, int):
        raise TypeMismatch("from_code needs an integer code point")
    if not 0 <= code <= 0x10FFFF:
        raise IndexRange(f"the code point {code} is outside the valid range")
    return chr(code)


def _pad_left(args: list[Any]) -> str:
    text = _string(args[0], "pad_left")
    return _padded(text, args[1], _string(args[2], "pad_left"), "pad_left", left=True)


def _pad_right(args: list[Any]) -> str:
    text = _string(args[0], "pad_right")
    return _padded(text, args[1], _string(args[2], "pad_right"), "pad_right", left=False)


def _padded(text: str, width: Any, filler: str, who: str, left: bool) -> str:
    if isinstance(width, bool) or not isinstance(width, int):
        raise TypeMismatch(f"{who} needs an integer width")
    if len(filler) != 1:
        raise IndexRange(f"{who} needs a single character to pad with")
    if width <= len(text):
        # already wide enough, so nothing is added and nothing is cut away
        return text
    padding = filler * (width - len(text))
    return padding + text if left else text + padding


def _lines(args: list[Any]) -> list[str]:
    return _string(args[0], "lines").splitlines()


def _words(args: list[Any]) -> list[str]:
    return _string(args[0], "words").split()


def _last_index_of(args: list[Any]) -> int:
    return _string(args[0], "last_index_of").rfind(_string(args[1], "last_index_of"))


def _count_of(args: list[Any]) -> int:
    text = _string(args[0], "count_of")
    needle = _string(args[1], "count_of")
    if needle == "":
        raise IndexRange("count_of needs a non-empty string to look for")
    return text.count(needle)


def _reverse_text(args: list[Any]) -> str:
    return _string(args[0], "reverse_text")[::-1]


def _is_blank(args: list[Any]) -> bool:
    return _string(args[0], "is_blank").strip() == ""


_REGISTRY: dict[str, tuple[int, Any]] = {
    "pad_left": (3, _pad_left),
    "pad_right": (3, _pad_right),
    "lines": (1, _lines),
    "words": (1, _words),
    "last_index_of": (2, _last_index_of),
    "count_of": (2, _count_of),
    "reverse_text": (1, _reverse_text),
    "is_blank": (1, _is_blank),
    "upper": (1, _upper),
    "lower": (1, _lower),
    "trim": (1, _trim),
    "split": (2, _split),
    "join": (2, _join),
    "replace": (3, _replace),
    "starts_with": (2, _starts_with),
    "ends_with": (2, _ends_with),
    "index_of": (2, _index_of),
    "substring": (3, _substring),
    "repeat": (2, _repeat),
    "chars": (1, _chars),
    "code_at": (2, _code_at),
    "from_code": (1, _from_code),
}


def install_string_library(machine: Any) -> None:
    for name, (arity, handler) in _REGISTRY.items():
        machine.define_native(name, arity, handler)


def string_names() -> list[str]:
    return sorted(_REGISTRY)
