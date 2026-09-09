from __future__ import annotations

import pytest

from ember.generator import program_for
from ember.traces.verifytrace import CORPUS
from ember.typecheck import Finding, check, is_clean, report

NEWLINE = chr(10)


def kinds_of(source: str) -> list[str]:
    return [found.kind for found in check(source)]


class TestNoFalsePositives:
    @pytest.mark.parametrize("source", CORPUS)
    def test_a_known_good_program_reports_nothing(self, source):
        assert check(source) == []

    @pytest.mark.parametrize("seed", range(30))
    def test_a_generated_program_reports_nothing(self, seed):
        # the generator only builds valid programs, so any finding here is a bug
        assert check(program_for(seed)) == []

    def test_a_clean_program_is_reported_as_clean(self):
        assert is_clean("let a = 1; print a + 2;")

    def test_a_faulty_program_is_not(self):
        assert not is_clean('print "a" - 1;')


class TestArithmetic:
    def test_subtracting_from_a_string_is_caught(self):
        assert kinds_of('print "a" - 1;') == ["not-a-number"]

    def test_multiplying_a_bool_is_caught(self):
        assert kinds_of("print true * 2;") == ["not-a-number"]

    def test_dividing_by_a_string_is_caught(self):
        assert kinds_of('print 1 / "a";') == ["not-a-number"]

    def test_both_operands_wrong_are_both_reported(self):
        assert kinds_of('print "a" - "b";') == ["not-a-number", "not-a-number"]

    def test_the_message_names_the_side(self):
        found = check('print "a" - 1;')[0]
        assert "left operand is a string" in found.message

    def test_a_bitwise_operator_needs_numbers(self):
        assert kinds_of('print "a" & 1;') == ["not-a-number"]

    def test_a_shift_needs_numbers(self):
        assert kinds_of('print "a" << 1;') == ["not-a-number"]

    def test_numbers_are_fine(self):
        assert check("print 1 - 2 * 3 / 4 % 5;") == []

    def test_negating_a_string_is_caught(self):
        assert kinds_of('print -"a";') == ["not-a-number"]

    def test_complementing_a_string_is_caught(self):
        assert kinds_of('print ~"a";') == ["not-a-number"]

    def test_negating_a_number_is_fine(self):
        assert check("print -5;") == []

    def test_not_accepts_anything(self):
        # truthiness is defined for every value, so not is never a mistake
        assert check('print !"a"; print !nil; print !1;') == []


class TestAddition:
    def test_two_numbers_add(self):
        assert check("print 1 + 2;") == []

    def test_two_strings_add(self):
        assert check('print "a" + "b";') == []

    def test_two_lists_add(self):
        assert check("print [1] + [2];") == []

    def test_a_string_and_a_number_do_not(self):
        assert kinds_of('print "a" + 1;') == ["cannot-add"]

    def test_a_bool_and_a_number_do_not(self):
        assert kinds_of("print true + 1;") == ["cannot-add"]

    def test_the_message_says_what_addition_joins(self):
        found = check('print "a" + 1;')[0]
        assert "two numbers" in found.message
        assert "two strings" in found.message


class TestComparing:
    def test_comparing_a_string_with_a_number_is_caught(self):
        assert kinds_of('print "a" < 1;') == ["cannot-compare"]

    def test_ordering_two_bools_is_caught(self):
        assert kinds_of("print true < false;") == ["not-orderable"]

    def test_ordering_two_lists_is_caught(self):
        assert kinds_of("print [1] < [2];") == ["not-orderable"]

    def test_ordering_two_numbers_is_fine(self):
        assert check("print 1 < 2; print 1 >= 2;") == []

    def test_ordering_two_strings_is_fine(self):
        assert check('print "a" < "b";') == []

    def test_the_message_names_both_kinds(self):
        found = check('print "a" < 1;')[0]
        assert "a string with a number" in found.message


class TestEquality:
    def test_comparing_a_string_with_a_number_is_caught(self):
        assert kinds_of('print "a" == 1;') == ["never-equal"]

    def test_inequality_is_caught_too(self):
        assert kinds_of('print "a" != 1;') == ["never-equal"]

    def test_two_of_a_kind_are_fine(self):
        assert check('print "a" == "b"; print 1 == 2;') == []

    def test_comparing_with_nil_is_always_allowed(self):
        # comparing with nil is how a program asks whether something is nil
        assert check("let x = 1; print x == nil;") == []

    def test_comparing_nil_on_the_left_is_allowed(self):
        assert check('let x = "a"; print nil != x;') == []

    def test_two_bools_can_be_equal(self):
        assert check("print true == false;") == []

    def test_the_message_explains_why_it_matters(self):
        found = check('print "a" == 1;')[0]
        assert "always gives the same answer" in found.message


class TestCalling:
    def test_calling_a_number_is_caught(self):
        assert kinds_of("let n = 1; print n();") == ["not-callable"]

    def test_calling_a_string_is_caught(self):
        assert kinds_of('let s = "a"; print s();') == ["not-callable"]

    def test_calling_a_list_is_caught(self):
        assert kinds_of("let a = [1]; print a();") == ["not-callable"]

    def test_calling_a_function_is_fine(self):
        assert check("fn f() { return 1; } print f();") == []

    def test_calling_a_class_is_fine(self):
        assert check("class C { } print C();") == []

    def test_calling_an_unknown_is_not_reported(self):
        assert check("fn f(g) { return g(); }") == []

    def test_the_message_says_what_can_be_called(self):
        found = check("let n = 1; print n();")[0]
        assert "only a function or a class" in found.message


class TestArity:
    def test_too_few_arguments_are_caught(self):
        assert kinds_of("fn f(a, b) { return a; } print f(1);") == ["wrong-arity"]

    def test_too_many_arguments_are_caught(self):
        assert kinds_of("fn f(a) { return a; } print f(1, 2);") == ["wrong-arity"]

    def test_the_right_count_is_fine(self):
        assert check("fn f(a, b) { return a; } print f(1, 2);") == []

    def test_one_argument_reads_in_the_singular(self):
        found = check("fn f(a) { return a; } print f();")[0]
        assert "takes 1 argument," in found.message

    def test_two_arguments_read_in_the_plural(self):
        found = check("fn f(a, b) { return a; } print f(1);")[0]
        assert "takes 2 arguments," in found.message

    def test_a_default_gives_a_range(self):
        found = check("fn f(a, b = 2) { return a; } print f(1, 2, 3);")[0]
        assert "takes 1 to 2 arguments" in found.message

    def test_a_call_inside_the_range_is_fine(self):
        source = "fn f(a, b = 2) { return a; } print f(1); print f(1, 2);"
        assert check(source) == []

    def test_a_variadic_function_has_a_lower_bound_only(self):
        found = check("fn f(a, ...r) { return a; } print f();")[0]
        assert "at least 1 argument," in found.message

    def test_a_variadic_function_accepts_any_number_above_it(self):
        source = "fn f(a, ...r) { return a; } print f(1); print f(1, 2, 3, 4);"
        assert check(source) == []

    def test_a_class_takes_its_initializer_arity(self):
        found = check("class P { init(x, y) { this.x = x; } } print P(1);")[0]
        assert "P takes 2 arguments" in found.message

    def test_a_class_with_no_initializer_takes_nothing(self):
        assert kinds_of("class C { } print C(1);") == ["wrong-arity"]

    def test_a_class_with_no_initializer_called_bare_is_fine(self):
        assert check("class C { } print C();") == []

    def test_an_unknown_callee_has_no_arity_to_check(self):
        assert check("fn apply(g) { return g(1, 2, 3); }") == []


class TestIndexing:
    def test_indexing_a_bool_is_caught(self):
        assert kinds_of("let b = true; print b[0];") == ["not-indexable"]

    def test_indexing_a_number_is_caught(self):
        assert kinds_of("let n = 1; print n[0];") == ["not-indexable"]

    def test_indexing_a_list_is_fine(self):
        assert check("let a = [1, 2]; print a[0];") == []

    def test_indexing_a_string_is_fine(self):
        assert check('let s = "ab"; print s[0];') == []

    def test_indexing_a_map_is_fine(self):
        assert check('let m = {"a": 1}; print m["a"];') == []

    def test_a_string_key_on_a_list_is_caught(self):
        assert kinds_of('let a = [1]; print a["x"];') == ["bad-index"]

    def test_a_string_key_on_a_string_is_caught(self):
        assert kinds_of('let s = "ab"; print s["x"];') == ["bad-index"]

    def test_a_map_takes_any_key(self):
        assert check('let m = {"a": 1}; print m[1];') == []

    def test_the_message_says_what_can_be_indexed(self):
        found = check("let b = true; print b[0];")[0]
        assert "only a list, a map or a string" in found.message

    def test_writing_through_a_bad_index_is_caught(self):
        assert kinds_of('let a = [1]; a["x"] = 2;') == ["bad-index"]


class TestFlowSensitivity:
    def test_a_straight_line_reassignment_is_tracked_exactly(self):
        # the case a first version missed by merging both types into unknown
        assert kinds_of('let v = 1; v = "text"; print v - 1;') == ["not-a-number"]

    def test_a_reassignment_the_other_way_clears_a_mistake(self):
        assert check('let v = "a"; v = 1; print v - 1;') == []

    def test_a_name_assigned_in_a_branch_becomes_unknown(self):
        assert check('let v = 1; if (c) { v = "text"; } print v - 1;') == []

    def test_a_name_not_assigned_in_a_branch_keeps_its_type(self):
        assert kinds_of('let v = "a"; if (c) { print v; } print v - 1;') == ["not-a-number"]

    def test_a_name_assigned_in_a_loop_becomes_unknown(self):
        assert check('let v = 1; while (c) { v = "text"; } print v - 1;') == []

    def test_a_loop_body_does_not_trust_the_first_pass(self):
        # the correction that needed forgetting before the body as well as after
        assert check('let v = 1; while (c) { print v - 1; v = "t"; }') == []

    def test_a_name_assigned_in_a_match_arm_becomes_unknown(self):
        source = 'let v = 1; match (1) { case 1: v = "t"; default: } print v - 1;'
        assert check(source) == []

    def test_a_name_assigned_in_a_try_becomes_unknown(self):
        assert check('let v = 1; try { v = "t"; } catch (e) { } print v - 1;') == []

    def test_a_caught_value_is_unknown(self):
        assert check("try { throw 1; } catch (e) { print e - 1; }") == []

    def test_a_conditional_with_one_type_on_both_arms_keeps_it(self):
        assert kinds_of('let v = c ? "a" : "b"; print v - 1;') == ["not-a-number"]

    def test_a_conditional_with_two_types_becomes_unknown(self):
        assert check('let v = c ? "a" : 1; print v - 1;') == []


class TestParametersAreUnknown:
    def test_a_function_body_using_a_parameter_is_not_checked(self):
        # the honest cost of having no annotations
        assert check("fn f(x) { return x - 1; } print f(1);") == []

    def test_a_parameter_shadows_an_outer_name(self):
        source = 'let x = "a"; fn f(x) { return x - 1; } print f(1);'
        assert check(source) == []

    def test_a_local_inside_a_function_is_still_checked(self):
        source = 'fn f() { let y = "a"; return y - 1; }'
        assert kinds_of(source) == ["not-a-number"]

    def test_a_loop_variable_is_unknown(self):
        assert check("for (x in [1, 2]) { print x - 1; }") == []

    def test_a_property_read_is_unknown(self):
        assert check("class C { } let c = C(); print c.anything - 1;") == []


class TestScoping:
    def test_a_block_local_does_not_escape(self):
        source = 'let v = 1; { let v = "a"; print v; } print v - 1;'
        assert check(source) == []

    def test_a_block_local_is_checked_inside(self):
        source = '{ let v = "a"; print v - 1; }'
        assert kinds_of(source) == ["not-a-number"]

    def test_a_for_loop_variable_is_scoped_to_the_loop(self):
        source = 'let i = "a"; for (let i = 0; i < 2; i = i + 1) { print i; } print i - 1;'
        assert kinds_of(source) == ["not-a-number"]


class TestReporting:
    def test_findings_come_back_in_line_order(self):
        source = 'print "a" - 1;' + NEWLINE + 'print "b" - 2;'
        lines = [found.line for found in check(source)]
        assert lines == sorted(lines)

    def test_a_finding_renders_with_its_line(self):
        rendered = Finding(line=3, kind="a-kind", message="something").render()
        assert rendered == "line 3: a-kind: something"

    def test_a_clean_report_says_it_is_not_a_proof(self):
        rendered = report("print 1;")
        assert len(rendered) == 1
        assert "not a proof" in rendered[0]

    def test_a_report_counts_the_findings(self):
        assert "1 definite mistake" in report('print "a" - 1;')[-1]

    def test_two_findings_read_in_the_plural(self):
        assert "2 definite mistakes" in report('print "a" - "b";')[-1]

    def test_a_finding_appears_in_the_report(self):
        assert any("not-a-number" in line for line in report('print "a" - 1;'))

    def test_the_line_number_is_the_operator_line(self):
        source = "print 1;" + NEWLINE + 'print "a" - 1;'
        assert check(source)[0].line == 2
