"""Quantities with units, and the conversions that are refused rather than performed.

A number without its unit is where a program loses track of what it is computing, and the
famous failures of that kind were not arithmetic errors: the arithmetic was right and the units
did not match. A quantity here carries its unit, so adding a length to a time is refused at the
moment it is attempted rather than producing a number that looks like an answer.

A quantity is a list of a number and a unit name, so it prints and serialises like any other
value. Units belong to families, length and mass and time and so on, and each family names one
unit as its base with every other defined as a multiple of it. That single table is the whole of
the conversion machinery: converting means multiplying to the base and dividing out to the
target, and refusing means noticing that the two units belong to different families.

Temperature is the exception that shows why the table is shaped this way. Every other
conversion is a multiplication, so a scale factor is all a unit needs; a temperature
conversion has an offset as well, since zero in one scale is not zero in another. That means
temperatures cannot be added to each other meaningfully at all, which most unit libraries
quietly allow, and this one refuses: adding twenty degrees to thirty degrees is a question
about a difference rather than a sum, and a library that answered fifty would be answering
a question nobody asked.

Multiplication and division of quantities are deliberately absent. Multiplying a length by a
length gives an area, which is a different family with its own units, and doing that properly
means tracking dimensions as exponents rather than as names. That is a real and much larger
design, and half of it would be worse than none: a library that multiplied two lengths and
called the result a length would produce exactly the silent wrongness this one exists to
prevent. Adding, subtracting, comparing and converting are what is offered, and each of them
is exact about which units it accepts.
"""

from __future__ import annotations

from typing import Any

from ember.errors import Arithmetic, TypeMismatch
from ember.valueops import type_name

# each family names its base unit, and every other unit is a multiple of that base
_FAMILIES: dict[str, dict[str, float]] = {
    "length": {
        "metre": 1.0,
        "kilometre": 1000.0,
        "centimetre": 0.01,
        "millimetre": 0.001,
        "mile": 1609.344,
        "yard": 0.9144,
        "foot": 0.3048,
        "inch": 0.0254,
    },
    "mass": {
        "kilogram": 1.0,
        "gram": 0.001,
        "tonne": 1000.0,
        "pound": 0.45359237,
        "ounce": 0.028349523125,
    },
    "time": {
        "second": 1.0,
        "minute": 60.0,
        "hour": 3600.0,
        "day": 86400.0,
        "week": 604800.0,
        "millisecond": 0.001,
    },
    "volume": {
        "litre": 1.0,
        "millilitre": 0.001,
        "gallon": 4.54609,
        "pint": 0.56826125,
    },
}

# a comparison of converted amounts needs slack: converting goes through floating
# point, so two quantities that are the same temperature can differ in the last bits
_TOLERANCE = 1e-9

# temperature is its own case: a conversion here has an offset as well as a factor
_TEMPERATURES: dict[str, tuple[float, float]] = {
    "kelvin": (1.0, 0.0),
    "celsius": (1.0, 273.15),
    "fahrenheit": (5.0 / 9.0, 255.372222222222222),
}


def _unit_family(unit: str) -> str | None:
    for family, units in _FAMILIES.items():
        if unit in units:
            return family
    return "temperature" if unit in _TEMPERATURES else None


def _text(value: Any, who: str) -> str:
    if not isinstance(value, str):
        raise TypeMismatch(f"{who} needs a unit name as a string, not a {type_name(value)}")
    return value


def _number(value: Any, who: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeMismatch(f"{who} needs a number, not a {type_name(value)}")
    return value


def _known(unit: str, who: str) -> str:
    family = _unit_family(unit)
    if family is None:
        raise Arithmetic(f"{who} does not know the unit {unit!r}")
    return family


def _quantity(value: Any, who: str) -> tuple[float, str]:
    if not isinstance(value, list) or len(value) != 2:
        raise TypeMismatch(
            f"{who} needs a quantity as a list of a number and a unit, not a "
            f"{type_name(value)}"
        )
    amount = _number(value[0], who)
    unit = _text(value[1], who)
    _known(unit, who)
    return amount, unit


def _made(args: list[Any]) -> list[Any]:
    amount = _number(args[0], "quantity")
    unit = _text(args[1], "quantity")
    _known(unit, "quantity")
    return [amount, unit]


def _to_base(amount: float, unit: str) -> float:
    if unit in _TEMPERATURES:
        factor, offset = _TEMPERATURES[unit]
        return amount * factor + offset
    for units in _FAMILIES.values():
        if unit in units:
            return amount * units[unit]
    raise Arithmetic(f"the unit {unit!r} is not known")


def _from_base(amount: float, unit: str) -> float:
    if unit in _TEMPERATURES:
        factor, offset = _TEMPERATURES[unit]
        return (amount - offset) / factor
    for units in _FAMILIES.values():
        if unit in units:
            return amount / units[unit]
    raise Arithmetic(f"the unit {unit!r} is not known")


def convert(amount: float, unit: str, target: str, who: str = "convert") -> float:
    from_family = _known(unit, who)
    to_family = _known(target, who)
    if from_family != to_family:
        # the whole point: this is refused at the moment it is attempted
        raise Arithmetic(
            f"{unit} measures {from_family} and {target} measures {to_family}, so one "
            "cannot be converted into the other"
        )
    return _from_base(_to_base(amount, unit), target)


def _converted(args: list[Any]) -> list[Any]:
    amount, unit = _quantity(args[0], "convertTo")
    target = _text(args[1], "convertTo")
    return [convert(amount, unit, target, "convertTo"), target]


def _amount_of(args: list[Any]) -> float:
    return _quantity(args[0], "amountOf")[0]


def _unit_of(args: list[Any]) -> str:
    return _quantity(args[0], "unitOf")[1]


def _family_of(args: list[Any]) -> str:
    unit = _text(args[0], "familyOf")
    return _known(unit, "familyOf")


def _same_family(args: list[Any]) -> bool:
    left = _text(args[0], "sameFamily")
    right = _text(args[1], "sameFamily")
    return _known(left, "sameFamily") == _known(right, "sameFamily")


def _known_units(args: list[Any]) -> list[str]:
    del args
    found: list[str] = []
    for units in _FAMILIES.values():
        found.extend(units)
    found.extend(_TEMPERATURES)
    return sorted(found)


def _units_in(args: list[Any]) -> list[str]:
    family = _text(args[0], "unitsIn")
    if family == "temperature":
        return sorted(_TEMPERATURES)
    if family not in _FAMILIES:
        raise Arithmetic(f"unitsIn does not know the family {family!r}")
    return sorted(_FAMILIES[family])


def _families(args: list[Any]) -> list[str]:
    del args
    return sorted([*_FAMILIES, "temperature"])


def _refuse_temperature(unit: str, who: str) -> None:
    if unit in _TEMPERATURES:
        raise Arithmetic(
            f"{who} has no meaning for temperatures, because a scale with an offset has "
            "no zero to add from; subtract to get a difference instead"
        )


def _added(args: list[Any]) -> list[Any]:
    left_amount, left_unit = _quantity(args[0], "quantityAdd")
    right_amount, right_unit = _quantity(args[1], "quantityAdd")
    _refuse_temperature(left_unit, "quantityAdd")
    _refuse_temperature(right_unit, "quantityAdd")
    moved = convert(right_amount, right_unit, left_unit, "quantityAdd")
    return [left_amount + moved, left_unit]


def _subtracted(args: list[Any]) -> list[Any]:
    left_amount, left_unit = _quantity(args[0], "quantitySubtract")
    right_amount, right_unit = _quantity(args[1], "quantitySubtract")
    moved = convert(right_amount, right_unit, left_unit, "quantitySubtract")
    return [left_amount - moved, left_unit]


def _scaled(args: list[Any]) -> list[Any]:
    amount, unit = _quantity(args[0], "quantityScaled")
    _refuse_temperature(unit, "quantityScaled")
    return [amount * _number(args[1], "quantityScaled"), unit]


def _compared(args: list[Any]) -> int:
    """Minus one, zero or one, with a tolerance because converting goes through floats.

    Comparing the converted amounts exactly said that nought degrees celsius was below
    thirty two degrees fahrenheit, which are the same temperature: the conversion
    produced five times ten to the minus fourteen rather than zero, and an exact
    comparison believed it. Any comparison of quantities that had to be converted has
    that problem, so the tolerance is relative to the sizes involved rather than
    absolute, since a tolerance that suits metres is far too coarse for millimetres.
    """
    left_amount, left_unit = _quantity(args[0], "quantityCompare")
    right_amount, right_unit = _quantity(args[1], "quantityCompare")
    moved = convert(right_amount, right_unit, left_unit, "quantityCompare")
    scale = max(abs(left_amount), abs(moved), 1.0)
    if abs(left_amount - moved) <= _TOLERANCE * scale:
        return 0
    return -1 if left_amount < moved else 1


def _quantity_text(args: list[Any]) -> str:
    amount, unit = _quantity(args[0], "quantityToText")
    plural = unit if amount == 1 else unit + "s"
    return f"{amount} {plural}"


_REGISTRY: dict[str, tuple[int, Any]] = {
    "quantity": (2, _made),
    "convertTo": (2, _converted),
    "amountOf": (1, _amount_of),
    "unitOf": (1, _unit_of),
    "familyOf": (1, _family_of),
    "sameFamily": (2, _same_family),
    "knownUnits": (1, _known_units),
    "unitsIn": (1, _units_in),
    "unitFamilies": (1, _families),
    "quantityAdd": (2, _added),
    "quantitySubtract": (2, _subtracted),
    "quantityScaled": (2, _scaled),
    "quantityCompare": (2, _compared),
    "quantityToText": (1, _quantity_text),
}


def install_unit_library(machine: Any) -> None:
    for name, (arity, handler) in _REGISTRY.items():
        machine.define_native(name, arity, handler)


def unit_names() -> list[str]:
    return sorted(_REGISTRY)
