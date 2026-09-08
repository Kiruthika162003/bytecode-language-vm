from __future__ import annotations

import pytest

from ember.errors import Syntax
from ember.numberparse import parse


class TestIntegers:
    def test_a_plain_decimal_integer(self):
        assert parse("42") == (42, False)

    def test_hexadecimal(self):
        assert parse("0xFF") == (255, False)

    def test_octal(self):
        assert parse("0o17") == (15, False)

    def test_binary(self):
        assert parse("0b1010") == (10, False)

    def test_underscores_group_digits(self):
        assert parse("1_000_000") == (1000000, False)


class TestFloats:
    def test_a_decimal_point_makes_a_float(self):
        assert parse("3.14") == (3.14, True)

    def test_an_exponent_makes_a_float(self):
        assert parse("1e3") == (1000.0, True)

    def test_a_negative_exponent(self):
        assert parse("2.5E-3") == (0.0025, True)

    def test_underscores_in_a_float(self):
        assert parse("1_000.5") == (1000.5, True)


class TestRefusals:
    def test_a_bare_radix_prefix_is_refused(self):
        with pytest.raises(Syntax):
            parse("0x")

    def test_a_doubled_underscore_is_refused(self):
        with pytest.raises(Syntax):
            parse("1__0")

    def test_a_leading_underscore_is_refused(self):
        with pytest.raises(Syntax):
            parse("_5")

    def test_a_trailing_underscore_is_refused(self):
        with pytest.raises(Syntax):
            parse("5_")

    def test_a_bad_hex_digit_is_refused(self):
        with pytest.raises(Syntax):
            parse("0xG")

    def test_a_radix_with_a_decimal_point_is_refused(self):
        with pytest.raises(Syntax):
            parse("0x1.5")

    def test_the_empty_string_is_refused(self):
        with pytest.raises(Syntax):
            parse("")
