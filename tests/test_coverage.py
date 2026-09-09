from __future__ import annotations

from ember.coverage import Report, lines_in, measure, uncovered_source
from ember.interpreter import build

NEWLINE = chr(10)


def program(*lines: str) -> str:
    return NEWLINE.join(lines) + NEWLINE


class TestEmittedLines:
    def test_a_two_line_program_emits_both(self):
        assert lines_in(build(program("print 1;", "print 2;"))) == {1, 2}

    def test_a_blank_line_emits_nothing(self):
        assert lines_in(build(program("print 1;", "", "print 3;"))) == {1, 3}

    def test_a_comment_emits_nothing(self):
        found = lines_in(build(program("print 1;", "// a remark", "print 3;")))
        assert found == {1, 3}

    def test_a_nested_function_contributes_its_lines(self):
        source = program("fn f() {", "  return 1;", "}", "print f();")
        assert 2 in lines_in(build(source))

    def test_a_method_contributes_its_lines(self):
        source = program("class C {", "  m() {", "    return 1;", "  }", "}", "print C().m();")
        assert 3 in lines_in(build(source))


class TestFullCoverage:
    def test_a_program_where_everything_runs_is_complete(self):
        report = measure(program("print 1;", "print 2;"))
        assert report.complete
        assert report.percentage == 100

    def test_a_loop_body_that_runs_is_covered(self):
        source = program("for (let i = 0; i < 2; i = i + 1) {", "  print i;", "}")
        assert measure(source).complete

    def test_a_called_function_is_covered(self):
        source = program("fn f() {", "  return 1;", "}", "print f();")
        assert measure(source).complete

    def test_the_share_of_a_complete_report_is_one(self):
        assert measure(program("print 1;")).share == 1.0

    def test_the_summary_names_both_counts(self):
        rendered = measure(program("print 1;", "print 2;")).summary()
        assert "2 of 2" in rendered
        assert "100 percent" in rendered


class TestMissedLines:
    def test_a_branch_never_taken_is_missed(self):
        source = program("if (false) {", '  print "never";', "}", 'print "after";')
        assert measure(source).missed == {2}

    def test_a_function_never_called_is_missed(self):
        source = program("fn unused() {", "  return 1;", "}", "print 2;")
        assert measure(source).missed == {2}

    def test_an_else_arm_never_taken_is_missed(self):
        source = program("if (true) {", '  print "yes";', "} else {", '  print "no";', "}")
        assert measure(source).missed == {4}

    def test_a_then_arm_never_taken_is_missed(self):
        source = program("if (false) {", '  print "yes";', "} else {", '  print "no";', "}")
        assert measure(source).missed == {2}

    def test_a_partial_report_is_not_complete(self):
        source = program("if (false) {", '  print "never";', "}", 'print "after";')
        assert not measure(source).complete

    def test_the_percentage_reflects_the_shortfall(self):
        source = program("if (false) {", '  print "never";', "}", 'print "after";')
        assert measure(source).percentage == 67


class TestReporting:
    def test_a_complete_report_says_only_the_summary(self):
        assert len(measure(program("print 1;")).render()) == 1

    def test_a_partial_report_lists_the_missed_lines(self):
        source = program("if (false) {", '  print "never";', "}", 'print "after";')
        rendered = measure(source).render()
        assert any("never ran: 2" in line for line in rendered)

    def test_the_source_can_be_shown_alongside(self):
        source = program("if (false) {", '  print "never";', "}", 'print "after";')
        rendered = measure(source).render(source)
        assert any('print "never";' in line for line in rendered)

    def test_the_uncovered_source_can_be_asked_for_directly(self):
        source = program("if (false) {", '  print "never";', "}", 'print "after";')
        assert uncovered_source(source) == ['print "never";']

    def test_a_complete_program_has_no_uncovered_source(self):
        assert uncovered_source(program("print 1;")) == []


class TestReportRecord:
    def test_an_empty_report_counts_as_complete(self):
        # nothing to cover is complete coverage rather than a division by zero
        empty = Report()
        assert empty.complete
        assert empty.share == 1.0

    def test_covered_lines_outside_the_emitted_set_do_not_inflate_the_share(self):
        report = Report(executable={1, 2}, covered={1, 2, 99})
        assert report.share == 1.0

    def test_the_missed_set_is_what_was_emitted_and_not_covered(self):
        report = Report(executable={1, 2, 3}, covered={1})
        assert report.missed == {2, 3}

    def test_the_percentage_rounds(self):
        report = Report(executable={1, 2, 3}, covered={1, 2})
        assert report.percentage == 67


class TestUnderTheOptimisers:
    def test_folding_does_not_break_the_measurement(self):
        source = program("print 1 + 2;", "print 3;")
        assert measure(source, optimize=True).complete

    def test_the_peephole_pass_does_not_break_the_measurement(self):
        source = program("fn f() {", "  return 1;", "}", "print f();")
        assert measure(source, peephole=True).complete

    def test_both_together_do_not_break_the_measurement(self):
        source = program("print 1 + 2;")
        assert measure(source, optimize=True, peephole=True).complete


class TestWhatLineCoverageCannotSee:
    def test_two_statements_on_one_line_are_one_line(self):
        # covering either covers both, which is the limit of line coverage
        report = measure(program('if (false) print "a"; print "b";'))
        assert report.complete

    def test_only_one_arm_of_a_conditional_on_one_line_still_reads_covered(self):
        report = measure(program('print true ? "y" : "n";'))
        assert report.complete
