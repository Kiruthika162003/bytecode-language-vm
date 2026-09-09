"""The standard builtins: the small library of native functions every program starts with.

A language is only as useful as what a program can reach without writing
it first, and some things a program simply cannot write for itself in
terms of the language: measuring a list, converting a string to a number,
taking a square root. This module supplies that floor as native
functions, implemented in the host and installed into the machine's
globals before a program runs, so that len, str, type, and their
companions are available the way a keyword is, but as ordinary values
that a program could even shadow. Each native function validates its
arguments and fails with the same error family the rest of the runtime
uses, so calling len on a number reports a type mismatch in the
language's own voice rather than leaking a host exception. The deliberate
scope is small and deterministic. The functions here compute from their
arguments alone and touch nothing outside, so a program's behavior
depends only on its inputs, which is what lets the tests pin exact
outputs; facilities that read the outside world, a clock or a random
source, are left out of this core precisely because they would make a
program's output depend on when it ran, and a language that wants them
adds them knowingly. Where a function could accept a variable number of
arguments, it takes a single list instead, keeping every native function
at a fixed arity so the call instruction checks argument counts the same
way for all of them.
"""

from __future__ import annotations

import math
from typing import Any

from ember.bitlib import bit_names, install_bit_library
from ember.chartlib import chart_names, install_chart_library
from ember.csvlib import csv_names, install_csv_library
from ember.datelib import date_names, install_date_library
from ember.difflib import diff_names, install_diff_library
from ember.encodelib import encode_names, install_encode_library
from ember.errors import Arithmetic, IndexRange, TypeMismatch
from ember.fraclib import fraction_names, install_fraction_library
from ember.geometrylib import geometry_names, install_geometry_library
from ember.hashlib import hash_names, install_hash_library
from ember.heaplib import heap_names, install_heap_library
from ember.higherorder import higher_order_names, install_higher_order
from ember.intervallib import install_interval_library, interval_names
from ember.jsonlib import install_json_library, json_names
from ember.listlib import install_list_library, list_names
from ember.maplib import install_map_library, map_names
from ember.mathlib import install_math_library, math_names
from ember.matrixlib import install_matrix_library, matrix_names
from ember.queuelib import install_queue_library, queue_names
from ember.randomlib import install_random_library, random_names
from ember.regexlib import install_regex_library, regex_names
from ember.schemalib import install_schema_library, schema_names
from ember.setlib import install_set_library, set_names
from ember.sortlib import install_sort_library, sort_names
from ember.statlib import install_stat_library, stat_names
from ember.stringlib import install_string_library, string_names
from ember.textlib import install_text_library, text_names
from ember.valueops import stringify, type_name, values_equal
from ember.vm import VM


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _length(args: list[Any]) -> int:
    value = args[0]
    if isinstance(value, (str, list, dict)):
        return len(value)
    raise TypeMismatch(f"len needs a string, list, or map, not a {type_name(value)}")


def _to_string(args: list[Any]) -> str:
    return stringify(args[0])


def _to_int(args: list[Any]) -> int:
    value = args[0]
    if isinstance(value, bool):
        raise TypeMismatch("int does not convert a bool; compare it instead")
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, str):
        try:
            return int(value.strip())
        except ValueError as exc:
            raise TypeMismatch(f"the string {value!r} does not name an integer") from exc
    raise TypeMismatch(f"int cannot convert a {type_name(value)}")


def _to_float(args: list[Any]) -> float:
    value = args[0]
    if isinstance(value, bool):
        raise TypeMismatch("float does not convert a bool")
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError as exc:
            raise TypeMismatch(f"the string {value!r} does not name a number") from exc
    raise TypeMismatch(f"float cannot convert a {type_name(value)}")


def _type_of(args: list[Any]) -> str:
    return type_name(args[0])


def _absolute(args: list[Any]) -> Any:
    value = args[0]
    if not _is_number(value):
        raise TypeMismatch(f"abs needs a number, not a {type_name(value)}")
    return abs(value)


def _square_root(args: list[Any]) -> float:
    value = args[0]
    if not _is_number(value):
        raise TypeMismatch(f"sqrt needs a number, not a {type_name(value)}")
    if value < 0:
        raise Arithmetic("sqrt of a negative number has no real result")
    return math.sqrt(value)


def _floor(args: list[Any]) -> int:
    value = args[0]
    if not _is_number(value):
        raise TypeMismatch(f"floor needs a number, not a {type_name(value)}")
    return math.floor(value)


def _ceil(args: list[Any]) -> int:
    value = args[0]
    if not _is_number(value):
        raise TypeMismatch(f"ceil needs a number, not a {type_name(value)}")
    return math.ceil(value)


def _smallest(args: list[Any]) -> Any:
    return _reduce_extreme(args[0], smallest=True)


def _largest(args: list[Any]) -> Any:
    return _reduce_extreme(args[0], smallest=False)


def _reduce_extreme(value: Any, smallest: bool) -> Any:
    if not isinstance(value, list):
        raise TypeMismatch(f"min and max need a list, not a {type_name(value)}")
    if not value:
        raise IndexRange("min and max need a non-empty list")
    best = value[0]
    for item in value[1:]:
        if not (_is_number(best) and _is_number(item)):
            raise TypeMismatch("min and max compare numbers")
        if (item < best) == smallest:
            best = item
    return best


def _push(args: list[Any]) -> Any:
    target, item = args[0], args[1]
    if not isinstance(target, list):
        raise TypeMismatch(f"push needs a list, not a {type_name(target)}")
    target.append(item)
    return target


def _pop(args: list[Any]) -> Any:
    target = args[0]
    if not isinstance(target, list):
        raise TypeMismatch(f"pop needs a list, not a {type_name(target)}")
    if not target:
        raise IndexRange("pop needs a non-empty list")
    return target.pop()


def _keys(args: list[Any]) -> list[Any]:
    target = args[0]
    if not isinstance(target, dict):
        raise TypeMismatch(f"keys needs a map, not a {type_name(target)}")
    return list(target.keys())


def _values(args: list[Any]) -> list[Any]:
    target = args[0]
    if not isinstance(target, dict):
        raise TypeMismatch(f"values needs a map, not a {type_name(target)}")
    return list(target.values())


def _contains(args: list[Any]) -> bool:
    collection, item = args[0], args[1]
    if isinstance(collection, list):
        return any(values_equal(existing, item) for existing in collection)
    if isinstance(collection, dict):
        return item in collection
    if isinstance(collection, str):
        return isinstance(item, str) and item in collection
    raise TypeMismatch(f"contains needs a list, map, or string, not a {type_name(collection)}")


def _range(args: list[Any]) -> list[int]:
    count = args[0]
    if isinstance(count, bool) or not isinstance(count, int):
        raise TypeMismatch(f"range needs an integer count, not a {type_name(count)}")
    if count < 0:
        raise IndexRange("range needs a count of zero or more")
    return list(range(count))


_REGISTRY: dict[str, tuple[int, Any]] = {
    "len": (1, _length),
    "str": (1, _to_string),
    "int": (1, _to_int),
    "float": (1, _to_float),
    "type": (1, _type_of),
    "abs": (1, _absolute),
    "sqrt": (1, _square_root),
    "floor": (1, _floor),
    "ceil": (1, _ceil),
    "min": (1, _smallest),
    "max": (1, _largest),
    "push": (2, _push),
    "pop": (1, _pop),
    "keys": (1, _keys),
    "values": (1, _values),
    "contains": (2, _contains),
    "range": (1, _range),
}


def install_builtins(machine: VM) -> None:
    for name, (arity, handler) in _REGISTRY.items():
        machine.define_native(name, arity, handler)
    install_string_library(machine)
    install_list_library(machine)
    install_math_library(machine)
    install_higher_order(machine)
    install_map_library(machine)
    install_set_library(machine)
    install_stat_library(machine)
    install_text_library(machine)
    install_json_library(machine)
    install_sort_library(machine)
    install_date_library(machine)
    install_random_library(machine)
    install_bit_library(machine)
    install_heap_library(machine)
    install_csv_library(machine)
    install_fraction_library(machine)
    install_matrix_library(machine)
    install_regex_library(machine)
    install_encode_library(machine)
    install_diff_library(machine)
    install_schema_library(machine)
    install_queue_library(machine)
    install_hash_library(machine)
    install_geometry_library(machine)
    install_chart_library(machine)
    install_interval_library(machine)


def builtin_names() -> list[str]:
    names = set(_REGISTRY) | set(string_names()) | set(list_names()) | set(math_names())
    names |= set(higher_order_names())
    names |= set(map_names()) | set(set_names())
    names |= set(stat_names()) | set(text_names())
    names |= set(json_names()) | set(sort_names())
    names |= set(date_names()) | set(random_names()) | set(bit_names())
    names |= set(heap_names()) | set(csv_names()) | set(fraction_names())
    names |= set(matrix_names()) | set(regex_names())
    names |= set(encode_names()) | set(diff_names())
    names |= set(schema_names()) | set(queue_names())
    names |= set(hash_names()) | set(geometry_names())
    names |= set(chart_names()) | set(interval_names())
    return sorted(names)
