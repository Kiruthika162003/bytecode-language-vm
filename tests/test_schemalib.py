from __future__ import annotations

import pytest

from ember.errors import Arithmetic, TypeMismatch
from ember.interpreter import run_output, run_treewalk_output
from ember.schemalib import Problem, Result, schema_names, validate


def evaluate(expression: str) -> str:
    return run_output(f"print {expression};")[0]


class TestRegistration:
    def test_the_functions_are_named(self):
        assert "isValid" in schema_names()
        assert "schemaProblems" in schema_names()

    def test_the_names_are_sorted(self):
        assert schema_names() == sorted(schema_names())

    def test_there_are_eight_of_them(self):
        assert len(schema_names()) == 8


class TestTypes:
    @pytest.mark.parametrize(
        "value,kind",
        [
            (1, "int"),
            (1.5, "float"),
            (1, "number"),
            (1.5, "number"),
            ("a", "string"),
            (True, "bool"),
            (None, "nil"),
            ([1], "list"),
            ({"a": 1}, "map"),
            ("anything", "any"),
        ],
    )
    def test_a_matching_type_passes(self, value, kind):
        assert validate(value, {"type": kind}).valid

    @pytest.mark.parametrize(
        "value,kind",
        [
            ("a", "int"),
            (1, "string"),
            (1, "float"),
            (1.5, "int"),
            (True, "int"),
            (1, "bool"),
            (None, "int"),
            ([1], "map"),
            ({"a": 1}, "list"),
        ],
    )
    def test_a_mismatched_type_fails(self, value, kind):
        assert not validate(value, {"type": kind}).valid

    def test_a_boolean_is_not_a_number(self):
        # the language keeps them apart, and so does the schema
        assert not validate(True, {"type": "number"}).valid

    def test_the_message_names_both_types(self):
        found = validate("a", {"type": "int"})
        assert "expected int but found string" in found.problems[0].message

    def test_a_schema_with_no_type_accepts_anything(self):
        assert validate("anything", {}).valid
        assert validate(1, {}).valid


class TestBounds:
    def test_a_number_inside_its_bounds_passes(self):
        assert validate(5, {"type": "int", "least": 0, "most": 10}).valid

    def test_a_number_below_the_least_fails(self):
        found = validate(-1, {"type": "int", "least": 0})
        assert "below the least allowed" in found.problems[0].message

    def test_a_number_above_the_most_fails(self):
        found = validate(11, {"type": "int", "most": 10})
        assert "above the most allowed" in found.problems[0].message

    def test_a_number_on_the_boundary_passes(self):
        assert validate(0, {"type": "int", "least": 0, "most": 0}).valid

    def test_a_float_can_be_bounded_too(self):
        assert not validate(1.5, {"type": "float", "most": 1}).valid

    def test_both_bounds_can_fail_at_once_only_one_way(self):
        found = validate(-1, {"type": "int", "least": 0, "most": 10})
        assert found.count == 1


class TestLengths:
    def test_a_string_of_the_right_length_passes(self):
        assert validate("abc", {"type": "string", "shortest": 1, "longest": 5}).valid

    def test_a_string_too_short_fails(self):
        found = validate("", {"type": "string", "shortest": 1})
        assert "shorter than the 1 required" in found.problems[0].message

    def test_a_string_too_long_fails(self):
        found = validate("abcdef", {"type": "string", "longest": 3})
        assert "longer than the 3 allowed" in found.problems[0].message

    def test_a_list_can_be_bounded(self):
        assert not validate([1, 2, 3], {"type": "list", "longest": 2}).valid

    def test_a_map_can_be_bounded(self):
        assert not validate({}, {"type": "map", "shortest": 1}).valid

    def test_a_length_on_a_number_is_ignored(self):
        assert validate(5, {"type": "int", "shortest": 100}).valid


class TestAllowedValues:
    def test_an_allowed_value_passes(self):
        assert validate(2, {"type": "int", "allowed": [1, 2, 3]}).valid

    def test_a_value_outside_the_set_fails(self):
        found = validate(9, {"type": "int", "allowed": [1, 2, 3]})
        assert "is not one of" in found.problems[0].message

    def test_strings_can_be_restricted(self):
        schema = {"type": "string", "allowed": ["red", "green"]}
        assert validate("red", schema).valid
        assert not validate("blue", schema).valid

    def test_the_message_lists_what_was_allowed(self):
        found = validate("blue", {"type": "string", "allowed": ["red", "green"]})
        assert "red, green" in found.problems[0].message

    def test_allowed_values_that_are_not_a_list_are_refused(self):
        with pytest.raises(TypeMismatch) as caught:
            validate(1, {"type": "int", "allowed": 1})
        assert "given as a list" in str(caught.value)


class TestLists:
    def test_every_element_is_checked(self):
        schema = {"type": "list", "elements": {"type": "int"}}
        assert validate([1, 2, 3], schema).valid

    def test_a_bad_element_is_reported_with_its_index(self):
        schema = {"type": "list", "elements": {"type": "int"}}
        found = validate([1, "a", 3], schema)
        assert found.problems[0].path == "[1]"

    def test_several_bad_elements_are_all_reported(self):
        schema = {"type": "list", "elements": {"type": "int"}}
        assert validate(["a", "b"], schema).count == 2

    def test_an_empty_list_passes_any_element_schema(self):
        assert validate([], {"type": "list", "elements": {"type": "int"}}).valid

    def test_nested_lists_report_a_nested_path(self):
        schema = {
            "type": "list",
            "elements": {"type": "list", "elements": {"type": "int"}},
        }
        found = validate([[1], ["a"]], schema)
        assert found.problems[0].path == "[1].[0]"


PERSON = {
    "type": "map",
    "fields": {
        "name": {"type": "string", "shortest": 1},
        "age": {"type": "int", "least": 0},
        "email": {"type": "string", "optional": True},
    },
}


class TestMapFields:
    def test_a_document_that_fits_passes(self):
        assert validate({"name": "Ada", "age": 36}, PERSON).valid

    def test_an_optional_field_can_be_present(self):
        value = {"name": "Ada", "age": 36, "email": "a@b"}
        assert validate(value, PERSON).valid

    def test_a_missing_required_field_is_reported(self):
        found = validate({"age": 36}, PERSON)
        assert found.problems[0].path == "name"
        assert "missing" in found.problems[0].message

    def test_a_missing_optional_field_is_not_reported(self):
        assert validate({"name": "Ada", "age": 36}, PERSON).valid

    def test_a_field_holding_nil_is_not_the_same_as_absent(self):
        # a document that omitted something and one that said nothing differ
        found = validate({"name": "Ada", "age": 36, "email": None}, PERSON)
        assert not found.valid
        assert "expected string but found nil" in found.problems[0].message

    def test_a_field_of_the_wrong_type_is_reported_with_its_name(self):
        found = validate({"name": 1, "age": 36}, PERSON)
        assert found.problems[0].path == "name"

    def test_several_bad_fields_are_all_reported(self):
        found = validate({"name": "", "age": -1}, PERSON)
        assert found.count == 2

    def test_an_unexpected_field_passes_by_default(self):
        # data usually arrives from something that adds fields over time
        value = {"name": "Ada", "age": 36, "surprise": 1}
        assert validate(value, PERSON).valid

    def test_strictness_refuses_an_unexpected_field(self):
        strict = dict(PERSON)
        strict["strict"] = True
        value = {"name": "Ada", "age": 36, "surprise": 1}
        found = validate(value, strict)
        assert not found.valid
        assert "not in the schema" in found.problems[0].message

    def test_nested_maps_report_a_nested_path(self):
        schema = {
            "type": "map",
            "fields": {"inner": {"type": "map", "fields": {"n": {"type": "int"}}}},
        }
        found = validate({"inner": {"n": "a"}}, schema)
        assert found.problems[0].path == "inner.n"

    def test_fields_that_are_not_a_map_are_refused(self):
        with pytest.raises(TypeMismatch) as caught:
            validate({}, {"type": "map", "fields": [1]})
        assert "given as a map" in str(caught.value)


class TestBadSchemas:
    def test_a_schema_that_is_not_a_map_is_refused(self):
        with pytest.raises(TypeMismatch) as caught:
            validate(1, "int")
        assert "a map describing what is expected" in str(caught.value)

    def test_an_unknown_setting_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            validate(1, {"colour": "red"})
        assert "not a schema setting" in str(caught.value)

    def test_the_refusal_lists_the_settings(self):
        with pytest.raises(Arithmetic) as caught:
            validate(1, {"colour": "red"})
        assert "optional" in str(caught.value)

    def test_an_unknown_type_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            validate(1, {"type": "integer"})
        assert "not a type a schema knows" in str(caught.value)

    def test_a_non_string_key_is_refused(self):
        with pytest.raises(TypeMismatch):
            validate(1, {1: "int"})

    def test_a_program_can_test_a_schema(self):
        assert evaluate('isSchema({"type": "int"})') == "true"
        assert evaluate("isSchema(5)") == "false"

    def test_an_unknown_setting_makes_it_not_a_schema(self):
        assert evaluate('isSchema({"colour": "red"})') == "false"


class TestReporting:
    def test_a_valid_result_says_so(self):
        assert validate(1, {"type": "int"}).render() == ["the value fits the schema"]

    def test_a_problem_renders_with_its_path(self):
        assert Problem("a.b", "went wrong").render() == "a.b: went wrong"

    def test_a_problem_at_the_top_names_the_value(self):
        assert Problem("", "went wrong").render() == "the value: went wrong"

    def test_a_valid_result_summarises_as_valid(self):
        assert validate(1, {"type": "int"}).summary() == "valid"

    def test_one_problem_reads_in_the_singular(self):
        assert validate("a", {"type": "int"}).summary() == "1 problem"

    def test_several_problems_read_in_the_plural(self):
        schema = {"type": "list", "elements": {"type": "int"}}
        assert validate(["a", "b"], schema).summary() == "2 problems"

    def test_an_empty_result_is_valid(self):
        assert Result().valid

    def test_the_paths_can_be_asked_for(self):
        schema = {"type": "list", "elements": {"type": "int"}}
        assert validate(["a", "b"], schema).paths() == ["[0]", "[1]"]


class TestFromPrograms:
    def test_a_program_can_validate(self):
        source = 'print isValid(1, {"type": "int"});'
        assert run_output(source) == ["true"]

    def test_a_program_gets_nothing_when_valid(self):
        source = 'print schemaProblems(1, {"type": "int"});'
        assert run_output(source) == ["[]"]

    def test_a_program_gets_the_problems_when_not(self):
        source = 'print schemaProblems("a", {"type": "int"});'
        assert "expected int" in run_output(source)[0]

    def test_a_program_can_count_the_problems(self):
        source = 'print schemaProblemCount("a", {"type": "int"});'
        assert run_output(source) == ["1"]

    def test_a_program_can_ask_for_a_summary(self):
        source = 'print explainSchema("a", {"type": "int"});'
        assert run_output(source) == ["1 problem"]

    def test_a_program_can_list_the_settings(self):
        assert "optional" in evaluate("schemaSettings(0)")

    def test_a_program_can_list_the_types(self):
        assert "string" in evaluate("schemaTypes(0)")

    def test_a_realistic_document_is_checked(self):
        quote = chr(34)
        schema = (
            "{" + quote + "type" + quote + ": " + quote + "map" + quote + ", "
            + quote + "fields" + quote + ": {"
            + quote + "id" + quote + ": {" + quote + "type" + quote + ": "
            + quote + "int" + quote + "}}}"
        )
        good = "{" + quote + "id" + quote + ": 1}"
        bad = "{" + quote + "id" + quote + ": " + quote + "one" + quote + "}"
        assert run_output(f"print isValid({good}, {schema});") == ["true"]
        assert run_output(f"print isValid({bad}, {schema});") == ["false"]


class TestBothBackendsAgree:
    @pytest.mark.parametrize(
        "expression",
        [
            'isValid(1, {"type": "int"})',
            'isValid("a", {"type": "int"})',
            'schemaProblems("a", {"type": "int"})',
            'schemaProblemCount("a", {"type": "int"})',
            'explainSchema("a", {"type": "int"})',
            'schemaPaths([1, "a"], {"type": "list", "elements": {"type": "int"}})',
            'isSchema({"type": "int"})',
            "schemaSettings(0)",
            "schemaTypes(0)",
        ],
    )
    def test_the_two_backends_agree(self, expression):
        source = f"print {expression};"
        assert run_output(source) == run_treewalk_output(source)
