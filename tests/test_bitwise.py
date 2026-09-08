from __future__ import annotations

import pytest

from ember.errors import Arithmetic, TypeMismatch
from ember.interpreter import run, run_output, run_treewalk_output

SHARED = [
    "print 12 & 10; print 12 | 10; print 12 ^ 10; print ~5;",
    "print 1 << 4; print 256 >> 4;",
    "print 6 & 3 | 8;",
    "print 1 | 2 ^ 3 & 4;",
    "print (2 + 3) & 7;",
    "print 1 << 2 + 1;",
    "print 255 & 0x0F; print 0b1100 ^ 0b1010;",
    "print ~0; print ~(-1);",
    "let flags = 0; flags = flags | 4; flags = flags | 1; print flags;",
]


class TestOperators:
    def test_and_or_xor(self):
        assert run_output("print 12 & 10; print 12 | 10; print 12 ^ 10;") == [
            "8",
            "14",
            "6",
        ]

    def test_not_inverts_every_bit(self):
        assert run_output("print ~5; print ~0; print ~(-1);") == ["-6", "-1", "0"]

    def test_shifts(self):
        assert run_output("print 1 << 4; print 256 >> 4;") == ["16", "16"]

    def test_a_shift_beyond_a_machine_word_still_works(self):
        # the host's integers are arbitrary precision, so nothing overflows
        assert run_output("print 1 << 70;") == [str(1 << 70)]

    def test_binary_and_hex_literals_combine(self):
        assert run_output("print 255 & 0x0F; print 0b1100 ^ 0b1010;") == ["15", "6"]


class TestPrecedence:
    def test_and_binds_tighter_than_or(self):
        # 1 | (2 ^ (3 & 4)) = 1 | (2 ^ 0) = 3
        assert run_output("print 1 | 2 ^ 3 & 4;") == ["3"]

    def test_shift_binds_looser_than_addition(self):
        # 1 << (2 + 1) = 8, not (1 << 2) + 1 = 5
        assert run_output("print 1 << 2 + 1;") == ["8"]

    def test_comparison_binds_tighter_than_bitwise_or(self):
        # (1 < 2) would be a bool, so this only works if & takes the numbers
        assert run_output("print 6 & 3 | 8;") == ["10"]

    def test_grouping_overrides(self):
        assert run_output("print (2 + 3) & 7;") == ["5"]


class TestTypeRules:
    def test_a_float_has_no_bit_pattern(self):
        with pytest.raises(TypeMismatch):
            run("print 1.5 & 2;")

    def test_a_bool_is_not_an_integer_here(self):
        with pytest.raises(TypeMismatch):
            run("print true & 1;")

    def test_a_string_is_refused(self):
        with pytest.raises(TypeMismatch):
            run('print "a" | 1;')

    def test_inverting_a_non_integer_is_refused(self):
        with pytest.raises(TypeMismatch):
            run("print ~1.5;")

    def test_a_negative_shift_is_refused(self):
        with pytest.raises(Arithmetic):
            run("print 1 << -1;")


class TestBothBackendsAgree:
    @pytest.mark.parametrize("source", SHARED)
    def test_agreement(self, source: str):
        assert run_output(source) == run_treewalk_output(source)

    @pytest.mark.parametrize("source", SHARED)
    def test_agreement_when_fully_optimized(self, source: str):
        assert run_output(source, optimize=True, peephole=True) == run_treewalk_output(
            source, optimize=True
        )
