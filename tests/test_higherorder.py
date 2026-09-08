from __future__ import annotations

import pytest

from ember.errors import Arithmetic, IndexRange, TypeMismatch
from ember.higherorder import higher_order_names
from ember.interpreter import run, run_output, run_treewalk_output

DOUBLE = "fn dbl(x) { return x * 2; } "
EVEN = "fn even(x) { return x % 2 == 0; } "
ADD = "fn add(a, b) { return a + b; } "

SHARED = [
    DOUBLE + "print map([1, 2, 3], dbl);",
    EVEN + "print filter([1, 2, 3, 4, 5, 6], even);",
    ADD + "print reduce([1, 2, 3, 4], add, 0);",
    (
        "fn big(x) { return x > 3; }"
        " print find([1, 2, 5, 7], big); print find([1, 2], big);"
    ),
    "fn pos(x) { return x > 0; } print every([1, 2], pos); print some([-1, 2], pos);",
    "fn odd(x) { return x % 2 == 1; } print count_where([1, 2, 3, 4, 5], odd);",
    "fn odd(x) { return x % 2 == 1; } print index_where([2, 4, 5], odd);",
    "fn neg(x) { return -x; } print sort_by([3, 1, 2], neg);",
    "fn small(x) { return x < 3; } print partition([1, 2, 3, 4], small);",
    "print remove_all([1, 2, 1, 3], 1);",
    "fn sq(i) { return i * i; } print times(5, sq);",
    "fn adder(n) { fn a(x) { return x + n; } return a; } print map([1, 2, 3], adder(10));",
    (
        "class D { init(k) { this.k = k; } scale(x) { return x * this.k; } }"
        " let d = D(3); print map([1, 2], d.scale);"
    ),
    DOUBLE + EVEN + "print filter(map([1, 2, 3, 4], dbl), even);",
    (
        "fn fact(n) { if (n <= 1) return 1; return n * fact(n - 1); }"
        " print map([1, 2, 3, 4, 5], fact);"
    ),
]


class TestMapFilterReduce:
    def test_map_applies_to_every_element(self):
        assert run_output(DOUBLE + "print map([1, 2, 3], dbl);") == ["[2, 4, 6]"]

    def test_map_leaves_the_input_alone(self):
        source = DOUBLE + "let a = [1, 2]; map(a, dbl); print a;"
        assert run_output(source) == ["[1, 2]"]

    def test_filter_keeps_the_matching_elements(self):
        assert run_output(EVEN + "print filter([1, 2, 3, 4], even);") == ["[2, 4]"]

    def test_reduce_folds_with_a_starting_value(self):
        assert run_output(ADD + "print reduce([1, 2, 3, 4], add, 10);") == ["20"]

    def test_reduce_over_an_empty_list_returns_the_start(self):
        assert run_output(ADD + "print reduce([], add, 7);") == ["7"]


class TestSearching:
    def test_find_returns_the_first_match(self):
        assert run_output("fn big(x) { return x > 3; } print find([1, 5, 7], big);") == ["5"]

    def test_find_returns_nil_when_nothing_matches(self):
        # not finding something is an ordinary outcome, not a fault
        assert run_output("fn big(x) { return x > 9; } print find([1, 2], big);") == ["nil"]

    def test_every_and_some(self):
        source = (
            "fn pos(x) { return x > 0; }"
            " print every([1, 2], pos); print every([1, -1], pos);"
        )
        assert run_output(source) == ["true", "false"]

    def test_index_where_reports_minus_one_when_absent(self):
        source = "fn odd(x) { return x % 2 == 1; } print index_where([2, 4], odd);"
        assert run_output(source) == ["-1"]


class TestOrderingAndGrouping:
    def test_sort_by_uses_the_computed_key(self):
        assert run_output("fn neg(x) { return -x; } print sort_by([3, 1, 2], neg);") == [
            "[3, 2, 1]"
        ]

    def test_sort_by_is_stable_for_equal_keys(self):
        # every element has the same key, so the input order must survive
        source = "fn same(x) { return 0; } print sort_by([3, 1, 2], same);"
        assert run_output(source) == ["[3, 1, 2]"]

    def test_partition_splits_into_matching_and_rest(self):
        source = "fn small(x) { return x < 3; } print partition([1, 2, 3, 4], small);"
        assert run_output(source) == ["[[1, 2], [3, 4]]"]

    def test_times_calls_with_each_index(self):
        assert run_output("fn sq(i) { return i * i; } print times(4, sq);") == [
            "[0, 1, 4, 9]"
        ]


class TestCallableArguments:
    def test_a_closure_can_be_passed(self):
        source = (
            "fn adder(n) { fn a(x) { return x + n; } return a; }"
            " print map([1, 2], adder(10));"
        )
        assert run_output(source) == ["[11, 12]"]

    def test_a_bound_method_can_be_passed(self):
        source = (
            "class D { init(k) { this.k = k; } scale(x) { return x * this.k; } }"
            " print map([1, 2], D(3).scale);"
        )
        assert run_output(source) == ["[3, 6]"]

    def test_a_recursive_function_can_be_passed(self):
        source = (
            "fn fact(n) { if (n <= 1) return 1; return n * fact(n - 1); }"
            " print map([3, 4], fact);"
        )
        assert run_output(source) == ["[6, 24]"]

    def test_higher_order_calls_nest(self):
        source = DOUBLE + EVEN + "print filter(map([1, 2, 3, 4], dbl), even);"
        assert run_output(source) == ["[2, 4, 6, 8]"]


class TestErrors:
    def test_a_non_function_second_argument_is_refused(self):
        with pytest.raises(TypeMismatch):
            run("print map([1, 2], 5);")

    def test_a_non_list_first_argument_is_refused(self):
        with pytest.raises(TypeMismatch):
            run(DOUBLE + "print map(5, dbl);")

    def test_sort_by_needs_a_numeric_key(self):
        with pytest.raises(TypeMismatch):
            run('fn tag(x) { return "k"; } print sort_by([1, 2], tag);')

    def test_a_negative_times_count_is_refused(self):
        with pytest.raises(IndexRange):
            run("fn f(i) { return i; } print times(-1, f);")

    def test_an_error_inside_the_callback_propagates(self):
        # the fault surfaces from inside the re-entered dispatch loop
        with pytest.raises(Arithmetic):
            run("fn bad(x) { return x / 0; } print map([1], bad);")


class TestRegistry:
    def test_every_name_is_installed(self):
        machine = run("print 1;")
        for name in higher_order_names():
            assert name in machine.globals, name

    def test_the_machine_aware_natives_are_marked(self):
        machine = run("print 1;")
        assert machine.globals["map"].needs_machine
        # a first-order native is not marked, so it is called without the machine
        assert not machine.globals["len"].needs_machine


class TestBothBackendsAgree:
    @pytest.mark.parametrize("source", SHARED)
    def test_agreement(self, source: str):
        assert run_output(source) == run_treewalk_output(source)
