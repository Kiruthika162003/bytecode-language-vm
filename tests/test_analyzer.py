from __future__ import annotations

import pytest

from ember.analyzer import (
    CONSTANT_CONDITION,
    EMPTY_BODY,
    SELF_ASSIGNMENT,
    SHADOWED,
    STATIC_METHOD,
    UNREACHABLE,
    UNUSED_LOCAL,
    UNUSED_PARAMETER,
    Diagnostic,
    analyze,
)
from ember.parser import parse
from ember.scanner import scan

CLEAN = [
    "fn add(a, b) { return a + b; } print add(1, 2);",
    "{ let x = 1; print x; }",
    "class C { get() { return this.v; } }",
    "class C { init() { this.v = 1; } } print C().v;",
    "let n = 0; while (true) { n = n + 1; if (n > 2) break; } print n;",
    "let total = 0; for (i in [1, 2, 3]) total = total + i; print total;",
    "{ let _deliberate = 1; print 2; }",
    "fn f(_slot, used) { return used; } print f(1, 2);",
    'try { throw "x"; } catch (e) { print e; }',
    "fn outer() { let c = 0; fn inc() { c = c + 1; return c; } return inc; } print outer()();",
]


def kinds(source: str) -> list[str]:
    return [found.kind for found in analyze(parse(scan(source)))]


def diagnostics(source: str) -> list[Diagnostic]:
    return analyze(parse(scan(source)))


class TestNoFalsePositives:
    @pytest.mark.parametrize("source", CLEAN)
    def test_well_written_code_reports_nothing(self, source: str):
        assert kinds(source) == [], source


class TestUnusedBindings:
    def test_an_unread_local_is_reported(self):
        assert UNUSED_LOCAL in kinds("{ let unused = 1; print 2; }")

    def test_a_written_but_never_read_local_is_reported(self):
        # storing a value nobody reads is the thing worth knowing about
        assert UNUSED_LOCAL in kinds("{ let x = 1; x = 2; }")

    def test_an_underscore_name_is_exempt(self):
        assert UNUSED_LOCAL not in kinds("{ let _unused = 1; print 2; }")

    def test_an_unread_parameter_is_reported(self):
        assert UNUSED_PARAMETER in kinds("fn f(a, b) { return a; } print f(1, 2);")

    def test_an_underscore_parameter_is_exempt(self):
        assert UNUSED_PARAMETER not in kinds("fn f(a, _b) { return a; } print f(1, 2);")

    def test_a_read_local_is_not_reported(self):
        assert UNUSED_LOCAL not in kinds("{ let x = 1; print x; }")

    def test_the_message_names_the_binding(self):
        found = diagnostics("{ let scratch = 1; print 2; }")
        assert "'scratch'" in found[0].message


class TestShadowing:
    def test_an_inner_declaration_hiding_an_outer_one_is_reported(self):
        assert SHADOWED in kinds("fn f() { let x = 1; { let x = 2; return x; } }")

    def test_shadowing_is_not_reported_across_functions(self):
        # a local reusing a global's name is ordinary, not a mistake
        source = "let x = 1; fn f() { let x = 2; return x; } print f(); print x;"
        assert SHADOWED not in kinds(source)

    def test_the_message_names_the_earlier_line(self):
        source = "fn f() {" + chr(10) + "let x = 1;" + chr(10) + "{ let x = 2; return x; } }"
        found = [d for d in diagnostics(source) if d.kind == SHADOWED]
        assert "line 2" in found[0].message


class TestUnreachable:
    def test_a_statement_after_return_is_reported(self):
        assert UNREACHABLE in kinds('fn f() { return 1; print "dead"; }')

    def test_a_statement_after_break_is_reported(self):
        assert UNREACHABLE in kinds('while (true) { break; print "dead"; }')

    def test_a_statement_after_continue_is_reported(self):
        assert UNREACHABLE in kinds('while (true) { continue; print "dead"; }')

    def test_a_statement_after_throw_is_reported(self):
        assert UNREACHABLE in kinds('fn f() { throw "x"; print "dead"; }')

    def test_only_the_first_unreachable_statement_is_reported(self):
        # one report per block, not one per line, so the noise stays proportionate
        source = 'fn f() { return 1; print "a"; print "b"; print "c"; }'
        assert kinds(source).count(UNREACHABLE) == 1

    def test_the_message_names_what_left_the_block(self):
        source = 'fn f() { return 1; print "x"; }'
        found = [d for d in diagnostics(source) if d.kind == UNREACHABLE]
        assert "return" in found[0].message


class TestConstantConditions:
    def test_an_always_true_if_is_reported(self):
        assert CONSTANT_CONDITION in kinds('if (true) print "a";')

    def test_a_never_true_if_is_reported(self):
        assert CONSTANT_CONDITION in kinds('if (false) print "a";')

    def test_while_true_is_allowed(self):
        # an idiom for a loop that breaks out, not a mistake
        source = "let n = 0; while (true) { n = n + 1; if (n > 2) break; } print n;"
        assert CONSTANT_CONDITION not in kinds(source)

    def test_a_variable_condition_is_not_reported(self):
        assert CONSTANT_CONDITION not in kinds('if (cond) print "a";')


class TestOtherRules:
    def test_an_empty_body_is_reported(self):
        assert EMPTY_BODY in kinds("if (cond) { }")

    def test_a_method_ignoring_this_is_reported(self):
        assert STATIC_METHOD in kinds("class C { helper() { return 1; } }")

    def test_an_initializer_is_exempt_from_that(self):
        assert STATIC_METHOD not in kinds("class C { init() { this.v = 1; } }")

    def test_a_method_using_this_is_not_reported(self):
        assert STATIC_METHOD not in kinds("class C { get() { return this.v; } }")

    def test_a_method_using_super_counts_as_depending_on_the_instance(self):
        # A.m legitimately ignores this, so only B.m must escape the rule
        source = (
            "class A { m() { return this.v; } }"
            " class B < A { m() { return super.m(); } }"
        )
        assert STATIC_METHOD not in kinds(source)

    def test_a_self_assignment_is_reported(self):
        assert SELF_ASSIGNMENT in kinds("{ let x = 1; x = x; print x; }")


class TestOrderingAndShape:
    def test_diagnostics_are_sorted_by_line(self):
        source = (
            "fn f() {" + chr(10) + "  let a = 1;" + chr(10) + "  return 2;"
            + chr(10) + '  print "dead";' + chr(10) + "}"
        )
        found = diagnostics(source)
        assert [d.line for d in found] == sorted(d.line for d in found)

    def test_a_diagnostic_renders_with_its_line_and_kind(self):
        rendered = diagnostics("{ let unused = 1; print 2; }")[0].render()
        assert rendered.startswith("line 1: unused-local:")

    def test_analysis_never_raises_on_a_valid_program(self):
        for source in CLEAN:
            analyze(parse(scan(source)))
