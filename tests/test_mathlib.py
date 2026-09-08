from __future__ import annotations

import pytest

from ember.errors import Arithmetic, TypeMismatch
from ember.interpreter import run, run_output


class TestPowersAndLogs:
    def test_pow(self):
        assert run_output("print pow(2, 10);") == ["1024"]

    def test_log_of_a_non_positive_is_refused(self):
        with pytest.raises(Arithmetic):
            run("print log(0);")

    def test_exp_and_log_round_trip(self):
        assert run_output("print log(exp(1));") == ["1.0"]


class TestRounding:
    def test_round_half_up(self):
        assert run_output("print round(2.5);") == ["3"]
        assert run_output("print round(2.4);") == ["2"]

    def test_round_of_a_negative(self):
        assert run_output("print round(-2.5);") == ["-3"]

    def test_trunc_drops_the_fraction(self):
        assert run_output("print trunc(3.9);") == ["3"]
        assert run_output("print trunc(-3.9);") == ["-3"]

    def test_sign(self):
        assert run_output("print sign(-4); print sign(0); print sign(7);") == [
            "-1",
            "0",
            "1",
        ]

    def test_clamp(self):
        assert run_output("print clamp(15, 0, 10);") == ["10"]
        assert run_output("print clamp(-5, 0, 10);") == ["0"]
        assert run_output("print clamp(5, 0, 10);") == ["5"]


class TestIntegers:
    def test_gcd(self):
        assert run_output("print gcd(48, 36);") == ["12"]

    def test_factorial(self):
        assert run_output("print factorial(5);") == ["120"]

    def test_factorial_of_a_negative_is_refused(self):
        with pytest.raises(Arithmetic):
            run("print factorial(-1);")

    def test_factorial_rejects_a_float(self):
        with pytest.raises(TypeMismatch):
            run("print factorial(4.5);")
