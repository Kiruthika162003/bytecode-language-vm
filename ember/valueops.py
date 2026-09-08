"""Value semantics: the runtime's rules for truth, equality, type names, and printing.

A dynamically typed language must answer three questions about its
values at run time that a statically typed one settles at compile time:
is this value true when a condition tests it, are these two values equal,
and how does this value look when printed. Scattering those answers
through the machine's instruction handlers would let them drift apart, so
this module gathers them in one place that the machine calls into. Each
rule is a small deliberate choice. Truthiness is kept narrow: only the
boolean false and nil are false, and everything else, including zero and
the empty string, is true, because a language where zero is false invites
the bug where a legitimate zero is mistaken for absence, and the honest
cost is that a programmer used to the looser rule must write an explicit
comparison. Equality compares by value within a type and never across
types, so the integer one and the boolean true are not equal even though
the host language conflates them, which keeps the language's own model
consistent regardless of the host's quirks. Printing renders a value the
way the language talks about it, not the way Python does: nil prints as
nil, the booleans as true and false, and a whole-valued float without a
trailing point is still shown as a float so the type stays visible. These
choices are the language's personality, collected here so they are stated
once and tested directly.
"""

from __future__ import annotations

from typing import Any

from ember.classes import BoundMethod
from ember.closure import Closure
from ember.function import Function, NativeFunction


def is_truthy(value: Any) -> bool:
    if value is None:
        return False
    if value is True or value is False:
        return value
    return True


def values_equal(left: Any, right: Any) -> bool:
    if left is None or right is None:
        return left is None and right is None
    left_bool = left is True or left is False
    right_bool = right is True or right is False
    if left_bool != right_bool:
        return False
    if left_bool:
        return left is right
    if isinstance(left, bool) or isinstance(right, bool):
        return False
    if type(left) is not type(right):
        # allow int and float to compare numerically, nothing else across types
        if isinstance(left, (int, float)) and isinstance(right, (int, float)):
            return left == right
        return False
    return left == right


def type_name(value: Any) -> str:
    if value is None:
        return "nil"
    if value is True or value is False:
        return "bool"
    if isinstance(value, bool):
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, float):
        return "float"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "list"
    if isinstance(value, dict):
        return "map"
    # classes and instances are recognized by shape rather than by type, so the
    # two backends' own objects report the same names without this module having
    # to import either backend and create a cycle
    if hasattr(value, "klass") and hasattr(value, "fields"):
        return value.klass.name
    if hasattr(value, "methods") and hasattr(value, "name"):
        return "class"
    if isinstance(value, (Function, NativeFunction, Closure, BoundMethod)):
        return "function"
    if hasattr(value, "arity"):
        return "function"
    return "value"


def stringify(value: Any) -> str:
    if value is None:
        return "nil"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, float):
        if value == int(value) and value not in (float("inf"), float("-inf")):
            return f"{int(value)}.0"
        return repr(value)
    if isinstance(value, str):
        return value
    if isinstance(value, list):
        return "[" + ", ".join(_element(item) for item in value) + "]"
    if isinstance(value, dict):
        pairs = ", ".join(f"{_element(k)}: {_element(v)}" for k, v in value.items())
        return "{" + pairs + "}"
    return str(value)


def _element(value: Any) -> str:
    if isinstance(value, str):
        return f'"{value}"'
    return stringify(value)
