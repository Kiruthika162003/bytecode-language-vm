from __future__ import annotations

import pytest

from ember.errors import Syntax, Unbound
from ember.formatter import format_program
from ember.interpreter import run, run_output, run_treewalk_output
from ember.parser import parse
from ember.scanner import scan

SHARED = [
    'match (1) { case 1: print "one"; case 2: print "two"; }',
    'match (2) { case 1: print "one"; case 2: print "two"; }',
    'match (9) { case 1: print "one"; default: print "other"; }',
    'match (3) { case 1, 2: print "low"; case 3, 4: print "high"; }',
    'match ("b") { case "a": print "A"; case "b": print "B"; }',
    'match (true) { case true: print "yes"; case false: print "no"; }',
    'match (nil) { case nil: print "nothing"; default: print "something"; }',
    'let n = 2; match (n + 1) { case 3: print "computed"; default: print "no"; }',
    'match (5) { case 1: print "one"; }',
    'match (1) { case 1: let a = 1; print a; print "two statements"; }',
    'fn f(n) { match (n) { case 0: return "zero"; default: return "other"; } }'
    " print f(0); print f(7);",
    "let hits = 0; for (x in [1, 2, 3]) { match (x) { case 2: hits = hits + 1; } }"
    " print hits;",
    "for (x in [1, 2, 3]) { match (x) { case 2: break; default: print x; } }",
]


class TestSelection:
    def test_the_matching_arm_runs(self):
        assert run_output('match (1) { case 1: print "one"; case 2: print "two"; }') == [
            "one"
        ]

    def test_a_later_arm_can_match(self):
        assert run_output('match (2) { case 1: print "one"; case 2: print "two"; }') == [
            "two"
        ]

    def test_the_default_runs_when_nothing_matches(self):
        source = 'match (9) { case 1: print "one"; default: print "other"; }'
        assert run_output(source) == ["other"]

    def test_nothing_runs_when_there_is_no_default(self):
        assert run_output('match (5) { case 1: print "one"; }') == []

    def test_one_arm_matching_stops_the_rest(self):
        # no fallthrough, so exactly one arm can run
        source = 'match (1) { case 1: print "a"; case 1: print "b"; }'
        assert run_output(source) == ["a"]

    def test_an_arm_may_list_several_values(self):
        source = 'match (4) { case 1, 2: print "low"; case 3, 4: print "high"; }'
        assert run_output(source) == ["high"]

    def test_an_arm_holds_several_statements_without_braces(self):
        source = 'match (1) { case 1: let a = 1; print a; print "second"; }'
        assert run_output(source) == ["1", "second"]


class TestSubjectAndValues:
    def test_the_subject_is_evaluated_once(self):
        source = (
            "let calls = 0; fn subject() { calls = calls + 1; return 2; }"
            ' match (subject()) { case 1: print "a"; case 2: print "b"; case 3: print "c"; }'
            " print calls;"
        )
        assert run_output(source) == ["b", "1"]

    def test_the_subject_may_be_any_expression(self):
        source = 'let n = 2; match (n + 1) { case 3: print "computed"; }'
        assert run_output(source) == ["computed"]

    def test_case_values_may_be_expressions(self):
        source = 'let k = 3; match (3) { case k: print "matched a variable"; }'
        assert run_output(source) == ["matched a variable"]

    def test_matching_follows_the_language_equality_rule(self):
        # 1 and true are distinct here, so neither matches the other
        assert run_output('match (1) { case true: print "bool"; default: print "int"; }') == [
            "int"
        ]

    def test_strings_booleans_and_nil_all_match(self):
        assert run_output('match ("b") { case "b": print "s"; }') == ["s"]
        assert run_output('match (true) { case true: print "t"; }') == ["t"]
        assert run_output('match (nil) { case nil: print "n"; }') == ["n"]

    def test_an_int_matches_an_equal_float(self):
        assert run_output('match (1) { case 1.0: print "same number"; }') == ["same number"]


class TestControlFlow:
    def test_an_arm_can_return_from_its_function(self):
        source = (
            'fn f(n) { match (n) { case 0: return "zero"; default: return "other"; } }'
            " print f(0); print f(7);"
        )
        assert run_output(source) == ["zero", "other"]

    def test_break_inside_a_match_leaves_the_enclosing_loop(self):
        source = 'for (x in [1, 2, 3]) { match (x) { case 2: break; default: print x; } }'
        assert run_output(source) == ["1"]

    def test_continue_inside_a_match_skips_the_iteration(self):
        source = "for (x in [1, 2, 3]) { match (x) { case 2: continue; } print x; }"
        assert run_output(source) == ["1", "3"]

    def test_a_match_inside_a_loop_runs_each_iteration(self):
        source = (
            "let hits = 0; for (x in [1, 2, 2, 3]) { match (x) { case 2: hits = hits + 1; } }"
            " print hits;"
        )
        assert run_output(source) == ["2"]

    def test_an_arm_can_throw_and_be_caught(self):
        source = 'try { match (1) { case 1: throw "from an arm"; } } catch (e) { print e; }'
        assert run_output(source) == ["from an arm"]


class TestScoping:
    def test_each_arm_has_its_own_scope(self):
        source = 'match (1) { case 1: let a = 1; print a; }'
        assert run_output(source) == ["1"]

    def test_an_arm_local_does_not_escape(self):
        # the arm has a scope of its own, so afterwards the name is not a global
        with pytest.raises(Unbound):
            run("match (1) { case 1: let a = 1; } print a;")


class TestSyntaxRules:
    def test_an_empty_match_is_refused(self):
        with pytest.raises(Syntax):
            run("match (1) { }")

    def test_two_defaults_are_refused(self):
        with pytest.raises(Syntax):
            run('match (1) { default: print "a"; default: print "b"; }')

    def test_a_case_without_a_colon_is_refused(self):
        with pytest.raises(Syntax):
            run('match (1) { case 1 print "a"; }')

    def test_a_subject_without_parentheses_is_refused(self):
        with pytest.raises(Syntax):
            run('match 1 { case 1: print "a"; }')

    def test_a_statement_where_a_case_belongs_is_refused(self):
        with pytest.raises(Syntax):
            run('match (1) { print "a"; }')


class TestFormatting:
    def test_a_match_is_printed_back_with_indented_arms(self):
        source = 'match (n) { case 1, 2: print "low"; default: print "high"; }'
        text = format_program(parse(scan(source)))
        assert "match (n) {" in text
        assert "  case 1, 2:" in text
        assert '    print "low";' in text
        assert "  default:" in text

    def test_formatting_stays_idempotent(self):
        source = 'match (n) { case 1: print "a"; case 2, 3: print "b"; default: print "c"; }'
        once = format_program(parse(scan(source)))
        assert format_program(parse(scan(once))) == once

    def test_formatting_preserves_the_result(self):
        source = 'let n = 2; match (n) { case 1: print "a"; case 2: print "b"; }'
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
