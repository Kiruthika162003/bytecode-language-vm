"""The text library: the string operations a program reaches for when formatting output.

The core string library covers the operations that ask a question about a string or
take it apart. This module covers the other half, the ones that build a string for
someone to read: padding to a width, wrapping to a line length, indenting, casing
for a title, repeating, and reversing. They are separated from the core because they
have a different character. The core operations have one obvious answer, while nearly
every function here embodies a convention that could reasonably be different, and
grouping them makes those conventions visible in one place rather than scattered
through a larger file.

Two functions that belong here by subject are not here, and the reason is worth recording
because it was a bug before it was a decision. Repeating a string and splitting one into lines
were written in this module and were already in the core string library, so installing this one
afterwards silently replaced both. The two versions of splitting into lines were not even the
same: the older one handles a carriage return before a newline and this one did not, so adding
this module quietly changed how every program split text on a file written by another system.
Nothing failed, because both versions pass the obvious tests. The generated reference is what
found it, by noticing that two libraries claimed one name, and a test now pins that count at
zero so the next one cannot go unnoticed.

Two of the conventions are worth naming outright. Padding to a width shorter than the
string returns the string unchanged rather than truncating it, because silently losing
text is worse than a misaligned column, and a caller who wants truncation has slice
for that. Wrapping breaks on spaces and never inside a word, which means a single word
longer than the width overflows its line: the alternative, breaking mid-word, produces
output that is harder to read than a long line, and hyphenating correctly needs a
dictionary this language has no business carrying. Title casing capitalises the first
letter of every space-separated run and lowercases the rest, which is deliberately the
simple rule rather than the typographic one, since the real rule depends on a list of
words that stay lowercase and on the language the text is in, and a library that got
that subtly wrong would be worse than one that is plainly mechanical.
"""

from __future__ import annotations

from typing import Any

from ember.errors import Arithmetic, TypeMismatch
from ember.valueops import type_name

_NEWLINE = chr(10)


def _text(value: Any, who: str) -> str:
    if not isinstance(value, str):
        raise TypeMismatch(f"{who} needs a string, not a {type_name(value)}")
    return value


def _count(value: Any, who: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeMismatch(f"{who} needs a whole number, not a {type_name(value)}")
    if value < 0:
        raise Arithmetic(f"{who} needs a count of zero or more, not {value}")
    return value


def _one_character(value: Any, who: str) -> str:
    filler = _text(value, who)
    if len(filler) != 1:
        raise Arithmetic(
            f"{who} pads with a single character, but was given {len(filler)}; "
            "pass one character to pad with"
        )
    return filler


def _padded(text: str, width: int, filler: str, on_left: bool) -> str:
    if len(text) >= width:
        # never truncate: a misaligned column beats losing text
        return text
    made = filler * (width - len(text))
    return made + text if on_left else text + made


def _pad_left(args: list[Any]) -> str:
    text = _text(args[0], "padLeft")
    return _padded(text, _count(args[1], "padLeft"), " ", on_left=True)


def _pad_right(args: list[Any]) -> str:
    text = _text(args[0], "padRight")
    return _padded(text, _count(args[1], "padRight"), " ", on_left=False)


def _pad_left_with(args: list[Any]) -> str:
    # a native takes a fixed count of arguments, so a chosen filler is its own
    # function rather than an optional third argument
    text = _text(args[0], "padLeftWith")
    filler = _one_character(args[2], "padLeftWith")
    return _padded(text, _count(args[1], "padLeftWith"), filler, on_left=True)


def _pad_right_with(args: list[Any]) -> str:
    text = _text(args[0], "padRightWith")
    filler = _one_character(args[2], "padRightWith")
    return _padded(text, _count(args[1], "padRightWith"), filler, on_left=False)


def _centre(args: list[Any]) -> str:
    text = _text(args[0], "centre")
    width = _count(args[1], "centre")
    if len(text) >= width:
        return text
    spare = width - len(text)
    left = spare // 2
    # an odd remainder goes on the right, which is the usual choice
    return " " * left + text + " " * (spare - left)


def _reversed_text(args: list[Any]) -> str:
    return _text(args[0], "reversedText")[::-1]


def _title(args: list[Any]) -> str:
    text = _text(args[0], "title")
    words = text.split(" ")
    lifted = [word[:1].upper() + word[1:].lower() if word else word for word in words]
    return " ".join(lifted)


def _capitalise(args: list[Any]) -> str:
    text = _text(args[0], "capitalise")
    return text[:1].upper() + text[1:] if text else text


def _swap_case(args: list[Any]) -> str:
    text = _text(args[0], "swapCase")
    return "".join(
        character.lower() if character.isupper() else character.upper() for character in text
    )


def _wrap(args: list[Any]) -> list[str]:
    text = _text(args[0], "wrap")
    width = _count(args[1], "wrap")
    if width == 0:
        raise Arithmetic("wrap needs a width of at least one character")
    lines: list[str] = []
    current = ""
    for word in text.split():
        if not current:
            current = word
        elif len(current) + 1 + len(word) <= width:
            current = current + " " + word
        else:
            lines.append(current)
            current = word
    if current:
        # a word longer than the width overflows rather than being broken
        lines.append(current)
    return lines


def _indent(args: list[Any]) -> str:
    text = _text(args[0], "indent")
    width = _count(args[1], "indent")
    prefix = " " * width
    return _NEWLINE.join(prefix + line if line else line for line in text.split(_NEWLINE))


def _dedent(args: list[Any]) -> str:
    text = _text(args[0], "dedent")
    lines = text.split(_NEWLINE)
    filled = [line for line in lines if line.strip()]
    if not filled:
        return text
    common = min(len(line) - len(line.lstrip(" ")) for line in filled)
    return _NEWLINE.join(line[common:] if line.strip() else line for line in lines)


def _truncate(args: list[Any]) -> str:
    text = _text(args[0], "truncate")
    width = _count(args[1], "truncate")
    if len(text) <= width:
        return text
    if width <= 3:
        # no room for the ellipsis, so the width wins over the marker
        return text[:width]
    return text[: width - 3] + "..."


def _count_of(args: list[Any]) -> int:
    text = _text(args[0], "countOf")
    needle = _text(args[1], "countOf")
    if not needle:
        raise Arithmetic("countOf needs something to look for, but the needle is empty")
    return text.count(needle)


def _unlines(args: list[Any]) -> str:
    value = args[0]
    if not isinstance(value, list):
        raise TypeMismatch(f"unlines needs a list, not a {type_name(value)}")
    return _NEWLINE.join(_text(entry, "unlines") for entry in value)


def _is_blank(args: list[Any]) -> bool:
    return not _text(args[0], "isBlank").strip()


def _squeeze(args: list[Any]) -> str:
    text = _text(args[0], "squeeze")
    return " ".join(text.split())


def _common_prefix(args: list[Any]) -> str:
    left = _text(args[0], "commonPrefix")
    right = _text(args[1], "commonPrefix")
    shared: list[str] = []
    for first, second in zip(left, right, strict=False):
        if first != second:
            break
        shared.append(first)
    return "".join(shared)


_REGISTRY: dict[str, tuple[int, Any]] = {
    "padLeft": (2, _pad_left),
    "padRight": (2, _pad_right),
    "padLeftWith": (3, _pad_left_with),
    "padRightWith": (3, _pad_right_with),
    "centre": (2, _centre),
    "reversedText": (1, _reversed_text),
    "title": (1, _title),
    "capitalise": (1, _capitalise),
    "swapCase": (1, _swap_case),
    "wrap": (2, _wrap),
    "indent": (2, _indent),
    "dedent": (1, _dedent),
    "truncate": (2, _truncate),
    "countOf": (2, _count_of),
    "unlines": (1, _unlines),
    "isBlank": (1, _is_blank),
    "squeeze": (1, _squeeze),
    "commonPrefix": (2, _common_prefix),
}


def install_text_library(machine: Any) -> None:
    for name, (arity, handler) in _REGISTRY.items():
        machine.define_native(name, arity, handler)


def text_names() -> list[str]:
    return sorted(_REGISTRY)
