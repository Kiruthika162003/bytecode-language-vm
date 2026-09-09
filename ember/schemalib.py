"""Validating data against a shape, and saying precisely where it did not fit.

A program that reads data from outside itself has to check that data before trusting it, and
the checking is where such programs are most often wrong: not because the checks are hard,
but because writing them by hand means writing the same nested conditions repeatedly and
getting one of them subtly wrong. A schema states the shape once and the checking follows
from it.

A schema is written in the language's own values, a map describing what is expected, so a
program can build one at run time, print it, store it, and send it through the JSON library
without any of that needing a new type. The keys are the vocabulary: a type, whether a value
is optional, bounds for a number, a length range for a string or list, a set of allowed
values, the shape of a list's elements, and the shape of a map's fields. Nothing here is a
general purpose predicate, because a schema holding a function could not be printed or
serialised and would turn the schema from data into code.

Reporting is the part worth the care. A validator that answers yes or no is nearly useless
on data of any depth, because the whole question is which part was wrong, so every failure
carries a path saying where it was found: the field of the map, the index of the list, and
so on down. A program can then say precisely what its caller got wrong instead of refusing a
document with no explanation. Every failure is collected rather than stopping at the first,
for the same reason a compiler reports more than one error: someone fixing a document wants
the whole list.

Two decisions worth naming. An absent field and a field holding nil are different, because a
document that omitted something and one that explicitly said nothing are different documents,
so optional means may be absent while a type of nil means must be nil. And a map with fields
the schema does not mention passes by default, with strictness available as a setting, because
data usually arrives from something that adds fields over time and a validator that refused
every unexpected field would break on every upstream addition.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ember.errors import Arithmetic, TypeMismatch
from ember.valueops import type_name, values_equal

_KINDS = ("any", "int", "float", "number", "string", "bool", "nil", "list", "map")
_SETTINGS = (
    "type",
    "optional",
    "least",
    "most",
    "shortest",
    "longest",
    "allowed",
    "elements",
    "fields",
    "strict",
)


@dataclass(frozen=True)
class Problem:
    """One place the data did not fit, named by its path."""

    path: str
    message: str

    def render(self) -> str:
        where = self.path or "the value"
        return f"{where}: {self.message}"


@dataclass
class Result:
    """Every place the data did not fit, or none."""

    problems: list[Problem] = field(default_factory=list)

    @property
    def valid(self) -> bool:
        return not self.problems

    @property
    def count(self) -> int:
        return len(self.problems)

    def paths(self) -> list[str]:
        return [problem.path for problem in self.problems]

    def render(self) -> list[str]:
        if self.valid:
            return ["the value fits the schema"]
        return [problem.render() for problem in self.problems]

    def summary(self) -> str:
        if self.valid:
            return "valid"
        noun = "problem" if self.count == 1 else "problems"
        return f"{self.count} {noun}"


def _check_schema(schema: Any, path: str) -> None:
    """Refuse a schema that is not one, rather than silently accepting anything."""
    if not isinstance(schema, dict):
        raise TypeMismatch(
            f"a schema is a map describing what is expected, and at {path or 'the top'} "
            f"this is a {type_name(schema)}"
        )
    for key in schema:
        if not isinstance(key, str):
            raise TypeMismatch(f"a schema's keys are strings, and {key!r} is not")
        if key not in _SETTINGS:
            raise Arithmetic(
                f"{key!r} is not a schema setting; the settings are "
                + ", ".join(_SETTINGS)
            )
    kind = schema.get("type", "any")
    if not isinstance(kind, str) or kind not in _KINDS:
        raise Arithmetic(
            f"{kind!r} is not a type a schema knows; the types are " + ", ".join(_KINDS)
        )


def _matches_kind(value: Any, kind: str) -> bool:
    if kind == "any":
        return True
    if kind == "nil":
        return value is None
    if kind == "bool":
        return isinstance(value, bool)
    if kind == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    if kind == "float":
        return isinstance(value, float)
    if kind == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if kind == "string":
        return isinstance(value, str)
    if kind == "list":
        return isinstance(value, list)
    return isinstance(value, dict)


def _joined(path: str, piece: str) -> str:
    return piece if not path else f"{path}.{piece}"


def _check_bounds(value: Any, schema: dict[str, Any], path: str, found: Result) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return
    least = schema.get("least")
    most = schema.get("most")
    if least is not None and value < least:
        found.problems.append(Problem(path, f"{value} is below the least allowed, {least}"))
    if most is not None and value > most:
        found.problems.append(Problem(path, f"{value} is above the most allowed, {most}"))


def _check_length(value: Any, schema: dict[str, Any], path: str, found: Result) -> None:
    if not isinstance(value, (str, list, dict)):
        return
    shortest = schema.get("shortest")
    longest = schema.get("longest")
    size = len(value)
    if shortest is not None and size < shortest:
        found.problems.append(
            Problem(path, f"a length of {size} is shorter than the {shortest} required")
        )
    if longest is not None and size > longest:
        found.problems.append(
            Problem(path, f"a length of {size} is longer than the {longest} allowed")
        )


def _check_allowed(value: Any, schema: dict[str, Any], path: str, found: Result) -> None:
    allowed = schema.get("allowed")
    if allowed is None:
        return
    if not isinstance(allowed, list):
        raise TypeMismatch("the allowed values of a schema are given as a list")
    if not any(values_equal(value, one) for one in allowed):
        listed = ", ".join(str(one) for one in allowed)
        found.problems.append(Problem(path, f"{value!r} is not one of {listed}"))


def _validate(value: Any, schema: Any, path: str, found: Result) -> None:
    _check_schema(schema, path)
    kind = schema.get("type", "any")
    if not _matches_kind(value, kind):
        found.problems.append(
            Problem(path, f"expected {kind} but found {type_name(value)}")
        )
        # the shape is wrong, so the settings below would report against the wrong kind
        return
    _check_bounds(value, schema, path, found)
    _check_length(value, schema, path, found)
    _check_allowed(value, schema, path, found)
    if isinstance(value, list) and "elements" in schema:
        for index, element in enumerate(value):
            _validate(element, schema["elements"], _joined(path, f"[{index}]"), found)
    if isinstance(value, dict) and "fields" in schema:
        _validate_fields(value, schema, path, found)


def _validate_fields(
    value: dict[Any, Any], schema: dict[str, Any], path: str, found: Result
) -> None:
    fields = schema["fields"]
    if not isinstance(fields, dict):
        raise TypeMismatch("the fields of a schema are given as a map")
    for name, inner in fields.items():
        if not isinstance(name, str):
            raise TypeMismatch(f"a field name is a string, and {name!r} is not")
        if name not in value:
            if not (isinstance(inner, dict) and inner.get("optional")):
                # absent and present holding nil are different documents
                found.problems.append(Problem(_joined(path, name), "this field is missing"))
            continue
        _validate(value[name], inner, _joined(path, name), found)
    if schema.get("strict"):
        for name in value:
            if isinstance(name, str) and name not in fields:
                found.problems.append(
                    Problem(_joined(path, str(name)), "this field is not in the schema")
                )


def validate(value: Any, schema: Any) -> Result:
    """Every place the value fails the schema, in the order they were found."""
    found = Result()
    _validate(value, schema, "", found)
    return found


def _valid(args: list[Any]) -> bool:
    return validate(args[0], args[1]).valid


def _problems_of(args: list[Any]) -> list[str]:
    found = validate(args[0], args[1])
    # nothing rather than a line saying it fits, so a caller can test the list itself
    return [] if found.valid else found.render()


def _paths_of(args: list[Any]) -> list[str]:
    return validate(args[0], args[1]).paths()


def _problem_count(args: list[Any]) -> int:
    return validate(args[0], args[1]).count


def _explain(args: list[Any]) -> str:
    return validate(args[0], args[1]).summary()


def _is_schema(args: list[Any]) -> bool:
    try:
        _check_schema(args[0], "")
    except (TypeMismatch, Arithmetic):
        return False
    return True


def _schema_settings(args: list[Any]) -> list[str]:
    del args
    return list(_SETTINGS)


def _schema_types(args: list[Any]) -> list[str]:
    del args
    return list(_KINDS)


_REGISTRY: dict[str, tuple[int, Any]] = {
    "isValid": (2, _valid),
    "schemaProblems": (2, _problems_of),
    "schemaPaths": (2, _paths_of),
    "schemaProblemCount": (2, _problem_count),
    "explainSchema": (2, _explain),
    "isSchema": (1, _is_schema),
    "schemaSettings": (1, _schema_settings),
    "schemaTypes": (1, _schema_types),
}


def install_schema_library(machine: Any) -> None:
    for name, (arity, handler) in _REGISTRY.items():
        machine.define_native(name, arity, handler)


def schema_names() -> list[str]:
    return sorted(_REGISTRY)
