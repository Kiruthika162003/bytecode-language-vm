"""Number parsing: read a numeric literal's text into the integer or float it denotes.

The scanner recognizes the shape of a number, a run of digits with
optional decoration, but the shape is not the value, and turning the
text into a value has enough rules to deserve its own module. Ember
distinguishes integers from floats by their spelling: a literal with a
decimal point or an exponent is a float, and one without is an integer,
so the scanner can tell the two apart without the parser's help and the
value carries the right type from the start. Integers may be written in
decimal or, with a prefix, in hexadecimal, octal, or binary, which lets
bit patterns be written the way they are reasoned about. Underscores are
permitted between digits as visual separators and are stripped before
conversion, so a long constant can be grouped for reading without
changing its value. The honest edge cases are what this module refuses:
a prefix with no digits after it, an underscore at either end or doubled,
and a radix prefix combined with a decimal point, none of which denote a
clear number, are all rejected with a message naming the text. It
returns the decoded value and a flag saying whether the literal was a
float, so the caller need not inspect the spelling a second time.
"""

from __future__ import annotations

from ember.errors import Syntax

_RADIX = {"x": 16, "o": 8, "b": 2}
_DIGITS = {
    16: "0123456789abcdefABCDEF",
    8: "01234567",
    2: "01",
}


def _strip_underscores(text: str) -> str:
    if text.startswith("_") or text.endswith("_") or "__" in text:
        raise Syntax(
            f"the number {text!r} has a misplaced underscore; underscores may "
            "only separate digits"
        )
    return text.replace("_", "")


def parse(text: str) -> tuple[int | float, bool]:
    if text == "":
        raise Syntax("an empty string is not a number")
    if len(text) >= 2 and text[0] == "0" and text[1] in _RADIX:
        radix = _RADIX[text[1]]
        body = _strip_underscores(text[2:])
        if body == "":
            raise Syntax(
                f"the literal {text!r} has a base prefix but no digits; write "
                "the digits after the prefix"
            )
        allowed = _DIGITS[radix]
        for char in body:
            if char not in allowed:
                raise Syntax(
                    f"the digit {char!r} is not valid in the literal {text!r} "
                    f"for base {radix}"
                )
        return int(body, radix), False
    body = _strip_underscores(text)
    is_float = "." in body or "e" in body or "E" in body
    try:
        if is_float:
            return float(body), True
        return int(body), False
    except ValueError as exc:
        raise Syntax(f"the text {text!r} is not a valid number") from exc
