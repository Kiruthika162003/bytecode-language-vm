from __future__ import annotations

from ember.testrunner import (
    ERRORED,
    FAILED,
    PASSED,
    Result,
    Suite,
    discover_tests,
    is_test_name,
    report,
    run_suite,
)

NEWLINE = chr(10)

PASSING = (
    "fn add(a, b) { return a + b; }"
    + NEWLINE
    + "fn testAdds() { if (add(1, 2) != 3) throw 1; }"
)
FAILING = 'fn testWrong() { throw "deliberately wrong"; }'
ERRORING = "fn testFaults() { print 1 / 0; }"


class TestTheNamingConvention:
    def test_a_name_beginning_with_test_is_a_test(self):
        assert is_test_name("testAdds")

    def test_the_bare_word_test_is_a_test(self):
        assert is_test_name("test")

    def test_another_name_is_not(self):
        assert not is_test_name("addsUp")

    def test_the_convention_catches_a_name_nobody_meant(self):
        # the honest cost of a convention rather than syntax
        assert is_test_name("testTheWaters")

    def test_a_capitalised_test_does_not_count(self):
        assert not is_test_name("TestAdds")


class TestDiscovery:
    def test_a_test_is_found(self):
        assert discover_tests(PASSING) == ["testAdds"]

    def test_a_helper_is_not_found(self):
        assert "add" not in discover_tests(PASSING)

    def test_several_tests_are_found(self):
        source = "fn testOne() { } fn testTwo() { }"
        assert sorted(discover_tests(source)) == ["testOne", "testTwo"]

    def test_a_program_with_no_tests_finds_none(self):
        assert discover_tests("print 1;") == []

    def test_a_value_named_like_a_test_is_not_a_test(self):
        # only a function can be called, so a plain binding is skipped
        assert discover_tests("let testValue = 1;") == []

    def test_a_nested_function_is_not_a_test(self):
        source = "fn outer() { fn testInner() { } return 1; } print outer();"
        assert discover_tests(source) == []


class TestOutcomes:
    def test_a_test_that_returns_passes(self):
        suite = run_suite(PASSING)
        assert suite.results[0].outcome == PASSED

    def test_a_test_that_throws_fails(self):
        suite = run_suite(FAILING)
        assert suite.results[0].outcome == FAILED

    def test_the_thrown_value_becomes_the_detail(self):
        suite = run_suite(FAILING)
        assert suite.results[0].detail == "deliberately wrong"

    def test_a_test_that_faults_errors(self):
        # a fault usually means the test itself is wrong, not the program
        suite = run_suite(ERRORING)
        assert suite.results[0].outcome == ERRORED

    def test_the_fault_message_becomes_the_detail(self):
        suite = run_suite(ERRORING)
        assert "division by zero" in suite.results[0].detail

    def test_a_thrown_number_is_shown_as_the_language_shows_it(self):
        suite = run_suite("fn testThrows() { throw 42; }")
        assert suite.results[0].detail == "42"

    def test_a_passing_result_says_it_held(self):
        assert run_suite(PASSING).results[0].held

    def test_a_failing_result_says_it_did_not(self):
        assert not run_suite(FAILING).results[0].held


class TestIsolation:
    def test_a_test_cannot_see_what_another_did_to_a_global(self):
        # each test gets its own machine, so order cannot decide the outcome
        source = (
            "let counter = 0;"
            + NEWLINE
            + "fn testOne() { counter = counter + 1; if (counter != 1) throw counter; }"
            + NEWLINE
            + "fn testTwo() { counter = counter + 1; if (counter != 1) throw counter; }"
        )
        assert run_suite(source).all_held

    def test_a_test_that_faults_does_not_disturb_the_next(self):
        source = ERRORING + NEWLINE + PASSING
        suite = run_suite(source)
        assert len(suite.errored) == 1
        assert len(suite.passed) == 1

    def test_output_from_one_test_does_not_appear_in_another(self):
        source = (
            'fn testPrints() { print "mine"; }'
            + NEWLINE
            + 'fn testAlsoFails() { throw "no"; }'
        )
        suite = run_suite(source)
        failing = suite.failed[0]
        assert "mine" not in failing.output


class TestCapturedOutput:
    def test_what_a_failing_test_printed_is_kept(self):
        source = 'fn testTalks() { print "before"; throw "after"; }'
        assert run_suite(source).results[0].output == ["before"]

    def test_a_passing_test_keeps_its_output_too(self):
        source = 'fn testTalks() { print "hello"; }'
        assert run_suite(source).results[0].output == ["hello"]

    def test_the_report_shows_what_a_failing_test_printed(self):
        source = 'fn testTalks() { print "before"; throw "after"; }'
        rendered = report(source)
        assert any("before" in line for line in rendered)

    def test_the_report_does_not_show_output_of_a_passing_test(self):
        source = 'fn testTalks() { print "hello"; }'
        rendered = report(source)
        assert not any("hello" in line for line in rendered)


class TestSuiteSummaries:
    def test_a_suite_of_passes_all_held(self):
        assert run_suite(PASSING).all_held

    def test_a_suite_with_a_failure_did_not(self):
        assert not run_suite(FAILING).all_held

    def test_the_counts_are_separated(self):
        source = PASSING + NEWLINE + FAILING + NEWLINE + ERRORING
        suite = run_suite(source)
        assert len(suite.passed) == 1
        assert len(suite.failed) == 1
        assert len(suite.errored) == 1

    def test_the_summary_names_the_failures(self):
        source = PASSING + NEWLINE + FAILING
        assert "1 failed" in run_suite(source).summary()

    def test_the_summary_names_the_errors(self):
        source = PASSING + NEWLINE + ERRORING
        assert "1 errored" in run_suite(source).summary()

    def test_a_clean_summary_mentions_only_passes(self):
        rendered = run_suite(PASSING).summary()
        assert "1 passed" in rendered
        assert "failed" not in rendered

    def test_no_tests_says_so_and_explains_the_convention(self):
        rendered = run_suite("print 1;").summary()
        assert "no tests found" in rendered
        assert "begins with test" in rendered

    def test_the_count_is_the_number_of_tests(self):
        source = "fn testOne() { } fn testTwo() { }"
        assert run_suite(source).count == 2

    def test_an_empty_suite_holds_vacuously(self):
        assert Suite().all_held


class TestRendering:
    def test_a_passing_result_renders_plainly(self):
        assert Result(name="testOne", outcome=PASSED).render() == "testOne: passed"

    def test_a_failing_result_renders_its_detail(self):
        rendered = Result(name="testOne", outcome=FAILED, detail="wrong").render()
        assert rendered == "testOne: failed: wrong"

    def test_an_erroring_result_renders_its_detail(self):
        rendered = Result(name="testOne", outcome=ERRORED, detail="boom").render()
        assert "errored: boom" in rendered

    def test_the_report_ends_with_the_summary(self):
        assert "1 tests: 1 passed" in report(PASSING)[-1]

    def test_the_report_has_a_line_per_test(self):
        source = "fn testOne() { } fn testTwo() { }"
        rendered = report(source)
        assert len([line for line in rendered if line.startswith("test")]) == 2


class TestUnderTheOptimisers:
    def test_a_suite_still_passes_after_folding(self):
        assert run_suite(PASSING, optimize=True).all_held

    def test_a_suite_still_passes_after_the_peephole_pass(self):
        assert run_suite(PASSING, peephole=True).all_held

    def test_a_failure_is_still_a_failure_after_both(self):
        assert not run_suite(FAILING, optimize=True, peephole=True).all_held
