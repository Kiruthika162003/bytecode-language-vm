"""Tables: relational operations over a list of maps, which is the shape data arrives in.

Every other library here works on one value at a time. This one works on the shape that
data actually has when it comes from a file or a request: a list of maps, each map a row,
the keys the column names. The comma separated values library already produces exactly
that, and until now a program that read a file could only walk it with a loop, which is
how selecting three columns out of twelve ends up written eleven different ways in one
codebase. These are the operations that loop is almost always spelling out.

The choice that shapes everything else is that a table is not a type. It is a list of
maps, checked when a function receives one and never wrapped, so a table read from a file
prints, serialises to json, indexes, and passes to the list library without conversion. The
cost is that every call revalidates, which is real work proportional to the table on
operations that would otherwise be constant, and the benefit is that there is no
conversion to forget and no second representation to keep in step. For tables of the size
a program written in this language will handle, that is the right side of the trade.

Rows are not required to agree about their columns, which is a deliberate decision and
the one most likely to surprise. Real data has gaps: a column absent from a row is
different from a column present and empty, and forcing every row to carry every key would
invent values that were never there. So the column list is the union across rows, a row
missing a column is left missing rather than filled, and any function that must have a
value for a column says which row and which column when it does not find one. Aggregation
skips rows that lack the column rather than treating them as zero, because a mean over
three of five rows is a mean over three rows and calling it a mean over five is a lie the
caller cannot see.

Ordering is stable and total, which needed a decision that measurement forced. Sorting a
column whose values are a mix of numbers and strings raised a host error the first time it
was tried, because comparing them is undefined, and the choice was between refusing the
sort and defining an order. Refusing is what this does: a column has to be comparable
within itself, and mixing kinds in one column is a fault in the data worth reporting
rather than resolving by an arbitrary rule about which kind sorts first. Within one kind,
ties keep the order the rows arrived in, so sorting by one column and then another leaves
the second sort's grouping intact.

The join here is an inner equi-join on one column, with the left join beside it, and
nothing more. A join on several columns, an outer join, and a cross product are all
absent, not because they are hard but because each needs a decision about what happens to
colliding column names, and the answer this one gives, that the right side wins a
collision and the key column appears once, is only obviously right for the simple case.
"""

from __future__ import annotations

from typing import Any

from ember.errors import Arithmetic, IndexRange, TypeMismatch
from ember.valueops import type_name

_ORDERED = (int, float, str)


class _Missing:
    """A value nothing in the language can equal, so an absent column matches nothing."""


_MISSING = _Missing()


def _rows(value: Any, who: str) -> list[dict[Any, Any]]:
    """A table, which is a list of maps, checked on the way in and never wrapped."""
    if not isinstance(value, list):
        raise TypeMismatch(
            f"{who} needs a table, which is a list of maps, not a {type_name(value)}"
        )
    for index, row in enumerate(value):
        if not isinstance(row, dict):
            raise TypeMismatch(
                f"{who} needs every row to be a map, and row {index} is a "
                f"{type_name(row)}"
            )
    return value


def _column(value: Any, who: str) -> str:
    if not isinstance(value, str):
        raise TypeMismatch(
            f"{who} needs a column name as text, not a {type_name(value)}"
        )
    return value


def _names(value: Any, who: str) -> list[str]:
    if not isinstance(value, list):
        raise TypeMismatch(
            f"{who} needs a list of column names, not a {type_name(value)}"
        )
    return [_column(name, who) for name in value]


def _whole(value: Any, who: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeMismatch(f"{who} needs a whole number, not a {type_name(value)}")
    return value


def _cell(row: dict[Any, Any], column: str, index: int, who: str) -> Any:
    if column not in row:
        raise IndexRange(
            f"{who} needs the column {column!r}, and row {index} does not have it; "
            f"that row has {_listed(sorted(str(key) for key in row))}"
        )
    return row[column]


def _listed(names: list[str]) -> str:
    if not names:
        return "no columns"
    return ", ".join(names)


def _number(value: Any, column: str, index: int, who: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeMismatch(
            f"{who} needs numbers in the column {column!r}, and row {index} holds a "
            f"{type_name(value)}"
        )
    return value


def _sortable(values: list[Any], column: str, who: str) -> None:
    """Refuse a column that mixes kinds, because comparing them has no defined answer."""
    kinds = set()
    for index, value in enumerate(values):
        if isinstance(value, bool) or not isinstance(value, _ORDERED):
            raise TypeMismatch(
                f"{who} cannot order the column {column!r}, because row {index} holds "
                f"a {type_name(value)} and only numbers and text have an order"
            )
        kinds.add(str if isinstance(value, str) else float)
    if len(kinds) > 1:
        # this raised a host error the first time it was tried; refusing is the answer,
        # because any rule about which kind sorts first would be arbitrary
        raise TypeMismatch(
            f"{who} cannot order the column {column!r}, because it mixes numbers and "
            "text and there is no order between them; make the column one kind"
        )


def _columns(args: list[Any]) -> list[str]:
    """Every column any row has, which is the union rather than the intersection."""
    rows = _rows(args[0], "columns")
    found: list[str] = []
    for row in rows:
        for key in row:
            name = str(key)
            if name not in found:
                found.append(name)
    return sorted(found)


def _select(args: list[Any]) -> list[dict[str, Any]]:
    """Keep the named columns, dropping the rest, and leave a missing one missing."""
    rows = _rows(args[0], "select")
    wanted = _names(args[1], "select")
    return [{name: row[name] for name in wanted if name in row} for row in rows]


def _drop_column(args: list[Any]) -> list[dict[Any, Any]]:
    rows = _rows(args[0], "dropColumn")
    unwanted = _column(args[1], "dropColumn")
    return [
        {key: value for key, value in row.items() if key != unwanted} for row in rows
    ]


def _rename_column(args: list[Any]) -> list[dict[Any, Any]]:
    rows = _rows(args[0], "renameColumn")
    before = _column(args[1], "renameColumn")
    after = _column(args[2], "renameColumn")
    renamed: list[dict[Any, Any]] = []
    for row in rows:
        moved: dict[Any, Any] = {}
        for key, value in row.items():
            moved[after if key == before else key] = value
        renamed.append(moved)
    return renamed


def _add_column(args: list[Any]) -> list[dict[Any, Any]]:
    """Give every row the same value for a new column, which is how a tag is added."""
    rows = _rows(args[0], "addColumn")
    name = _column(args[1], "addColumn")
    value = args[2]
    return [{**row, name: value} for row in rows]


def _where_equals(args: list[Any]) -> list[dict[Any, Any]]:
    rows = _rows(args[0], "whereEquals")
    column = _column(args[1], "whereEquals")
    wanted = args[2]
    return [row for row in rows if row.get(column, _MISSING) == wanted]


def _where_above(args: list[Any]) -> list[dict[Any, Any]]:
    rows = _rows(args[0], "whereAbove")
    column = _column(args[1], "whereAbove")
    floor = args[2]
    if isinstance(floor, bool) or not isinstance(floor, (int, float)):
        raise TypeMismatch(
            f"whereAbove compares against a number, not a {type_name(floor)}"
        )
    kept: list[dict[Any, Any]] = []
    for index, row in enumerate(rows):
        if column not in row:
            continue
        if _number(row[column], column, index, "whereAbove") > floor:
            kept.append(row)
    return kept


def _where_present(args: list[Any]) -> list[dict[Any, Any]]:
    """The rows that have the column at all, which is how a gap is found."""
    rows = _rows(args[0], "wherePresent")
    column = _column(args[1], "wherePresent")
    return [row for row in rows if column in row]


def _order_by(args: list[Any]) -> list[dict[Any, Any]]:
    rows = _rows(args[0], "orderBy")
    column = _column(args[1], "orderBy")
    present = [row for row in rows if column in row]
    absent = [row for row in rows if column not in row]
    _sortable([row[column] for row in present], column, "orderBy")
    # a row without the column sorts last, because it has no place among the values
    return sorted(present, key=lambda row: row[column]) + absent


def _order_by_descending(args: list[Any]) -> list[dict[Any, Any]]:
    rows = _rows(args[0], "orderByDescending")
    column = _column(args[1], "orderByDescending")
    present = [row for row in rows if column in row]
    absent = [row for row in rows if column not in row]
    _sortable([row[column] for row in present], column, "orderByDescending")
    return sorted(present, key=lambda row: row[column], reverse=True) + absent


def _top_by(args: list[Any]) -> list[dict[Any, Any]]:
    rows = _rows(args[0], "topBy")
    column = _column(args[1], "topBy")
    count = _whole(args[2], "topBy")
    if count < 0:
        raise Arithmetic(f"topBy needs a count of zero or more, not {count}")
    return _order_by_descending([rows, column])[:count]


def _group_by(args: list[Any]) -> dict[Any, list[dict[Any, Any]]]:
    """Split into a map from each value of the column to the rows holding it."""
    rows = _rows(args[0], "groupBy")
    column = _column(args[1], "groupBy")
    groups: dict[Any, list[dict[Any, Any]]] = {}
    for index, row in enumerate(rows):
        key = _cell(row, column, index, "groupBy")
        if isinstance(key, (list, dict)):
            raise TypeMismatch(
                f"groupBy cannot group on a {type_name(key)}, which row {index} holds "
                f"in the column {column!r}; a group key must be a single value"
            )
        groups.setdefault(key, []).append(row)
    return groups


def _count_by(args: list[Any]) -> dict[Any, int]:
    groups = _group_by([args[0], args[1]])
    return {key: len(rows) for key, rows in groups.items()}


def _distinct_values(args: list[Any]) -> list[Any]:
    """Each value the column takes, once, in the order the rows first showed it."""
    rows = _rows(args[0], "distinctValues")
    column = _column(args[1], "distinctValues")
    seen: list[Any] = []
    for row in rows:
        if column in row and row[column] not in seen:
            seen.append(row[column])
    return seen


def _sum_by(args: list[Any]) -> float:
    rows = _rows(args[0], "sumBy")
    column = _column(args[1], "sumBy")
    total: float = 0
    for index, row in enumerate(rows):
        if column in row:
            total += _number(row[column], column, index, "sumBy")
    return total


def _mean_by(args: list[Any]) -> float:
    rows = _rows(args[0], "meanBy")
    column = _column(args[1], "meanBy")
    values = [
        _number(row[column], column, index, "meanBy")
        for index, row in enumerate(rows)
        if column in row
    ]
    if not values:
        # a mean over no rows has no answer, and zero would be a number that looks like one
        raise Arithmetic(
            f"meanBy has no rows holding the column {column!r}, so there is no mean"
        )
    # the mean is over the rows that have the column, not over every row
    return sum(values) / len(values)


def _max_by(args: list[Any]) -> dict[Any, Any]:
    rows = _order_by_descending([args[0], args[1]])
    column = _column(args[1], "maxBy")
    if not rows or column not in rows[0]:
        raise Arithmetic(
            f"maxBy has no rows holding the column {column!r}, so there is no largest"
        )
    return rows[0]


def _min_by(args: list[Any]) -> dict[Any, Any]:
    rows = _order_by([args[0], args[1]])
    column = _column(args[1], "minBy")
    if not rows or column not in rows[0]:
        raise Arithmetic(
            f"minBy has no rows holding the column {column!r}, so there is no smallest"
        )
    return rows[0]


def _join_on(args: list[Any]) -> list[dict[Any, Any]]:
    """Inner equi-join on one column, the right side winning any other collision."""
    left = _rows(args[0], "joinOn")
    right = _rows(args[1], "joinOn")
    column = _column(args[2], "joinOn")
    by_key: dict[Any, list[dict[Any, Any]]] = {}
    for index, row in enumerate(right):
        by_key.setdefault(_cell(row, column, index, "joinOn"), []).append(row)
    joined: list[dict[Any, Any]] = []
    for index, row in enumerate(left):
        key = _cell(row, column, index, "joinOn")
        for other in by_key.get(key, []):
            joined.append({**row, **other})
    return joined


def _left_join_on(args: list[Any]) -> list[dict[Any, Any]]:
    """Every left row once at least, unmatched ones keeping only their own columns."""
    left = _rows(args[0], "leftJoinOn")
    right = _rows(args[1], "leftJoinOn")
    column = _column(args[2], "leftJoinOn")
    by_key: dict[Any, list[dict[Any, Any]]] = {}
    for index, row in enumerate(right):
        by_key.setdefault(_cell(row, column, index, "leftJoinOn"), []).append(row)
    joined: list[dict[Any, Any]] = []
    for index, row in enumerate(left):
        key = _cell(row, column, index, "leftJoinOn")
        matches = by_key.get(key, [])
        if not matches:
            # nothing invented for the missing columns, so a gap stays a gap
            joined.append(dict(row))
            continue
        for other in matches:
            joined.append({**row, **other})
    return joined


def _rows_to_columns(args: list[Any]) -> dict[str, list[Any]]:
    """Turn the table on its side, one list per column, gaps becoming nil."""
    rows = _rows(args[0], "rowsToColumns")
    columns = _columns([rows])
    return {name: [row.get(name) for row in rows] for name in columns}


def _columns_to_rows(args: list[Any]) -> list[dict[str, Any]]:
    """Turn it back, which needs every column to be the same length."""
    table = args[0]
    if not isinstance(table, dict):
        raise TypeMismatch(
            f"columnsToRows needs a map of column names to lists, not a "
            f"{type_name(table)}"
        )
    lengths = set()
    for name, values in table.items():
        if not isinstance(values, list):
            raise TypeMismatch(
                f"columnsToRows needs a list for the column {str(name)!r}, not a "
                f"{type_name(values)}"
            )
        lengths.add(len(values))
    if len(lengths) > 1:
        raise Arithmetic(
            "columnsToRows needs every column to hold the same count of values, and "
            f"these hold {_listed([str(length) for length in sorted(lengths)])}"
        )
    height = lengths.pop() if lengths else 0
    return [
        {str(name): values[index] for name, values in table.items()}
        for index in range(height)
    ]


def _table_text(args: list[Any]) -> str:
    """A fixed width rendering, columns in the order asked for, gaps left blank."""
    rows = _rows(args[0], "tableText")
    wanted = _names(args[1], "tableText")
    if not wanted:
        raise Arithmetic("tableText needs at least one column to show")
    cells = [[_shown(row.get(name)) for name in wanted] for row in rows]
    widths = [
        max([len(name)] + [len(line[position]) for line in cells])
        for position, name in enumerate(wanted)
    ]
    lines = ["  ".join(name.ljust(widths[at]) for at, name in enumerate(wanted)).rstrip()]
    lines.append("  ".join("-" * width for width in widths))
    for line in cells:
        lines.append(
            "  ".join(value.ljust(widths[at]) for at, value in enumerate(line)).rstrip()
        )
    return chr(10).join(lines)


def _shown(value: Any) -> str:
    if value is None:
        return ""
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value)


_REGISTRY: dict[str, tuple[int, Any]] = {
    "addColumn": (3, _add_column),
    "columns": (1, _columns),
    "columnsToRows": (1, _columns_to_rows),
    "countBy": (2, _count_by),
    "distinctValues": (2, _distinct_values),
    "dropColumn": (2, _drop_column),
    "groupBy": (2, _group_by),
    "joinOn": (3, _join_on),
    "leftJoinOn": (3, _left_join_on),
    "maxBy": (2, _max_by),
    "meanBy": (2, _mean_by),
    "minBy": (2, _min_by),
    "orderBy": (2, _order_by),
    "orderByDescending": (2, _order_by_descending),
    "renameColumn": (3, _rename_column),
    "rowsToColumns": (1, _rows_to_columns),
    "select": (2, _select),
    "sumBy": (2, _sum_by),
    "tableText": (2, _table_text),
    "topBy": (3, _top_by),
    "whereAbove": (3, _where_above),
    "whereEquals": (3, _where_equals),
    "wherePresent": (2, _where_present),
}


def install_table_library(machine: Any) -> None:
    for name, (arity, handler) in _REGISTRY.items():
        machine.define_native(name, arity, handler)


def table_names() -> list[str]:
    return sorted(_REGISTRY)
