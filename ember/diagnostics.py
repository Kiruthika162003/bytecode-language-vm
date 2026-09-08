"""Diagnostics: show the offending line and point at it, rather than only describing it.

An error message that names what went wrong still leaves the reader
hunting for where, and the difference between a good and a bad runtime is
often only how quickly it can be found. This module turns a position into
something a person can read: the source line itself, numbered, with a
caret on the line beneath sitting under the exact column. That layout is
chosen because it survives being copied into a plain-text log, unlike
colour or terminal cursor tricks, and because the caret under the column
is unambiguous where a column number in prose is not. Surrounding lines
can be included when the mistake only makes sense in context, and are left
out by default, since one line and a caret is usually the whole story and
extra lines dilute it. The one subtlety worth stating is what a column
means here: it counts code points from one, matching the cursor that
produced it, so a tab occupies a single column even though a terminal will
render it wider, and a caret after a tab can therefore appear misaligned.
Expanding tabs to align the caret would fix the common case and break
whenever the reader's tab width differs from the one assumed, so this
module counts characters honestly and leaves the rendering to whatever
displays it. It also formats a call stack, innermost frame first, because
a fault deep inside three nested calls is usually explained by who called
what rather than by the failing line alone.
"""

from __future__ import annotations

from ember.errors import EmberError

_CARET = "^"
_GUTTER = " | "


def line_text(source: str, line: int) -> str:
    if line < 1:
        raise EmberError(f"source lines are numbered from one, but got {line}")
    lines = source.splitlines()
    if line > len(lines):
        raise EmberError(
            f"the source has {len(lines)} lines, so line {line} does not exist"
        )
    return lines[line - 1]


def excerpt(source: str, line: int, column: int | None = None, context: int = 0) -> str:
    lines = source.splitlines()
    if line < 1 or line > len(lines):
        raise EmberError(
            f"cannot show line {line} of a source with {len(lines)} lines"
        )
    if context < 0:
        raise EmberError(f"the context count cannot be negative, but got {context}")
    first = max(1, line - context)
    last = min(len(lines), line + context)
    width = len(str(last))
    out: list[str] = []
    for number in range(first, last + 1):
        out.append(f"{number:>{width}}{_GUTTER}{lines[number - 1]}")
        if number == line and column is not None:
            if column < 1:
                raise EmberError(
                    f"source columns are numbered from one, but got {column}"
                )
            pad = " " * (width + len(_GUTTER) + column - 1)
            out.append(f"{pad}{_CARET}")
    return "\n".join(out)


def format_frame(name: str, line: int) -> str:
    label = name if name else "script"
    return f"  in {label} at line {line}"


def format_call_stack(frames: list[tuple[str, int]]) -> str:
    # innermost first, because the frame that faulted is the one being read
    return "\n".join(format_frame(name, line) for name, line in frames)


def describe(source: str, message: str, line: int, column: int | None = None) -> str:
    return f"{message}\n{excerpt(source, line, column)}"
