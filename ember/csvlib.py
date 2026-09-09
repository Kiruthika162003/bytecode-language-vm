"""Comma separated values: a format with no specification, handled one way deliberately.

CSV has no standard that everything follows, which means writing a reader for it is
mostly a series of decisions about what to do with text that several tools would read
differently. Making those decisions explicitly, and writing down which way each went, is
the only honest way to handle the format, because a reader that silently guesses will
guess differently from the tool that wrote the file and the difference will surface as
data that is subtly wrong rather than as an error.

The decisions. A field is quoted when it contains a comma, a quote, or a newline, and
otherwise is not, because quoting everything makes files larger and harder to read while
quoting nothing loses data. A quote inside a quoted field is written as two quotes, which
is the convention nearly every tool follows. Whitespace around a field is kept, because
trimming it would make a field of two spaces indistinguishable from an empty one, and a
program that wants it trimmed has a function for that. An empty field reads as an empty
string rather than as nil, because the format cannot tell the two apart: a line reading
a,,b has a middle field that is present and empty, and there is no way to write an absent
one, so pretending otherwise would invent information. Rows of differing lengths are
returned as they are rather than padded, because padding invents empty fields that were
not in the file, and a caller who wants a rectangle can ask for one.

One ambiguity in the format cannot be decided, only worked around, and finding it took
a round trip test. A document holding one row with one empty field is written as empty
text, and empty text is also how a document with no rows at all is written, so reading
either back gives no rows and one of the two documents is lost. There is no reading of
empty text that is right for both. Writing that one case as a pair of quotes keeps the
two apart, which is why the writer quotes a field that needs no quoting in exactly this
situation, and the round trip is then exact for every document tested.

Everything is read as a string, and no attempt is made to recognise a number. This is the
decision that most often surprises, and it is the one most worth keeping. Guessing types
from text is where CSV handling goes wrong in practice: a field reading 007 becomes seven
and loses its shape, a version number becomes a decimal, a long digit string becomes a
float and loses its last digits. A caller who knows a column holds numbers converts it,
which is one call, and knows it happened.
"""

from __future__ import annotations

from typing import Any

from ember.errors import Arithmetic, TypeMismatch
from ember.valueops import type_name

_QUOTE = chr(34)
_COMMA = ","
_NEWLINE = chr(10)
_RETURN = chr(13)
_NEEDS_QUOTING = (_COMMA, _QUOTE, _NEWLINE, _RETURN)


def _text(value: Any, who: str) -> str:
    if not isinstance(value, str):
        raise TypeMismatch(f"{who} needs a string, not a {type_name(value)}")
    return value


def _rows_of(value: Any, who: str) -> list[list[str]]:
    if not isinstance(value, list):
        raise TypeMismatch(f"{who} needs a list of rows, not a {type_name(value)}")
    rows: list[list[str]] = []
    for row in value:
        if not isinstance(row, list):
            raise TypeMismatch(
                f"{who} needs each row to be a list of fields, but found a {type_name(row)}"
            )
        rows.append([_field_text(field, who) for field in row])
    return rows


def _field_text(value: Any, who: str) -> str:
    """A field is written as text, and anything but text has to be converted first."""
    if isinstance(value, str):
        return value
    raise TypeMismatch(
        f"{who} writes strings, and this field is a {type_name(value)}; convert it "
        "with str first, so the conversion is something the program chose"
    )


def quote_field(field: str) -> str:
    """Quote a field only when it needs it, doubling any quote inside."""
    if any(character in field for character in _NEEDS_QUOTING):
        return _QUOTE + field.replace(_QUOTE, _QUOTE + _QUOTE) + _QUOTE
    return field


def parse_rows(text: str) -> list[list[str]]:
    """Read a whole document, following quotes across newlines."""
    rows: list[list[str]] = []
    row: list[str] = []
    field: list[str] = []
    inside = False
    at = 0
    started = False
    while at < len(text):
        character = text[at]
        if inside:
            if character == _QUOTE:
                if at + 1 < len(text) and text[at + 1] == _QUOTE:
                    # two quotes inside a quoted field mean one quote
                    field.append(_QUOTE)
                    at += 2
                    continue
                inside = False
                at += 1
                continue
            field.append(character)
            at += 1
            continue
        if character == _QUOTE:
            inside = True
            started = True
            at += 1
            continue
        if character == _COMMA:
            row.append("".join(field))
            field = []
            started = True
            at += 1
            continue
        if character in (_NEWLINE, _RETURN):
            if character == _RETURN and at + 1 < len(text) and text[at + 1] == _NEWLINE:
                at += 1
            row.append("".join(field))
            rows.append(row)
            row = []
            field = []
            started = False
            at += 1
            continue
        field.append(character)
        started = True
        at += 1
    if inside:
        raise Arithmetic(
            "a quoted field was opened and never closed, so the rest of the document "
            "was read as part of it; check for an unmatched quote"
        )
    if field or row or started:
        row.append("".join(field))
        rows.append(row)
    return rows


def _from_csv(args: list[Any]) -> list[list[str]]:
    return parse_rows(_text(args[0], "fromCsv"))


def _to_csv(args: list[Any]) -> str:
    rows = _rows_of(args[0], "toCsv")
    if rows == [[""]]:
        # One row holding one empty field would otherwise be written as empty text,
        # and empty text reads back as no rows at all, so the two documents would be
        # indistinguishable. A round trip that loses a row is worse than a pair of
        # quotes nothing else needs, so this one case is quoted to keep them apart.
        return _QUOTE + _QUOTE
    return _NEWLINE.join(_COMMA.join(quote_field(field) for field in row) for row in rows)


def _parse_line(args: list[Any]) -> list[str]:
    text = _text(args[0], "csvLine")
    rows = parse_rows(text)
    if len(rows) > 1:
        raise Arithmetic(
            f"csvLine reads one row, and this text holds {len(rows)}; use fromCsv "
            "for a whole document"
        )
    return rows[0] if rows else []


def _format_line(args: list[Any]) -> str:
    row = args[0]
    if not isinstance(row, list):
        raise TypeMismatch(f"csvFormatLine needs a list of fields, not a {type_name(row)}")
    return _COMMA.join(quote_field(_field_text(field, "csvFormatLine")) for field in row)


def _widths(args: list[Any]) -> list[int]:
    return [len(row) for row in _rows_of(args[0], "csvWidths")]


def _is_rectangular(args: list[Any]) -> bool:
    rows = _rows_of(args[0], "csvRectangular")
    return len({len(row) for row in rows}) <= 1


def _padded(args: list[Any]) -> list[list[str]]:
    """Every row made the same width, which invents fields and so is asked for."""
    rows = _rows_of(args[0], "csvPadded")
    if not rows:
        return []
    widest = max(len(row) for row in rows)
    return [row + [""] * (widest - len(row)) for row in rows]


def _column(args: list[Any]) -> list[str]:
    rows = _rows_of(args[0], "csvColumn")
    at = args[1]
    if isinstance(at, bool) or not isinstance(at, int):
        raise TypeMismatch(f"csvColumn needs a whole number index, not a {type_name(at)}")
    if at < 0:
        raise Arithmetic(f"csvColumn counts columns from zero, so {at} has no meaning")
    found: list[str] = []
    for number, row in enumerate(rows, start=1):
        if at >= len(row):
            raise Arithmetic(
                f"csvColumn was asked for column {at}, and row {number} has only "
                f"{len(row)} fields; the document is not rectangular"
            )
        found.append(row[at])
    return found


def _with_header(args: list[Any]) -> list[dict[str, str]]:
    """Each row as a map keyed by the first row, which is how a header is usually meant."""
    rows = _rows_of(args[0], "csvWithHeader")
    if not rows:
        return []
    header = rows[0]
    if len(set(header)) != len(header):
        raise Arithmetic(
            "the header names a column twice, so a row keyed by it would lose a field"
        )
    found: list[dict[str, str]] = []
    for number, row in enumerate(rows[1:], start=2):
        if len(row) != len(header):
            raise Arithmetic(
                f"row {number} has {len(row)} fields and the header names "
                f"{len(header)}, so they cannot be paired"
            )
        found.append(dict(zip(header, row, strict=True)))
    return found


_REGISTRY: dict[str, tuple[int, Any]] = {
    "fromCsv": (1, _from_csv),
    "toCsv": (1, _to_csv),
    "csvLine": (1, _parse_line),
    "csvFormatLine": (1, _format_line),
    "csvWidths": (1, _widths),
    "csvRectangular": (1, _is_rectangular),
    "csvPadded": (1, _padded),
    "csvColumn": (2, _column),
    "csvWithHeader": (1, _with_header),
}


def install_csv_library(machine: Any) -> None:
    for name, (arity, handler) in _REGISTRY.items():
        machine.define_native(name, arity, handler)


def csv_names() -> list[str]:
    return sorted(_REGISTRY)
