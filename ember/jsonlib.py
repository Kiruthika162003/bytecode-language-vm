"""The JSON library: a data format written and read without the host's help.

JSON is implemented here rather than delegated to the host's parser, and the reason
is the mapping between the two value systems, which is where every subtle bug in a
JSON binding lives. Doing the parse by hand makes each decision explicit instead of
inheriting whatever the host happened to choose.

Four decisions matter. JSON has one number type and this language has two, so a
number is read as an integer when it is written without a fractional part or an
exponent and as a float otherwise, which means the text one comes back as an integer
and the text one point zero comes back as a float. That is faithful to what was
written rather than to what the value is worth, and it is the choice that keeps
round-tripping stable. JSON object keys are always strings, so a map with a number
key cannot be written and is refused rather than quietly stringified, because a
program that wrote a numeric key and read back a string one has silently lost
information. Encoding refuses anything the format cannot represent, a function or a
class instance, naming the type rather than emitting null, since null is a value JSON
already has and using it for something absent would make the two indistinguishable
on the way back. And decoding is strict: trailing commas, unquoted keys, and single
quotes are all refused, because a lenient parser accepts documents that other tools
will reject, which turns a problem that would have surfaced immediately into one that
surfaces somewhere else entirely.

The one deliberate looseness is depth. Parsing is recursive, so a document nested
thousands of levels deep would exhaust the host's stack rather than being refused
cleanly, and rather than pretend otherwise there is an explicit depth limit that
refuses in the language's own voice before the host's own limit is reached.
"""

from __future__ import annotations

from typing import Any

from ember.errors import Arithmetic, TypeMismatch
from ember.valueops import type_name

_DEPTH_LIMIT = 100
_ESCAPES = {
    '"': '"',
    "\\": "\\",
    "/": "/",
    "b": chr(8),
    "f": chr(12),
    "n": chr(10),
    "r": chr(13),
    "t": chr(9),
}
_REVERSED = {
    '"': '\\"',
    "\\": "\\\\",
    chr(8): "\\b",
    chr(12): "\\f",
    chr(10): "\\n",
    chr(13): "\\r",
    chr(9): "\\t",
}


def _escaped(text: str) -> str:
    pieces: list[str] = []
    for character in text:
        if character in _REVERSED:
            pieces.append(_REVERSED[character])
        elif ord(character) < 32:
            pieces.append("\\u" + format(ord(character), "04x"))
        else:
            pieces.append(character)
    return '"' + "".join(pieces) + '"'


def encode_value(value: Any, depth: int = 0) -> str:
    """Turn an Ember value into JSON text, refusing what the format cannot hold."""
    if depth > _DEPTH_LIMIT:
        raise Arithmetic(
            f"toJson gave up at {_DEPTH_LIMIT} levels of nesting; the value is "
            "either far deeper than intended or refers to itself"
        )
    if value is None:
        return "null"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        # a whole float keeps its point, so what was written comes back the same
        return repr(value)
    if isinstance(value, str):
        return _escaped(value)
    if isinstance(value, list):
        return "[" + ",".join(encode_value(entry, depth + 1) for entry in value) + "]"
    if isinstance(value, dict):
        pieces = []
        for key, held in value.items():
            if not isinstance(key, str):
                raise TypeMismatch(
                    f"toJson needs string keys, but this map has a key of type "
                    f"{type_name(key)}; JSON objects have no other kind"
                )
            pieces.append(_escaped(key) + ":" + encode_value(held, depth + 1))
        return "{" + ",".join(pieces) + "}"
    raise TypeMismatch(
        f"toJson has no representation for a {type_name(value)}; JSON holds numbers, "
        "strings, booleans, nil, lists and maps"
    )


class _Reader:
    """A strict recursive descent reader over JSON text."""

    def __init__(self, text: str) -> None:
        self._text = text
        self._at = 0

    def _fault(self, what: str) -> Arithmetic:
        return Arithmetic(f"fromJson found {what} at position {self._at}")

    def _skip_space(self) -> None:
        while self._at < len(self._text) and self._text[self._at] in " \t\r\n":
            self._at += 1

    def _peek(self) -> str:
        return self._text[self._at] if self._at < len(self._text) else ""

    def _take(self, expected: str) -> None:
        if self._peek() != expected:
            raise self._fault(f"{self._peek()!r} where {expected!r} was needed")
        self._at += 1

    def _word(self, word: str, value: Any) -> Any:
        if not self._text.startswith(word, self._at):
            raise self._fault(f"something that is not {word}")
        self._at += len(word)
        return value

    def _string(self) -> str:
        self._take('"')
        pieces: list[str] = []
        while True:
            if self._at >= len(self._text):
                raise self._fault("the end of the text inside a string")
            character = self._text[self._at]
            if character == '"':
                self._at += 1
                return "".join(pieces)
            if character == "\\":
                self._at += 1
                marker = self._peek()
                if marker in _ESCAPES:
                    pieces.append(_ESCAPES[marker])
                    self._at += 1
                elif marker == "u":
                    digits = self._text[self._at + 1 : self._at + 5]
                    if len(digits) != 4:
                        raise self._fault("a short unicode escape")
                    try:
                        pieces.append(chr(int(digits, 16)))
                    except ValueError as bad:
                        raise self._fault("an unreadable unicode escape") from bad
                    self._at += 5
                else:
                    raise self._fault(f"the unknown escape {marker!r}")
            else:
                pieces.append(character)
                self._at += 1

    def _number(self) -> Any:
        start = self._at
        if self._peek() == "-":
            self._at += 1
        while self._peek().isdigit():
            self._at += 1
        whole = True
        if self._peek() == ".":
            whole = False
            self._at += 1
            while self._peek().isdigit():
                self._at += 1
        if self._peek() in ("e", "E"):
            whole = False
            self._at += 1
            if self._peek() in ("+", "-"):
                self._at += 1
            while self._peek().isdigit():
                self._at += 1
        text = self._text[start : self._at]
        if not text or text in ("-", "."):
            raise self._fault("something that is not a number")
        try:
            # written without a point or exponent means an integer, faithful to the text
            return int(text) if whole else float(text)
        except ValueError as bad:
            raise self._fault(f"the unreadable number {text!r}") from bad

    def _list(self, depth: int) -> list[Any]:
        self._take("[")
        self._skip_space()
        found: list[Any] = []
        if self._peek() == "]":
            self._at += 1
            return found
        while True:
            found.append(self.value(depth + 1))
            self._skip_space()
            if self._peek() == ",":
                self._at += 1
                self._skip_space()
                if self._peek() == "]":
                    # strict: a trailing comma is a document other tools will reject
                    raise self._fault("a trailing comma before a closing bracket")
                continue
            self._take("]")
            return found

    def _map(self, depth: int) -> dict[str, Any]:
        self._take("{")
        self._skip_space()
        found: dict[str, Any] = {}
        if self._peek() == "}":
            self._at += 1
            return found
        while True:
            self._skip_space()
            if self._peek() != '"':
                raise self._fault("an unquoted key")
            key = self._string()
            self._skip_space()
            self._take(":")
            self._skip_space()
            found[key] = self.value(depth + 1)
            self._skip_space()
            if self._peek() == ",":
                self._at += 1
                self._skip_space()
                if self._peek() == "}":
                    raise self._fault("a trailing comma before a closing brace")
                continue
            self._take("}")
            return found

    def value(self, depth: int = 0) -> Any:
        if depth > _DEPTH_LIMIT:
            raise Arithmetic(
                f"fromJson gave up at {_DEPTH_LIMIT} levels of nesting, which is "
                "deeper than any document this language means to read"
            )
        self._skip_space()
        character = self._peek()
        if character == "":
            raise self._fault("the end of the text where a value was needed")
        if character == "{":
            return self._map(depth)
        if character == "[":
            return self._list(depth)
        if character == '"':
            return self._string()
        if character == "t":
            return self._word("true", True)
        if character == "f":
            return self._word("false", False)
        if character == "n":
            return self._word("null", None)
        if character == "-" or character.isdigit():
            return self._number()
        raise self._fault(f"the unexpected character {character!r}")

    def finish(self) -> None:
        self._skip_space()
        if self._at < len(self._text):
            raise self._fault("more text after the value ended")


def decode_text(text: str) -> Any:
    reader = _Reader(text)
    value = reader.value()
    reader.finish()
    return value


def _to_json(args: list[Any]) -> str:
    return encode_value(args[0])


def _from_json(args: list[Any]) -> Any:
    text = args[0]
    if not isinstance(text, str):
        raise TypeMismatch(f"fromJson needs a string, not a {type_name(text)}")
    return decode_text(text)


def _is_json(args: list[Any]) -> bool:
    text = args[0]
    if not isinstance(text, str):
        raise TypeMismatch(f"isJson needs a string, not a {type_name(text)}")
    try:
        decode_text(text)
    except (Arithmetic, TypeMismatch):
        return False
    return True


_REGISTRY: dict[str, tuple[int, Any]] = {
    "toJson": (1, _to_json),
    "fromJson": (1, _from_json),
    "isJson": (1, _is_json),
}


def install_json_library(machine: Any) -> None:
    for name, (arity, handler) in _REGISTRY.items():
        machine.define_native(name, arity, handler)


def json_names() -> list[str]:
    return sorted(_REGISTRY)
