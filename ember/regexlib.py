"""The pattern library: the regex engine offered to programs as native functions.

The engine lives in its own module, and this one is the boundary between it and the
language. The separation exists because the two have different jobs: the engine decides
what a pattern means, and this decides what a program gets back, and mixing them would put
decisions about return shapes inside a matcher.

The shapes are the substance here. A match returns a list rather than a new type, holding
the matched text, the start, the end, and the list of group captures, so a program can
index it and print it without conversions. A group that took part in no successful branch
comes back as nil, which is the one place nil is the right answer: the group exists in the
pattern and matched nothing, which is different from matching an empty string, and a
program testing an optional group needs to tell those apart.

Patterns are compiled on every call rather than being kept in a cache. That is the slower
choice, and it is deliberate: a cache keyed by pattern text would grow without bound over
a long run, and this language has no way for a program to hold a compiled pattern as a
value, so a cache would be invisible state that only ever grows. The cost is real, and a
program matching in a loop pays it on every iteration.

Every function takes the pattern first and the subject second, consistently, because a
library where the order varies between functions is one whose calls have to be looked up
every time.
"""

from __future__ import annotations

from typing import Any

from ember.errors import Arithmetic, TypeMismatch
from ember.pattern import (
    compile_pattern,
    find_all,
    matches_whole,
    replace_all,
    search,
    split_on,
)
from ember.valueops import type_name


def _text(value: Any, who: str, what: str) -> str:
    if not isinstance(value, str):
        raise TypeMismatch(f"{who} needs a string for the {what}, not a {type_name(value)}")
    return value


def _compiled(value: Any, who: str):
    return compile_pattern(_text(value, who, "pattern"))


def _shape(found: Any) -> list[Any] | None:
    """A match as a list: its text, where it began and ended, and its groups."""
    if found is None:
        return None
    return [found.text, found.start, found.end, list(found.groups)]


def _matches(args: list[Any]) -> bool:
    pattern = _compiled(args[0], "matches")
    return matches_whole(pattern, _text(args[1], "matches", "subject"))


def _found_in(args: list[Any]) -> bool:
    pattern = _compiled(args[0], "foundIn")
    return search(pattern, _text(args[1], "foundIn", "subject")) is not None


def _first_match(args: list[Any]) -> list[Any] | None:
    pattern = _compiled(args[0], "firstMatch")
    return _shape(search(pattern, _text(args[1], "firstMatch", "subject")))


def _all_matches(args: list[Any]) -> list[list[Any]]:
    pattern = _compiled(args[0], "allMatches")
    subject = _text(args[1], "allMatches", "subject")
    return [_shape(one) for one in find_all(pattern, subject)]  # type: ignore[misc]


def _matched_text(args: list[Any]) -> list[str]:
    pattern = _compiled(args[0], "matchedText")
    subject = _text(args[1], "matchedText", "subject")
    return [one.text for one in find_all(pattern, subject)]


def _count_matches(args: list[Any]) -> int:
    pattern = _compiled(args[0], "countMatches")
    subject = _text(args[1], "countMatches", "subject")
    return len(find_all(pattern, subject))


def _replaced(args: list[Any]) -> str:
    pattern = _compiled(args[0], "replaced")
    subject = _text(args[1], "replaced", "subject")
    return replace_all(pattern, subject, _text(args[2], "replaced", "replacement"))


def _split_by(args: list[Any]) -> list[str]:
    pattern = _compiled(args[0], "splitBy")
    return split_on(pattern, _text(args[1], "splitBy", "subject"))


def _groups_of(args: list[Any]) -> list[Any] | None:
    """Just the captures of the first match, which is what a program usually wants."""
    pattern = _compiled(args[0], "groupsOf")
    found = search(pattern, _text(args[1], "groupsOf", "subject"))
    return list(found.groups) if found is not None else None


def _group_count(args: list[Any]) -> int:
    return _compiled(args[0], "groupCount").groups


def _is_valid(args: list[Any]) -> bool:
    try:
        _compiled(args[0], "isValidPattern")
    except Arithmetic:
        return False
    return True


_REGISTRY: dict[str, tuple[int, Any]] = {
    "matches": (2, _matches),
    "foundIn": (2, _found_in),
    "firstMatch": (2, _first_match),
    "allMatches": (2, _all_matches),
    "matchedText": (2, _matched_text),
    "countMatches": (2, _count_matches),
    "replaced": (3, _replaced),
    "splitBy": (2, _split_by),
    "groupsOf": (2, _groups_of),
    "groupCount": (1, _group_count),
    "isValidPattern": (1, _is_valid),
}


def install_regex_library(machine: Any) -> None:
    for name, (arity, handler) in _REGISTRY.items():
        machine.define_native(name, arity, handler)


def regex_names() -> list[str]:
    return sorted(_REGISTRY)
