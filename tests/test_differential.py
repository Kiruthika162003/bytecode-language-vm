from __future__ import annotations

import pytest

from ember import interpreter
from ember.differential import (
    BLOCKED,
    BOTH,
    CONFIGURATIONS,
    FOLDED,
    PEEPED,
    PLAIN,
    WALKED,
    Campaign,
    Disagreement,
    Outcome,
    all_refused,
    campaign,
    compare,
    outcomes_for,
)
from ember.generator import program_for


class TestOutcomes:
    def test_a_printed_run_is_not_a_refusal(self):
        outcome = Outcome(label=PLAIN, output=["1"])
        assert not outcome.refused
        assert outcome.comparable() == ("printed", "1")

    def test_a_refusal_compares_as_its_message(self):
        outcome = Outcome(label=PLAIN, refusal="division by zero")
        assert outcome.refused
        assert outcome.comparable() == ("refused", "division by zero")

    def test_two_refusals_with_different_messages_do_not_match(self):
        first = Outcome(label=PLAIN, refusal="a")
        second = Outcome(label=WALKED, refusal="b")
        assert first.comparable() != second.comparable()

    def test_an_outcome_describes_itself(self):
        assert "printed" in Outcome(label=PLAIN, output=["1"]).describe()
        assert "refused" in Outcome(label=PLAIN, refusal="no").describe()

    def test_an_empty_run_differs_from_a_run_that_printed(self):
        empty = Outcome(label=PLAIN)
        printed = Outcome(label=PLAIN, output=["1"])
        assert empty.comparable() != printed.comparable()


class TestAgreement:
    def test_every_configuration_is_tried(self):
        assert len(outcomes_for("print 1;")) == len(CONFIGURATIONS)
        assert len(CONFIGURATIONS) == 6

    def test_the_block_pass_is_one_of_them(self):
        assert BLOCKED in CONFIGURATIONS

    def test_a_simple_program_agrees(self):
        assert compare("print 1 + 2 * 3;") is None

    def test_a_closure_agrees(self):
        source = "fn make() { let c = 0; fn inc() { c = c + 1; return c; } return inc; }"
        assert compare(source + " let g = make(); print g(); print g();") is None

    def test_a_class_with_inheritance_agrees(self):
        source = (
            "class A { m() { return 1; } } class B < A { m() { return super.m() + 1; } }"
            " print B().m();"
        )
        assert compare(source) is None

    def test_a_loop_agrees(self):
        source = "let s = 0; for (let i = 0; i < 6; i = i + 1) s = s + i; print s;"
        assert compare(source) is None

    def test_a_refusal_agrees_when_every_backend_refuses(self):
        # all five must agree about failure too, not only about success
        assert compare("print 1 / 0;") is None

    def test_a_program_every_backend_refuses_is_recognised(self):
        assert all_refused("print 1 / 0;")

    def test_a_program_that_runs_is_not_all_refused(self):
        assert not all_refused("print 1;")


class TestGeneratedProgramsAgree:
    @pytest.mark.parametrize("seed", range(40))
    def test_a_generated_program_agrees_everywhere(self, seed):
        assert compare(program_for(seed), seed=seed) is None

    @pytest.mark.parametrize("seed", [500, 501, 502, 503])
    def test_a_longer_generated_program_agrees(self, seed):
        assert compare(program_for(seed, 12), seed=seed) is None


class TestCampaigns:
    def test_a_campaign_checks_the_count_asked_for(self):
        result = campaign(12)
        assert result.checked == 12

    def test_a_campaign_over_generated_programs_is_clean(self):
        result = campaign(40)
        assert result.clean
        assert result.disagreements == []

    def test_every_program_is_accounted_for(self):
        result = campaign(20)
        counted = result.agreed + result.refused + len(result.disagreements)
        assert counted == result.checked

    def test_the_summary_names_the_numbers(self):
        rendered = campaign(5).summary()
        assert "5 programs checked" in rendered
        assert "disagreed" in rendered

    def test_a_campaign_is_reproducible_from_its_seeds(self):
        first = campaign(8, first_seed=77).summary()
        assert first == campaign(8, first_seed=77).summary()

    def test_an_empty_campaign_is_clean(self):
        result = campaign(0)
        assert result.clean
        assert result.checked == 0

    def test_a_campaign_with_a_disagreement_is_not_clean(self):
        result = Campaign(checked=1, disagreements=[Disagreement(source="x")])
        assert not result.clean


class TestDetectionPower:
    """A differential test that cannot fail proves nothing, so break one on purpose."""

    def test_a_broken_walker_is_caught(self, monkeypatch):
        real = interpreter.run_treewalk_output

        def perturbed(source, **options):
            printed = real(source, **options)
            return ["999", *printed[1:]] if printed else printed

        monkeypatch.setattr(interpreter, "run_treewalk_output", perturbed)
        assert compare("print 1 + 2;") is not None

    def test_a_broken_walker_is_blamed_on_the_compiled_side(self, monkeypatch):
        real = interpreter.run_treewalk_output

        def perturbed(source, **options):
            printed = real(source, **options)
            return ["999", *printed[1:]] if printed else printed

        monkeypatch.setattr(interpreter, "run_treewalk_output", perturbed)
        found = compare("print 1 + 2;")
        assert found is not None
        assert "only the walker differs" in found.suspect()

    def test_a_broken_folder_is_blamed_on_the_folding_pass(self, monkeypatch):
        real = interpreter.run_output

        def perturbed(source, optimize=False, peephole=False, **options):
            printed = real(source, optimize=optimize, peephole=peephole, **options)
            if optimize and not peephole and printed:
                return ["-1", *printed[1:]]
            return printed

        monkeypatch.setattr(interpreter, "run_output", perturbed)
        found = compare("print 1 + 2;")
        assert found is not None
        assert FOLDED in found.suspect()

    def test_a_broken_walker_is_caught_on_every_generated_seed(self, monkeypatch):
        real = interpreter.run_treewalk_output

        def perturbed(source, **options):
            printed = real(source, **options)
            return ["999", *printed[1:]] if printed else printed

        monkeypatch.setattr(interpreter, "run_treewalk_output", perturbed)
        caught = sum(1 for seed in range(15) if compare(program_for(seed), seed=seed))
        assert caught == 15

    def test_a_campaign_notices_a_broken_backend(self, monkeypatch):
        real = interpreter.run_treewalk_output

        def perturbed(source, **options):
            printed = real(source, **options)
            return ["999", *printed[1:]] if printed else printed

        monkeypatch.setattr(interpreter, "run_treewalk_output", perturbed)
        assert not campaign(6).clean


class TestDisagreementReports:
    def _split(self) -> Disagreement:
        return Disagreement(
            source="print 1;",
            seed=42,
            outcomes=[
                Outcome(label=WALKED, output=["2"]),
                Outcome(label=PLAIN, output=["1"]),
                Outcome(label=FOLDED, output=["1"]),
                Outcome(label=PEEPED, output=["1"]),
                Outcome(label=BLOCKED, output=["1"]),
                Outcome(label=BOTH, output=["1"]),
            ],
        )

    def test_the_groups_gather_the_configurations_that_matched(self):
        grouped = self._split().groups()
        assert len(grouped) == 2
        assert sorted(len(listed) for listed in grouped.values()) == [1, 5]

    def test_a_lone_walker_points_at_the_compiler(self):
        assert "compiler or the machine" in self._split().suspect()

    def test_the_report_carries_the_seed_and_the_source(self):
        lines = self._split().render()
        assert any("seed 42" in line for line in lines)
        assert any("print 1;" in line for line in lines)

    def test_the_report_names_every_configuration(self):
        rendered = "\n".join(self._split().render())
        for label in CONFIGURATIONS:
            assert label in rendered

    def test_a_three_way_split_blames_more_than_one_component(self):
        messy = Disagreement(
            source="print 1;",
            outcomes=[
                Outcome(label=WALKED, output=["1"]),
                Outcome(label=PLAIN, output=["2"]),
                Outcome(label=FOLDED, output=["3"]),
                Outcome(label=PEEPED, output=["4"]),
                Outcome(label=BLOCKED, output=["6"]),
                Outcome(label=BOTH, output=["5"]),
            ],
        )
        assert "more than one component" in messy.suspect()

    def test_a_clean_divide_between_walking_and_compiling_is_named(self):
        divided = Disagreement(
            source="print 1;",
            outcomes=[
                Outcome(label=WALKED, output=["1"]),
                Outcome(label=PLAIN, output=["2"]),
                Outcome(label=FOLDED, output=["2"]),
                Outcome(label=PEEPED, output=["2"]),
                Outcome(label=BLOCKED, output=["2"]),
                Outcome(label=BOTH, output=["2"]),
            ],
        )
        assert "only the walker differs" in divided.suspect()
