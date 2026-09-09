from __future__ import annotations

from ember.benchlib import (
    Comparison,
    Measurement,
    Suite,
    compare,
    is_repeatable,
    measure,
    optimiser_effect,
    run_suite,
    saved_by_optimising,
)

RECURSIVE = "fn fib(n) { if (n < 2) return n; return fib(n-1) + fib(n-2); } print fib(12);"
ITERATIVE = (
    "let a = 0; let b = 1;"
    " for (let i = 0; i < 12; i = i + 1) { let t = a + b; a = b; b = t; } print a;"
)
FOLDABLE = "print 1 + 2 * 3 - 4;"


class TestMeasuring:
    def test_a_program_dispatches_instructions(self):
        assert measure("print 1;").instructions > 0

    def test_the_output_is_kept(self):
        assert measure("print 1 + 2;").output == ("3",)

    def test_the_stack_high_water_is_recorded(self):
        assert measure("print 1 + 2;").stack_high_water > 0

    def test_the_label_is_kept(self):
        assert measure("print 1;", "mine").label == "mine"

    def test_a_bigger_program_dispatches_more(self):
        assert measure(RECURSIVE).instructions > measure("print 1;").instructions

    def test_recursion_reaches_a_deeper_stack(self):
        assert measure(RECURSIVE).stack_high_water > measure(ITERATIVE).stack_high_water

    def test_a_faulting_program_is_measured_up_to_the_fault(self):
        found = measure("print 1; print 1 / 0;")
        assert found.refused
        assert found.instructions > 0

    def test_the_fault_is_recorded(self):
        assert "division by zero" in measure("print 1 / 0;").refusal

    def test_the_output_before_a_fault_is_kept(self):
        assert measure("print 1; print 1 / 0;").output == ("1",)

    def test_a_clean_program_is_not_refused(self):
        assert not measure("print 1;").refused

    def test_a_measurement_renders_its_counts(self):
        rendered = measure("print 1;", "mine").render()
        assert "mine:" in rendered
        assert "instructions" in rendered

    def test_a_refused_measurement_says_so(self):
        assert "refused after" in measure("print 1 / 0;", "bad").render()


class TestRepeatability:
    def test_the_same_program_dispatches_the_same_count(self):
        # the property that makes this worth counting rather than timing
        assert measure(RECURSIVE).instructions == measure(RECURSIVE).instructions

    def test_repeatability_is_reported_directly(self):
        assert is_repeatable(RECURSIVE)

    def test_a_program_with_a_loop_is_repeatable(self):
        assert is_repeatable(ITERATIVE)

    def test_an_optimised_program_is_repeatable(self):
        assert is_repeatable(FOLDABLE, optimize=True)

    def test_the_count_is_the_same_across_many_runs(self):
        counts = {measure("print 1 + 2;").instructions for _ in range(5)}
        assert len(counts) == 1


class TestComparing:
    def test_two_ways_of_computing_one_answer_can_be_compared(self):
        found = compare(RECURSIVE, ITERATIVE, ("recursive", "iterative"))
        assert not found.disagreed

    def test_the_cheaper_one_is_named(self):
        found = compare(RECURSIVE, ITERATIVE, ("recursive", "iterative"))
        assert found.better == "iterative"

    def test_the_difference_is_reported(self):
        found = compare(RECURSIVE, ITERATIVE)
        assert found.difference < 0

    def test_the_ratio_is_reported(self):
        # a difference means nothing without what it is a difference from
        found = compare(RECURSIVE, ITERATIVE)
        assert 0 < found.ratio < 1

    def test_two_identical_programs_cost_the_same(self):
        found = compare("print 1;", "print 1;")
        assert found.difference == 0
        assert "cost the same" in found.better

    def test_two_disagreeing_programs_are_not_ranked(self):
        # two programs that do not agree are not two ways of doing one thing
        found = compare("print 1;", "print 2;")
        assert found.disagreed
        assert "do not agree" in found.better

    def test_the_report_says_why_they_were_not_ranked(self):
        lines = compare("print 1;", "print 2;").render()
        assert any("not comparable" in line for line in lines)

    def test_the_report_shows_what_each_printed(self):
        lines = compare("print 1;", "print 2;").render()
        assert any("printed ['1']" in line for line in lines)

    def test_one_program_faulting_counts_as_disagreement(self):
        assert compare("print 1;", "print 1 / 0;").disagreed

    def test_two_programs_faulting_the_same_way_agree(self):
        assert not compare("print 1 / 0;", "print 1 / 0;").disagreed

    def test_the_report_names_both_programs(self):
        lines = compare(RECURSIVE, ITERATIVE, ("one", "two")).render()
        assert any("one:" in line for line in lines)
        assert any("two:" in line for line in lines)

    def test_a_ratio_against_nothing_is_one(self):
        empty = Measurement(label="a", instructions=0, stack_high_water=0)
        found = Comparison(first=empty, second=empty)
        assert found.ratio == 1.0


class TestSuites:
    def test_every_program_is_measured(self):
        found = run_suite({"one": "print 1;", "two": "print 2;"})
        assert len(found.measurements) == 2

    def test_the_total_adds_up(self):
        found = run_suite({"one": "print 1;", "two": "print 2;"})
        assert found.total == sum(one.instructions for one in found.measurements)

    def test_the_cheapest_is_found(self):
        found = run_suite({"small": "print 1;", "large": RECURSIVE})
        assert found.cheapest().label == "small"

    def test_the_dearest_is_found(self):
        found = run_suite({"small": "print 1;", "large": RECURSIVE})
        assert found.dearest().label == "large"

    def test_a_refused_program_is_not_the_cheapest(self):
        found = run_suite({"bad": "print 1 / 0;", "good": RECURSIVE})
        assert found.cheapest().label == "good"

    def test_a_suite_of_only_refusals_has_no_cheapest(self):
        assert run_suite({"bad": "print 1 / 0;"}).cheapest() is None

    def test_an_empty_suite_has_no_cheapest(self):
        assert Suite().cheapest() is None

    def test_an_empty_suite_renders_nothing(self):
        assert Suite().render() == []

    def test_the_labels_are_aligned(self):
        lines = run_suite({"a": "print 1;", "longer": "print 2;"}).render()
        assert lines[0].startswith("a     ")

    def test_a_refused_program_is_marked(self):
        lines = run_suite({"bad": "print 1 / 0;"}).render()
        assert any("refused" in line for line in lines)

    def test_the_total_is_reported(self):
        lines = run_suite({"one": "print 1;"}).render()
        assert "altogether" in lines[-1]


class TestTheOptimisers:
    def test_every_setting_is_measured(self):
        assert len(optimiser_effect(FOLDABLE).measurements) == 5

    def test_folding_removes_instructions(self):
        found = optimiser_effect(FOLDABLE)
        plain = next(one for one in found.measurements if one.label == "plain")
        folded = next(one for one in found.measurements if one.label == "folded")
        assert folded.instructions < plain.instructions

    def test_the_saving_is_reported(self):
        assert saved_by_optimising(FOLDABLE) > 0

    def test_a_program_with_nothing_to_fold_saves_nothing(self):
        assert saved_by_optimising("let a = 1; print a;") == 0

    def test_every_setting_prints_the_same_thing(self):
        found = optimiser_effect(FOLDABLE)
        outputs = {one.output for one in found.measurements}
        assert len(outputs) == 1

    def test_the_settings_are_named(self):
        labels = [one.label for one in optimiser_effect(FOLDABLE).measurements]
        assert labels == ["plain", "folded", "peephole", "blocks", "all three"]

    def test_all_three_is_no_worse_than_any_one(self):
        found = optimiser_effect(FOLDABLE)
        best = min(one.instructions for one in found.measurements)
        together = next(one for one in found.measurements if one.label == "all three")
        assert together.instructions == best


class TestWhatCountingDoesNotSay:
    def test_a_native_doing_much_work_is_one_instruction(self):
        # the honest gap: instructions are not equal
        source = "let a = []; for (let i = 0; i < 200; i = i + 1) { a = push(a, 200 - i); }"
        by_hand = source + " print len(a);"
        by_native = source + " print len(ordered(a));"
        found = compare(by_hand, by_native, ("without sorting", "with sorting"))
        assert found.difference < 20

    def test_fewer_instructions_is_not_a_claim_about_time(self):
        # nothing here measures a clock, and the tests do not pretend otherwise
        found = measure("print 1;")
        assert not hasattr(found, "seconds")
