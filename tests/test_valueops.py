from __future__ import annotations

from ember.valueops import is_truthy, stringify, type_name, values_equal


class TestTruthiness:
    def test_only_false_and_nil_are_falsey(self):
        assert not is_truthy(None)
        assert not is_truthy(False)

    def test_everything_else_is_truthy(self):
        for value in (True, 0, 0.0, "", "x", [], [1], {}):
            assert is_truthy(value)


class TestEquality:
    def test_a_number_is_not_equal_to_a_boolean(self):
        assert not values_equal(1, True)
        assert not values_equal(0, False)

    def test_ints_and_floats_compare_numerically(self):
        assert values_equal(1, 1.0)
        assert not values_equal(1, 2)

    def test_nil_equals_only_nil(self):
        assert values_equal(None, None)
        assert not values_equal(None, 0)

    def test_strings_and_lists_compare_by_value(self):
        assert values_equal("a", "a")
        assert values_equal([1, 2], [1, 2])
        assert not values_equal([1], [1, 2])

    def test_booleans_compare_to_booleans(self):
        assert values_equal(True, True)
        assert not values_equal(True, False)


class TestTypeName:
    def test_each_value_reports_its_language_type(self):
        assert type_name(None) == "nil"
        assert type_name(True) == "bool"
        assert type_name(5) == "int"
        assert type_name(5.0) == "float"
        assert type_name("s") == "string"
        assert type_name([1]) == "list"
        assert type_name({"a": 1}) == "map"


class TestStringify:
    def test_literals_print_the_language_way(self):
        assert stringify(None) == "nil"
        assert stringify(True) == "true"
        assert stringify(False) == "false"

    def test_a_whole_float_keeps_its_point(self):
        assert stringify(5.0) == "5.0"
        assert stringify(5.5) == "5.5"

    def test_a_plain_string_prints_unquoted(self):
        assert stringify("hi") == "hi"

    def test_collection_elements_are_quoted(self):
        assert stringify([1, "a", True]) == '[1, "a", true]'
        assert stringify({"k": 1}) == '{"k": 1}'
