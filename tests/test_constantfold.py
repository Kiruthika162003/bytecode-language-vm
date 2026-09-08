from __future__ import annotations

from ember import exprnodes as e
from ember import stmtnodes as s
from ember.constantfold import fold_expression, fold_program
from ember.parser import parse
from ember.scanner import scan


def first_expression(source: str) -> e.Expr:
    program = fold_program(parse(scan(source)))
    assert isinstance(program[0], s.ExpressionStmt)
    return program[0].expression


def folded_value(source: str):
    node = first_expression(source)
    assert isinstance(node, e.Literal), f"not folded: {node}"
    return node.value


class TestArithmetic:
    def test_a_whole_arithmetic_expression_folds(self):
        assert folded_value("1 + 2 * 3;") == 7

    def test_subtraction_and_division_fold(self):
        assert folded_value("10 - 4;") == 6
        assert folded_value("9 / 2;") == 4.5

    def test_remainder_folds(self):
        assert folded_value("17 % 5;") == 2

    def test_nested_grouping_folds(self):
        assert folded_value("((2 + 3) * (4 - 1));") == 15


class TestStringsAndComparisons:
    def test_string_concatenation_folds(self):
        assert folded_value('"a" + "b";') == "ab"

    def test_numeric_comparison_folds(self):
        assert folded_value("2 * 3 < 10 - 1;") is True

    def test_string_comparison_folds(self):
        assert folded_value('"a" < "b";') is True

    def test_equality_folds(self):
        assert folded_value("1 == 1.0;") is True
        assert folded_value("1 == true;") is False


class TestUnary:
    def test_negation_folds(self):
        assert folded_value("-(-5);") == 5

    def test_not_folds(self):
        assert folded_value("not false;") is True
        assert folded_value("!nil;") is True


class TestLogical:
    def test_a_false_and_collapses_to_false(self):
        assert folded_value('false and "x";') is False

    def test_a_true_and_collapses_to_the_right_side(self):
        assert folded_value('true and "x";') == "x"

    def test_a_true_or_collapses_to_true(self):
        assert folded_value('true or "x";') is True

    def test_a_false_or_collapses_to_the_right_side(self):
        assert folded_value('false or "y";') == "y"


class TestDeliberatelyNotFolded:
    def test_division_by_zero_is_left_to_run_time(self):
        node = first_expression("1 / 0;")
        assert isinstance(node, e.Binary)

    def test_remainder_by_zero_is_left_to_run_time(self):
        assert isinstance(first_expression("1 % 0;"), e.Binary)

    def test_a_mixed_type_add_is_left_alone(self):
        # "a" + 0 is a type error the program is entitled to receive
        assert isinstance(first_expression('"a" + 0;'), e.Binary)

    def test_adding_zero_is_not_simplified_away(self):
        # unsound here: plus is overloaded, so x + 0 is not always x
        node = first_expression("someVariable + 0;")
        assert isinstance(node, e.Binary)

    def test_multiplying_by_one_is_not_simplified_away(self):
        assert isinstance(first_expression("someVariable * 1;"), e.Binary)

    def test_a_variable_is_never_folded(self):
        assert isinstance(first_expression("x + 1;"), e.Binary)


class TestFoldingReachesEverywhere:
    def test_it_folds_inside_a_function_body(self):
        program = fold_program(parse(scan("fn f() { return 2 * 4; }")))
        body = program[0].body
        assert isinstance(body[0].value, e.Literal)
        assert body[0].value.value == 8

    def test_it_folds_inside_a_method_body(self):
        program = fold_program(parse(scan("class C { m() { return 3 + 4; } }")))
        method_body = program[0].methods[0].body
        assert method_body[0].value.value == 7

    def test_it_folds_a_let_initializer(self):
        program = fold_program(parse(scan("let x = 6 * 7;")))
        assert program[0].initializer.value == 42

    def test_it_folds_inside_a_list_literal(self):
        node = fold_expression(parse(scan("[1 + 1, 2 * 2];"))[0].expression)
        assert [element.value for element in node.elements] == [2, 4]
