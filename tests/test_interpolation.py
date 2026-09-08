from __future__ import annotations

import pytest

from ember import exprnodes as e
from ember.constantfold import fold_program
from ember.errors import Arithmetic, Syntax
from ember.formatter import format_program
from ember.interpolation import EXPRESSION, TEXT, has_holes, split
from ember.interpreter import run, run_output, run_treewalk_output
from ember.parser import parse
from ember.scanner import scan

DOLLAR = "$"
BACKSLASH = chr(92)

SHARED = [
    'let name = "ada"; print "hello ' + DOLLAR + '{name}";',
    (
        'let a = 1; let b = 2; print "'
        + DOLLAR + "{a} + " + DOLLAR + "{b} = " + DOLLAR + '{a + b}";'
    ),
    'print "no holes here";',
    'let xs = [1, 2, 3]; print "list has ' + DOLLAR + '{len(xs)} items";',
    'class P { init(x) { this.x = x; } } print "x is ' + DOLLAR + '{P(7).x}";',
    'let m = {"k": 9}; print "value ' + DOLLAR + '{m["k"]}";',
    'let n = 5; print "' + DOLLAR + '{n > 3 ? "big" : "small"}";',
    'print "' + DOLLAR + "{1}" + DOLLAR + "{2}" + DOLLAR + '{3}";',
    'let v = nil; print "v is ' + DOLLAR + '{v}";',
    'let t = true; print "t is ' + DOLLAR + '{t}";',
]


class TestSplitting:
    def test_text_with_no_holes_is_one_part(self):
        assert split("hello") == [(TEXT, "hello")]

    def test_a_hole_is_separated_from_its_surroundings(self):
        assert split("hi " + DOLLAR + "{name}!") == [
            (TEXT, "hi "),
            (EXPRESSION, "name"),
            (TEXT, "!"),
        ]

    def test_two_holes_touching(self):
        assert split(DOLLAR + "{a}" + DOLLAR + "{b}") == [
            (EXPRESSION, "a"),
            (EXPRESSION, "b"),
        ]

    def test_braces_inside_a_hole_are_counted(self):
        parts = split("map " + DOLLAR + '{ {"k": 1} } end')
        assert parts[1] == (EXPRESSION, ' {"k": 1} ')

    def test_a_brace_inside_a_nested_string_is_not_structure(self):
        parts = split(DOLLAR + '{ f("}") }')
        assert parts[0] == (EXPRESSION, ' f("}") ')

    def test_an_escaped_dollar_does_not_open_a_hole(self):
        body = BACKSLASH + DOLLAR + "{notahole}"
        assert split(body) == [(TEXT, body)]
        assert not has_holes(body)

    def test_an_empty_body_has_no_parts(self):
        assert split("") == []

    def test_an_unclosed_hole_is_refused(self):
        with pytest.raises(Syntax):
            split("open " + DOLLAR + "{x")

    def test_has_holes_detects_one(self):
        assert has_holes("a " + DOLLAR + "{b}")
        assert not has_holes("a b")


class TestScanningAndParsing:
    def test_a_string_without_holes_stays_a_plain_literal(self):
        program = parse(scan('print "plain";'))
        assert isinstance(program[0].expression, e.Literal)

    def test_a_string_with_a_hole_becomes_an_interpolation(self):
        program = parse(scan('print "hi ' + DOLLAR + '{name}";'))
        node = program[0].expression
        assert isinstance(node, e.Interpolation)
        assert node.parts[0] == (TEXT, "hi ")
        assert isinstance(node.parts[1][1], e.Variable)

    def test_a_hole_may_contain_any_expression(self):
        program = parse(scan('print "' + DOLLAR + '{1 + 2 * 3}";'))
        node = program[0].expression
        assert isinstance(node.parts[0][1], e.Binary)

    def test_a_quote_inside_a_hole_does_not_end_the_string(self):
        # without hole-aware scanning a map lookup by string key was impossible
        source = 'let m = {"k": 9}; print "v ' + DOLLAR + '{m["k"]}";'
        assert run_output(source) == ["v 9"]


class TestRunning:
    def test_a_value_is_written_into_the_sentence(self):
        assert run_output('let name = "ada"; print "hello ' + DOLLAR + '{name}";') == [
            "hello ada"
        ]

    def test_several_holes_in_one_string(self):
        source = (
            "let a = 1; let b = 2; print "
            + '"' + DOLLAR + "{a} + " + DOLLAR + "{b} = " + DOLLAR + '{a + b}";'
        )
        assert run_output(source) == ["1 + 2 = 3"]

    def test_every_value_kind_is_rendered_the_language_way(self):
        source = (
            "let n = nil; let t = true; let f = 2.5; let l = [1, 2];"
            ' print "' + DOLLAR + "{n} " + DOLLAR + "{t} " + DOLLAR + "{f} "
            + DOLLAR + '{l}";'
        )
        assert run_output(source) == ["nil true 2.5 [1, 2]"]

    def test_a_call_can_appear_in_a_hole(self):
        source = 'let xs = [1, 2, 3]; print "has ' + DOLLAR + '{len(xs)}";'
        assert run_output(source) == ["has 3"]

    def test_a_property_can_appear_in_a_hole(self):
        source = (
            "class P { init(x) { this.x = x; } }"
            ' print "x is ' + DOLLAR + '{P(7).x}";'
        )
        assert run_output(source) == ["x is 7"]

    def test_an_escaped_dollar_prints_literally(self):
        assert run_output('print "cost ' + BACKSLASH + DOLLAR + '{5}";') == ["cost ${5}"]


class TestFolding:
    def test_a_hole_holding_a_literal_collapses_into_the_text(self):
        program = fold_program(parse(scan('print "a ' + DOLLAR + '{"b"} c";')))
        node = program[0].expression
        assert isinstance(node, e.Literal)
        assert node.value == "a b c"

    def test_a_hole_with_a_variable_stays_an_interpolation(self):
        program = fold_program(parse(scan('print "a ' + DOLLAR + '{x} c";')))
        assert isinstance(program[0].expression, e.Interpolation)

    def test_folding_does_not_change_the_result(self):
        source = 'let n = 2; print "n is ' + DOLLAR + '{n + 1}";'
        assert run_output(source, optimize=True) == run_output(source)


class TestErrors:
    def test_an_empty_hole_is_refused(self):
        with pytest.raises(Syntax):
            run('print "' + DOLLAR + '{}";')

    def test_two_expressions_in_one_hole_are_refused(self):
        with pytest.raises(Syntax):
            run('print "' + DOLLAR + '{1 2}";')

    def test_an_unclosed_hole_is_refused(self):
        with pytest.raises(Syntax):
            run('print "open ' + DOLLAR + '{x;')

    def test_a_fault_inside_a_hole_surfaces(self):
        with pytest.raises(Arithmetic):
            run('print "' + DOLLAR + '{1 / 0}";')


class TestFormatting:
    def test_an_interpolation_is_printed_back(self):
        source = 'print "hi ' + DOLLAR + '{name}!";'
        text = format_program(parse(scan(source)))
        assert DOLLAR + "{name}" in text

    def test_formatting_stays_idempotent(self):
        source = 'let a = 1; print "v ' + DOLLAR + '{a + 1} end";'
        once = format_program(parse(scan(source)))
        assert format_program(parse(scan(once))) == once

    def test_formatting_preserves_the_result(self):
        source = 'let a = 1; print "v ' + DOLLAR + '{a + 1} end";'
        once = format_program(parse(scan(source)))
        assert run_output(once) == run_output(source)


class TestBothBackendsAgree:
    @pytest.mark.parametrize("source", SHARED)
    def test_agreement(self, source: str):
        assert run_output(source) == run_treewalk_output(source)

    @pytest.mark.parametrize("source", SHARED)
    def test_agreement_when_fully_optimized(self, source: str):
        assert run_output(source, optimize=True, peephole=True) == run_treewalk_output(
            source, optimize=True
        )
