"""String escapes: turn the two-character source spellings into the single characters they mean.

Inside a string literal the source cannot contain a raw newline or a raw
quote, so the language spells those out as escape sequences: a backslash
followed by a letter or a run of hex digits standing for one character.
Decoding these is a small state machine that reads the text left to
right, copying ordinary characters through and, on a backslash, reading
the next character to decide what single character to emit. Keeping this
in its own module rather than inlining it in the scanner has a clear
payoff: the rules for what escapes exist and what they mean are subtle
enough, particularly the hex and unicode forms with their fixed digit
counts, that they deserve their own focused tests, and the scanner can
then treat a string body as a single call. The honest decisions are at
the edges. A backslash before an unrecognized character is an error
rather than being passed through silently, because silently keeping the
backslash hides typos, and a hex or unicode escape with too few digits
or an out-of-range value is an error for the same reason. This module
decodes the body of a string, without its surrounding quotes, and
raises on any malformed escape, naming the offending sequence.
"""

from __future__ import annotations

from ember.errors import Syntax

_SIMPLE = {
    "n": "\n",
    "t": "\t",
    "r": "\r",
    "0": "\0",
    "\\": "\\",
    '"': '"',
    "'": "'",
    "$": "$",
}


def _read_hex(body: str, start: int, count: int, kind: str) -> tuple[int, int]:
    digits = body[start : start + count]
    if len(digits) != count or any(c not in "0123456789abcdefABCDEF" for c in digits):
        raise Syntax(
            f"the {kind} escape needs {count} hex digits but found {digits!r}; "
            "supply the full number of hex digits"
        )
    return int(digits, 16), start + count


def decode(body: str) -> str:
    result: list[str] = []
    index = 0
    length = len(body)
    while index < length:
        char = body[index]
        if char != "\\":
            result.append(char)
            index += 1
            continue
        index += 1
        if index >= length:
            raise Syntax(
                "a string ends with a lone backslash; an escape needs a "
                "character after the backslash"
            )
        marker = body[index]
        index += 1
        if marker in _SIMPLE:
            result.append(_SIMPLE[marker])
        elif marker == "x":
            code, index = _read_hex(body, index, 2, "\\x")
            result.append(chr(code))
        elif marker == "u":
            code, index = _read_hex(body, index, 4, "\\u")
            result.append(chr(code))
        else:
            raise Syntax(
                f"unknown escape sequence \\{marker}; a backslash must be "
                "followed by a known escape character"
            )
    return "".join(result)
