"""Charts made of text, because text is the only output this language has.

A program whose only way of showing anything is printing lines still needs to show the shape
of its data, and a column of numbers does not show a shape. These functions draw with
characters: a bar chart of rows, a histogram of counts in buckets, a sparkline of one line,
and a table with aligned columns. None of them is a substitute for a real plot, and each is
substantially better than the numbers alone at the one job of making an outlier or a trend
visible at a glance.

The scaling decisions are the whole content. A bar chart scales to the largest value, so the
longest bar fills the width and everything else is proportional to it, which shows relative
size well and absolute size not at all: two charts drawn separately cannot be compared, and
that is worth knowing before comparing them. The baseline is zero rather than the smallest
value, because starting at the smallest exaggerates differences, which is the most common way
a chart misleads, and a caller who wants that can subtract first and know they did.

Negative values are refused by the bar chart rather than drawn. A bar of negative length has
no obvious meaning, and the alternatives, drawing leftwards from a centre line or drawing the
absolute value, are different pictures that a caller should choose between explicitly. The
histogram accepts them, because a bucket is a range and a range can be negative.

All of it is drawn in ASCII, which was a correction rather than a plan: the block
drawing characters make a far better looking bar and the first attempt to print one
raised an encoding error from the console before any chart appeared. A library cannot
know what its caller's terminal can render, and a chart that fails to print is worth
less than an uglier one that does, so the characters chosen are the ones that work
everywhere.

Rounding is where a chart lies quietly. A value scaled to a width has a fractional part, and
truncating it makes small values vanish while rounding up makes zero look like something. The
choice here is to round to nearest but never to round a value above zero down to nothing: a
value present in the data always draws at least one character, so a reader can never mistake
something small for nothing at all. The cost is that the shortest bars are all one character
long whatever their values, and that trade is worth the honesty about presence.
"""

from __future__ import annotations

from typing import Any

from ember.errors import Arithmetic, TypeMismatch
from ember.valueops import stringify, type_name

# Everything here draws in plain ASCII. The first version used the block drawing
# characters, which look better and failed immediately: printing one to a console
# using a Western code page raised an encoding error before the chart appeared. A
# chart that cannot be printed where it is used is not a chart, and a library cannot
# know what its caller's console can render, so the characters that work everywhere
# are the ones worth having.
_FULL = "#"
_SPARKS = ("_", ".", ",", "-", "=", "+", "*", "^")
_DEFAULT_WIDTH = 40


def _numbers(value: Any, who: str) -> list[float]:
    if not isinstance(value, list):
        raise TypeMismatch(f"{who} needs a list, not a {type_name(value)}")
    found: list[float] = []
    for entry in value:
        if isinstance(entry, bool) or not isinstance(entry, (int, float)):
            raise TypeMismatch(f"{who} needs numbers, and found a {type_name(entry)}")
        found.append(entry)
    return found


def _texts(value: Any, who: str) -> list[str]:
    if not isinstance(value, list):
        raise TypeMismatch(f"{who} needs a list, not a {type_name(value)}")
    return [entry if isinstance(entry, str) else stringify(entry) for entry in value]


def _width(value: Any, who: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeMismatch(f"{who} needs a whole number width, not a {type_name(value)}")
    if value < 1:
        raise Arithmetic(f"{who} needs a width of at least one, not {value}")
    return value


def _scaled_length(value: float, largest: float, width: int) -> int:
    """How many characters a value draws, never nothing when the value is not nothing."""
    if largest <= 0:
        return 0
    length = round(value / largest * width)
    if value > 0 and length == 0:
        # a value present in the data always draws, so small is never mistaken for none
        return 1
    return length


def _bars(args: list[Any]) -> list[str]:
    values = _numbers(args[0], "barChart")
    width = _width(args[1], "barChart")
    if any(value < 0 for value in values):
        raise Arithmetic(
            "barChart has no meaning for a negative value, because a bar of negative "
            "length is a different picture; take the absolute value or shift the data "
            "and say which you meant"
        )
    if not values:
        return []
    largest = max(values)
    return [_FULL * _scaled_length(value, largest, width) for value in values]


def _labelled_bars(args: list[Any]) -> list[str]:
    """A bar chart with its labels aligned, which is what a reader actually wants."""
    labels = _texts(args[0], "labelledBars")
    values = _numbers(args[1], "labelledBars")
    width = _width(args[2], "labelledBars")
    if len(labels) != len(values):
        raise Arithmetic(
            f"labelledBars was given {len(labels)} labels and {len(values)} values, "
            "and it needs one label for each value"
        )
    drawn = _bars([values, width])
    widest = max((len(label) for label in labels), default=0)
    return [
        f"{label.ljust(widest)}  {bar} {stringify(value)}"
        for label, bar, value in zip(labels, drawn, values, strict=True)
    ]


def _histogram(args: list[Any]) -> list[int]:
    """How many values fall into each of a number of equal buckets."""
    values = _numbers(args[0], "histogram")
    buckets = args[1]
    if isinstance(buckets, bool) or not isinstance(buckets, int):
        raise TypeMismatch(
            f"histogram needs a whole number of buckets, not a {type_name(buckets)}"
        )
    if buckets < 1:
        raise Arithmetic(f"histogram needs at least one bucket, not {buckets}")
    if not values:
        return [0] * buckets
    lowest = min(values)
    highest = max(values)
    if lowest == highest:
        # every value is the same, so they all belong to the first bucket rather than
        # the division by a span of zero being attempted
        return [len(values)] + [0] * (buckets - 1)
    span = highest - lowest
    tally = [0] * buckets
    for value in values:
        where = int((value - lowest) / span * buckets)
        tally[min(where, buckets - 1)] += 1
    return tally


def _histogram_lines(args: list[Any]) -> list[str]:
    counts = _histogram(args)
    width = _width(args[2], "histogramLines") if len(args) > 2 else _DEFAULT_WIDTH
    return _bars([counts, width])


def _sparkline(args: list[Any]) -> str:
    """One line of eight heights, which fits a trend into a single string."""
    values = _numbers(args[0], "sparkline")
    if not values:
        return ""
    lowest = min(values)
    highest = max(values)
    if lowest == highest:
        return _SPARKS[0] * len(values)
    span = highest - lowest
    pieces: list[str] = []
    for value in values:
        step = int((value - lowest) / span * (len(_SPARKS) - 1) + 0.5)
        pieces.append(_SPARKS[min(step, len(_SPARKS) - 1)])
    return "".join(pieces)


def _table(args: list[Any]) -> list[str]:
    """Rows with every column as wide as its widest entry."""
    rows = args[0]
    if not isinstance(rows, list):
        raise TypeMismatch(f"table needs a list of rows, not a {type_name(rows)}")
    shaped: list[list[str]] = []
    for row in rows:
        if not isinstance(row, list):
            raise TypeMismatch(f"table needs each row to be a list, not a {type_name(row)}")
        shaped.append([entry if isinstance(entry, str) else stringify(entry) for entry in row])
    if not shaped:
        return []
    columns = max(len(row) for row in shaped)
    widths = [
        max((len(row[at]) for row in shaped if at < len(row)), default=0)
        for at in range(columns)
    ]
    lines: list[str] = []
    for row in shaped:
        pieces = [
            (row[at] if at < len(row) else "").ljust(widths[at]) for at in range(columns)
        ]
        lines.append("  ".join(pieces).rstrip())
    return lines


def _axis(args: list[Any]) -> str:
    """A ruler under a chart, marked at its ends, so a width means something."""
    width = _width(args[0], "axis")
    lowest = args[1]
    highest = args[2]
    left = stringify(lowest)
    right = stringify(highest)
    if len(left) + len(right) + 1 > width:
        return left + " " + right
    return left + "-" * (width - len(left) - len(right)) + right


def _percentage_bars(args: list[Any]) -> list[str]:
    """Bars scaled to a hundred rather than to the largest, so charts compare."""
    values = _numbers(args[0], "percentageBars")
    width = _width(args[1], "percentageBars")
    if any(value < 0 for value in values):
        raise Arithmetic("percentageBars has no meaning for a negative value")
    return [_FULL * _scaled_length(value, 100, width) for value in values]


_REGISTRY: dict[str, tuple[int, Any]] = {
    "barChart": (2, _bars),
    "labelledBars": (3, _labelled_bars),
    "histogram": (2, _histogram),
    "histogramLines": (3, _histogram_lines),
    "sparkline": (1, _sparkline),
    "table": (1, _table),
    "axis": (3, _axis),
    "percentageBars": (2, _percentage_bars),
}


def install_chart_library(machine: Any) -> None:
    for name, (arity, handler) in _REGISTRY.items():
        machine.define_native(name, arity, handler)


def chart_names() -> list[str]:
    return sorted(_REGISTRY)
