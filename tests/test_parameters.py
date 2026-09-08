from __future__ import annotations

import pytest

from ember.chunk import Chunk
from ember.errors import Arity, Syntax
from ember.formatter import format_program
from ember.function import Function
from ember.interpreter import run, run_output, run_treewalk_output
from ember.parser import parse
from ember.scanner import scan

SHARED = [
    'fn greet(name, greeting = "hello") { return greeting + ", " + name; }'
    ' print greet("ada"); print greet("ada", "hi");',
    "fn f(a, b = 2, c = 3) { return a + b + c; }"
    " print f(1); print f(1, 20); print f(1, 20, 300);",
    "fn sum(...ns) { let t = 0; for (n in ns) t = t + n; return t; }"
    " print sum(); print sum(1); print sum(1, 2, 3, 4);",
    'fn tag(label, ...rest) { return label + ":" + str(len(rest)); }'
    ' print tag("a"); print tag("a", 1, 2);',
    "fn f(a, b = 2, ...rest) { return str(a) + str(b) + str(len(rest)); }"
    " print f(1); print f(1, 9); print f(1, 9, 7, 7);",
    "class C { init(x, y = 10) { this.x = x; this.y = y; } sum() { return this.x + this.y; } }"
    " print C(1).sum(); print C(1, 2).sum();",
    "class C { m(...xs) { return len(xs); } } print C().m(); print C().m(1, 2, 3);",
    'fn pick(...xs) { return xs; } print pick(1, "a", true);',
    "fn f(a = nil) { return a; } print f(); print f(5);",
]


class TestFunctionArityModel:
    def test_a_plain_function_requires_all_its_parameters(self):
        function = Function("f", 2, Chunk())
        assert function.required == 2
        assert function.named == 2
        assert function.accepts(2)
        assert not function.accepts(1)
        assert not function.accepts(3)
        assert function.describe_arity() == "2"

    def test_defaults_widen_the_lower_bound(self):
        function = Function("f", 3, Chunk(), defaults=(1, 2))
        assert function.required == 1
        assert [function.accepts(n) for n in range(5)] == [False, True, True, True, False]
        assert function.describe_arity() == "between 1 and 3"

    def test_a_rest_parameter_removes_the_upper_bound(self):
        function = Function("f", 2, Chunk(), is_variadic=True)
        assert function.required == 1
        assert function.named == 1
        assert all(function.accepts(n) for n in range(1, 20))
        assert not function.accepts(0)
        assert function.describe_arity() == "at least 1"

    def test_defaults_and_a_rest_parameter_combine(self):
        function = Function("f", 3, Chunk(), defaults=(2,), is_variadic=True)
        assert function.required == 1
        assert function.named == 2
        assert all(function.accepts(n) for n in range(1, 10))


class TestDefaults:
    def test_a_default_fills_a_missing_argument(self):
        source = (
            'fn greet(name, greeting = "hello") { return greeting + ", " + name; }'
            ' print greet("ada");'
        )
        assert run_output(source) == ["hello, ada"]

    def test_a_supplied_argument_wins(self):
        source = (
            'fn greet(name, greeting = "hello") { return greeting + ", " + name; }'
            ' print greet("ada", "hi");'
        )
        assert run_output(source) == ["hi, ada"]

    def test_defaults_fill_from_the_right(self):
        source = (
            "fn f(a, b = 2, c = 3) { return str(a) + str(b) + str(c); }"
            " print f(1); print f(1, 20); print f(1, 20, 300);"
        )
        assert run_output(source) == ["123", "1203", "120300"]

    def test_every_literal_kind_can_be_a_default(self):
        source = (
            "fn f(a = 1, b = 2.5, c = true, d = nil, e = \"s\") "
            "{ return str(a) + str(b) + str(c) + str(d) + e; } print f();"
        )
        assert run_output(source) == ["12.5truenils"]

    def test_a_default_works_on_an_initializer(self):
        source = (
            "class C { init(x, y = 10) { this.x = x; this.y = y; } "
            "sum() { return this.x + this.y; } } print C(1).sum(); print C(1, 2).sum();"
        )
        assert run_output(source) == ["11", "3"]


class TestVariadic:
    def test_a_rest_parameter_gathers_nothing(self):
        assert run_output("fn f(...xs) { return len(xs); } print f();") == ["0"]

    def test_a_rest_parameter_gathers_everything_extra(self):
        source = (
            "fn f(a, ...xs) { return str(a) + str(len(xs)); }"
            " print f(1); print f(1, 2, 3);"
        )
        assert run_output(source) == ["10", "12"]

    def test_the_gathered_arguments_are_an_ordinary_list(self):
        assert run_output('fn f(...xs) { return xs; } print f(1, "a", true);') == [
            '[1, "a", true]'
        ]

    def test_a_rest_parameter_can_be_iterated(self):
        source = (
            "fn sum(...ns) { let t = 0; for (n in ns) t = t + n; return t; }"
            " print sum(1, 2, 3, 4);"
        )
        assert run_output(source) == ["10"]

    def test_defaults_and_a_rest_parameter_together(self):
        source = (
            "fn f(a, b = 2, ...rest) { return str(a) + str(b) + str(len(rest)); }"
            " print f(1); print f(1, 9); print f(1, 9, 7, 7);"
        )
        assert run_output(source) == ["120", "190", "192"]

    def test_a_method_can_be_variadic(self):
        source = (
            "class C { m(...xs) { return len(xs); } }"
            " print C().m(); print C().m(1, 2, 3);"
        )
        assert run_output(source) == ["0", "3"]


class TestArityErrors:
    def test_too_few_arguments_is_refused(self):
        with pytest.raises(Arity):
            run("fn f(a, b) { return a; } f(1);")

    def test_below_the_required_count_with_defaults_is_refused(self):
        with pytest.raises(Arity):
            run("fn f(a, b = 1) { return a; } f();")

    def test_too_many_arguments_is_refused(self):
        with pytest.raises(Arity):
            run("fn f(a) { return a; } f(1, 2);")

    def test_a_variadic_still_requires_its_named_parameters(self):
        with pytest.raises(Arity):
            run("fn f(a, ...r) { return a; } f();")

    def test_the_message_describes_the_range(self):
        with pytest.raises(Arity) as caught:
            run("fn f(a, b = 1) { return a; } f();")
        assert "between 1 and 2" in str(caught.value)

    def test_the_message_describes_an_open_range(self):
        with pytest.raises(Arity) as caught:
            run("fn f(a, ...r) { return a; } f();")
        assert "at least 1" in str(caught.value)


class TestDeclarationRules:
    def test_a_parameter_without_a_default_cannot_follow_one_with(self):
        with pytest.raises(Syntax):
            run("fn f(a = 1, b) { return a; }")

    def test_nothing_may_follow_the_rest_parameter(self):
        with pytest.raises(Syntax):
            run("fn f(...r, a) { return a; }")

    def test_a_rest_parameter_needs_a_name(self):
        with pytest.raises(Syntax):
            run("fn f(...) { return 1; }")

    def test_a_default_must_be_a_literal(self):
        # it travels with the compiled function, so it cannot be computed
        with pytest.raises(Syntax) as caught:
            run("fn f(a = someName) { return a; }")
        assert "must be a literal" in str(caught.value)

    def test_a_computed_default_is_refused_even_when_constant(self):
        with pytest.raises(Syntax):
            run("fn f(a = 1 + 1) { return a; }")


class TestFormatting:
    def test_defaults_and_rest_are_printed_back(self):
        source = 'fn f(a, b = 2, ...rest) { return a; }'
        text = format_program(parse(scan(source)))
        assert "fn f(a, b = 2, ...rest) {" in text

    def test_formatting_stays_idempotent(self):
        source = 'fn f(a, b = "x", ...rest) { return a; } fn g(...xs) { return xs; }'
        once = format_program(parse(scan(source)))
        assert format_program(parse(scan(once))) == once


class TestBothBackendsAgree:
    @pytest.mark.parametrize("source", SHARED)
    def test_agreement(self, source: str):
        assert run_output(source) == run_treewalk_output(source)

    @pytest.mark.parametrize("source", SHARED)
    def test_agreement_when_fully_optimized(self, source: str):
        assert run_output(source, optimize=True, peephole=True) == run_treewalk_output(
            source, optimize=True
        )
