from __future__ import annotations

import pytest

from ember.errors import Arithmetic, TypeMismatch
from ember.interpreter import run_output, run_treewalk_output
from ember.unitlib import convert, unit_names

QUOTE = chr(34)


def quoted(text: str) -> str:
    return QUOTE + text + QUOTE


def evaluate(expression: str) -> str:
    return run_output(f"print {expression};")[0]


def quantity(amount: str, unit: str) -> str:
    return "[" + amount + ", " + quoted(unit) + "]"


class TestRegistration:
    def test_the_functions_are_named(self):
        assert "convertTo" in unit_names()
        assert "quantityAdd" in unit_names()

    def test_the_names_are_sorted(self):
        assert unit_names() == sorted(unit_names())

    def test_there_are_fourteen_of_them(self):
        assert len(unit_names()) == 14

    def test_multiplying_two_quantities_is_not_offered(self):
        # half a dimensional system would be worse than none
        assert not any("multiply" in name.lower() for name in unit_names())


class TestKnownEquivalences:
    @pytest.mark.parametrize(
        "amount,unit,target,expected",
        [
            (1, "kilometre", "metre", 1000),
            (1, "metre", "centimetre", 100),
            (1, "mile", "yard", 1760),
            (1, "yard", "foot", 3),
            (1, "foot", "inch", 12),
            (1, "hour", "second", 3600),
            (1, "day", "hour", 24),
            (1, "week", "day", 7),
            (1, "kilogram", "gram", 1000),
            (1, "tonne", "kilogram", 1000),
            (1, "pound", "ounce", 16),
            (1, "litre", "millilitre", 1000),
            (1, "gallon", "pint", 8),
        ],
    )
    def test_a_conversion_matches_its_known_value(self, amount, unit, target, expected):
        assert convert(amount, unit, target) == pytest.approx(expected)

    def test_a_round_trip_returns_the_original(self):
        for unit, target in (("mile", "metre"), ("pound", "gram"), ("hour", "second")):
            assert convert(convert(7, unit, target), target, unit) == pytest.approx(7)

    def test_converting_to_itself_changes_nothing(self):
        assert convert(5, "metre", "metre") == pytest.approx(5)


class TestTemperature:
    @pytest.mark.parametrize(
        "amount,unit,target,expected",
        [
            (0, "celsius", "kelvin", 273.15),
            (0, "kelvin", "celsius", -273.15),
            (100, "celsius", "fahrenheit", 212),
            (32, "fahrenheit", "celsius", 0),
            (-40, "celsius", "fahrenheit", -40),
            (0, "celsius", "celsius", 0),
        ],
    )
    def test_a_temperature_conversion_carries_its_offset(
        self, amount, unit, target, expected
    ):
        assert convert(amount, unit, target) == pytest.approx(expected)

    def test_temperatures_cannot_be_added(self):
        # twenty plus thirty degrees is a question about a difference, not a sum
        source = f"quantityAdd({quantity('20', 'celsius')}, {quantity('30', 'celsius')})"
        with pytest.raises(Arithmetic) as caught:
            run_output(f"print {source};")
        assert "no meaning for temperatures" in str(caught.value)

    def test_the_refusal_says_what_to_do_instead(self):
        source = f"quantityAdd({quantity('20', 'celsius')}, {quantity('30', 'celsius')})"
        with pytest.raises(Arithmetic) as caught:
            run_output(f"print {source};")
        assert "subtract to get a difference" in str(caught.value)

    def test_temperatures_can_be_subtracted(self):
        source = (
            f"quantitySubtract({quantity('100', 'celsius')}, {quantity('20', 'celsius')})"
        )
        assert evaluate(source) == '[80.0, "celsius"]'

    def test_a_temperature_cannot_be_scaled(self):
        with pytest.raises(Arithmetic):
            run_output(f"print quantityScaled({quantity('20', 'celsius')}, 2);")

    def test_temperatures_can_be_compared(self):
        source = (
            f"quantityCompare({quantity('0', 'celsius')}, {quantity('32', 'fahrenheit')})"
        )
        assert evaluate(source) == "0"


class TestRefusingAcrossFamilies:
    def test_a_length_cannot_become_a_time(self):
        # the whole point: refused at the moment it is attempted
        with pytest.raises(Arithmetic) as caught:
            convert(1, "metre", "second")
        assert "cannot be converted" in str(caught.value)

    def test_the_refusal_names_both_families(self):
        with pytest.raises(Arithmetic) as caught:
            convert(1, "metre", "second")
        message = str(caught.value)
        assert "measures length" in message
        assert "measures time" in message

    def test_a_mass_cannot_become_a_volume(self):
        with pytest.raises(Arithmetic):
            convert(1, "kilogram", "litre")

    def test_a_length_cannot_be_added_to_a_time(self):
        source = f"quantityAdd({quantity('1', 'metre')}, {quantity('1', 'second')})"
        with pytest.raises(Arithmetic):
            run_output(f"print {source};")

    def test_an_unknown_unit_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            convert(1, "furlong", "metre")
        assert "does not know the unit" in str(caught.value)


class TestQuantities:
    def test_a_quantity_holds_its_amount_and_unit(self):
        assert evaluate(f"quantity(5, {quoted('metre')})") == '[5, "metre"]'

    def test_the_amount_can_be_asked_for(self):
        assert evaluate(f"amountOf({quantity('5', 'metre')})") == "5"

    def test_the_unit_can_be_asked_for(self):
        assert evaluate(f"unitOf({quantity('5', 'metre')})") == "metre"

    def test_a_quantity_converts(self):
        source = f"convertTo({quantity('1', 'kilometre')}, {quoted('metre')})"
        assert evaluate(source) == '[1000.0, "metre"]'

    def test_adding_converts_to_the_first_unit(self):
        source = f"quantityAdd({quantity('1', 'metre')}, {quantity('50', 'centimetre')})"
        assert evaluate(source) == '[1.5, "metre"]'

    def test_subtracting_converts_too(self):
        source = f"quantitySubtract({quantity('1', 'metre')}, {quantity('50', 'centimetre')})"
        assert evaluate(source) == '[0.5, "metre"]'

    def test_scaling_multiplies_the_amount(self):
        assert evaluate(f"quantityScaled({quantity('2', 'metre')}, 3)") == '[6, "metre"]'

    def test_comparing_converts_first(self):
        source = f"quantityCompare({quantity('1', 'metre')}, {quantity('100', 'centimetre')})"
        assert evaluate(source) == "0"

    def test_a_larger_quantity_compares_above(self):
        source = f"quantityCompare({quantity('2', 'metre')}, {quantity('100', 'centimetre')})"
        assert evaluate(source) == "1"

    def test_a_smaller_quantity_compares_below(self):
        source = f"quantityCompare({quantity('1', 'metre')}, {quantity('2', 'metre')})"
        assert evaluate(source) == "-1"

    def test_a_quantity_that_is_not_a_pair_is_refused(self):
        with pytest.raises(TypeMismatch) as caught:
            run_output("print amountOf([1]);")
        assert "a number and a unit" in str(caught.value)

    def test_a_quantity_with_an_unknown_unit_is_refused(self):
        with pytest.raises(Arithmetic):
            run_output(f"print amountOf({quantity('1', 'furlong')});")

    def test_a_unit_that_is_not_a_string_is_refused(self):
        with pytest.raises(TypeMismatch):
            run_output("print quantity(1, 5);")


class TestNaming:
    def test_a_unit_reports_its_family(self):
        assert evaluate(f"familyOf({quoted('mile')})") == "length"

    def test_a_temperature_reports_its_family(self):
        assert evaluate(f"familyOf({quoted('celsius')})") == "temperature"

    def test_two_units_of_one_family_match(self):
        assert evaluate(f"sameFamily({quoted('mile')}, {quoted('inch')})") == "true"

    def test_two_units_of_different_families_do_not(self):
        assert evaluate(f"sameFamily({quoted('mile')}, {quoted('gram')})") == "false"

    def test_the_known_units_are_listed(self):
        listed = evaluate("knownUnits(0)")
        assert "metre" in listed
        assert "celsius" in listed

    def test_the_families_are_listed(self):
        listed = evaluate("unitFamilies(0)")
        assert "length" in listed
        assert "temperature" in listed

    def test_the_units_of_a_family_are_listed(self):
        assert evaluate(f"unitsIn({quoted('temperature')})") == (
            '["celsius", "fahrenheit", "kelvin"]'
        )

    def test_an_unknown_family_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output(f"print unitsIn({quoted('luminance')});")
        assert "does not know the family" in str(caught.value)

    def test_a_quantity_reads_as_a_phrase(self):
        assert evaluate(f"quantityToText({quantity('2', 'metre')})") == "2 metres"

    def test_one_of_something_is_singular(self):
        assert evaluate(f"quantityToText({quantity('1', 'metre')})") == "1 metre"


class TestBothBackendsAgree:
    @pytest.mark.parametrize(
        "expression",
        [
            f"quantity(5, {quoted('metre')})",
            f"convertTo({quantity('1', 'mile')}, {quoted('metre')})",
            f"amountOf({quantity('5', 'metre')})",
            f"unitOf({quantity('5', 'metre')})",
            f"familyOf({quoted('mile')})",
            f"sameFamily({quoted('mile')}, {quoted('gram')})",
            "knownUnits(0)",
            f"unitsIn({quoted('mass')})",
            "unitFamilies(0)",
            f"quantityAdd({quantity('1', 'metre')}, {quantity('50', 'centimetre')})",
            f"quantitySubtract({quantity('1', 'metre')}, {quantity('50', 'centimetre')})",
            f"quantityScaled({quantity('2', 'metre')}, 3)",
            f"quantityCompare({quantity('1', 'metre')}, {quantity('2', 'metre')})",
            f"quantityToText({quantity('2', 'metre')})",
        ],
    )
    def test_the_two_backends_agree(self, expression):
        source = f"print {expression};"
        assert run_output(source) == run_treewalk_output(source)
