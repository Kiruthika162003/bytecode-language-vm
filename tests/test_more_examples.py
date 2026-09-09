from __future__ import annotations

import inspect
import re
from pathlib import Path

import pytest

from examples import (
    checking_before_running,
    patterns_and_their_limits,
    where_the_cost_is,
)
from tests.test_examples import EXAMPLES

_SECONDS = re.compile(r"in [0-9]+[.][0-9]+ seconds")
LATER = (
    checking_before_running,
    where_the_cost_is,
    patterns_and_their_limits,
)


def _lines(module, capsys) -> list[str]:
    module.main()
    return capsys.readouterr().out.splitlines()


def _joined(module, capsys) -> str:
    return chr(10).join(_lines(module, capsys))


def _without_timings(printed: list[str]) -> list[str]:
    return [_SECONDS.sub("in ... seconds", line) for line in printed]


class TestEveryLaterExampleRuns:
    @pytest.mark.parametrize("module", LATER, ids=lambda m: m.__name__.split(".")[-1])
    def test_it_prints_a_narrative(self, module, capsys):
        assert len(_lines(module, capsys)) > 10, module.__name__

    @pytest.mark.parametrize("module", LATER, ids=lambda m: m.__name__.split(".")[-1])
    def test_it_ends_on_an_honest_note(self, module, capsys):
        printed = _lines(module, capsys)
        tail = " ".join(printed[-6:]).lower()
        markers = ("cost", "not", "limit", "refus", "never", "price", "discard")
        assert any(marker in tail for marker in markers), printed[-6:]

    @pytest.mark.parametrize("module", LATER, ids=lambda m: m.__name__.split(".")[-1])
    def test_it_reports_a_measurement(self, module, capsys):
        assert any(character.isdigit() for character in _joined(module, capsys))

    @pytest.mark.parametrize("module", LATER, ids=lambda m: m.__name__.split(".")[-1])
    def test_it_prints_only_ascii(self, module, capsys):
        # a console on this machine is cp1252, and a block character once broke one
        assert all(ord(character) < 128 for character in _joined(module, capsys))

    @pytest.mark.parametrize("module", LATER, ids=lambda m: m.__name__.split(".")[-1])
    def test_it_runs_twice_the_same_way(self, module, capsys):
        # anything that leaves state behind prints differently the second time; the
        # first version of this compared the output verbatim and failed on the
        # pattern example, which prints elapsed seconds and so is deliberately not
        # reproducible, so an elapsed figure is blanked before the comparison
        first = _without_timings(_lines(module, capsys))
        second = _without_timings(_lines(module, capsys))
        assert first == second, module.__name__

    @pytest.mark.parametrize("module", LATER, ids=lambda m: m.__name__.split(".")[-1])
    def test_it_has_a_docstring_naming_a_tradeoff(self, module):
        prose = (module.__doc__ or "").lower()
        assert len(prose) > 400, module.__name__
        assert any(
            marker in prose
            for marker in ("cost", "cannot", "limit", "refus", "tradeoff", "price")
        ), module.__name__


class TestCheckingBeforeRunning:
    def test_the_verifier_finds_nothing_in_compiled_output(self, capsys):
        joined = _joined(checking_before_running, capsys)
        assert "the verifier finds no fault anywhere" in joined
        assert "bytecode that came from somewhere else" in joined

    def test_the_table_has_a_row_for_every_program(self, capsys):
        printed = _lines(checking_before_running, capsys)
        header = next(index for index, line in enumerate(printed) if "verifier" in line)
        rows = [line for line in printed[header + 2 :] if line.strip() and line[0] == " "]
        assert len(rows) >= 6

    def test_the_checks_disagree_with_each_other(self, capsys):
        joined = _joined(checking_before_running, capsys)
        assert "the checks do not overlap" in joined
        assert "and nothing a linter would question" in joined
        assert "and no type mistake" in joined

    def test_the_type_mistake_is_found_by_the_type_checker(self, capsys):
        joined = _joined(checking_before_running, capsys)
        assert "type mistake has a type mistake" in joined

    def test_the_unused_local_is_found_by_the_linter(self, capsys):
        joined = _joined(checking_before_running, capsys)
        assert "unused local has something a reader would question" in joined

    def test_the_block_pass_removes_the_dead_blocks(self, capsys):
        joined = _joined(checking_before_running, capsys)
        assert "0 after the block pass" in joined

    def test_it_admits_that_passing_proves_nothing(self, capsys):
        joined = _joined(checking_before_running, capsys)
        assert "still be wrong" in joined


class TestWhereTheCostIs:
    def test_both_ways_reach_the_same_answer(self, capsys):
        printed = _lines(where_the_cost_is, capsys)
        assert not any("DIFFERS" in line for line in printed)
        assert sum(1 for line in printed if line.rstrip().endswith("same")) == 5

    def test_the_ratio_grows_rather_than_staying_put(self, capsys):
        joined = _joined(where_the_cost_is, capsys)
        assert "the ratio grows rather than staying put" in joined

    def test_the_recursion_costs_far_more(self, capsys):
        joined = _joined(where_the_cost_is, capsys)
        assert "recursive: 62007 instructions, 38 deep at the tallest" in joined
        assert "iterative: 406 instructions, 4 deep at the tallest" in joined
        assert "the cheaper is iterative" in joined

    def test_the_stack_depth_tells_the_same_story(self, capsys):
        joined = _joined(where_the_cost_is, capsys)
        assert "recursive reaches 38 deep, iterative reaches 4" in joined

    def test_a_native_call_hides_its_work_from_the_count(self, capsys):
        joined = _joined(where_the_cost_is, capsys)
        assert "sorting three hundred values cost 2 more instructions" in joined
        assert "not a measure of time" in joined

    def test_the_ratios_increase_monotonically(self, capsys):
        printed = _lines(where_the_cost_is, capsys)
        ratios = [
            float(line.split()[3])
            for line in printed
            if line.rstrip().endswith("same") and len(line.split()) >= 5
        ]
        assert ratios == sorted(ratios)
        assert ratios[0] < ratios[-1]


class TestPatternsAndTheirLimits:
    def test_it_agrees_with_the_host_engine_throughout(self, capsys):
        joined = _joined(patterns_and_their_limits, capsys)
        assert "14 of 14 agree" in joined
        assert "DIFFERS" not in joined

    def test_every_refusal_is_actually_refused(self, capsys):
        joined = _joined(patterns_and_their_limits, capsys)
        assert "NOT REFUSED" not in joined

    def test_a_backreference_is_refused_for_a_stated_reason(self, capsys):
        joined = _joined(patterns_and_their_limits, capsys)
        assert "not a regular language" in joined

    def test_a_question_mark_group_is_refused_wholesale(self, capsys):
        joined = _joined(patterns_and_their_limits, capsys)
        assert "a non capturing group:" in joined
        assert "beginning with a question mark is refused" in joined

    def test_the_runaway_pattern_is_refused_at_length(self, capsys):
        printed = _lines(patterns_and_their_limits, capsys)
        outcomes = [line for line in printed if "characters:" in line]
        assert len(outcomes) == 5
        assert sum(1 for line in outcomes if "refused" in line) >= 4

    def test_the_refusal_arrives_quickly(self, capsys):
        printed = _lines(patterns_and_their_limits, capsys)
        seconds = [
            float(line.split()[-2]) for line in printed if "characters:" in line
        ]
        # the whole point is that no length takes appreciably longer than any other
        assert max(seconds) < 5.0

    def test_the_stack_limit_that_was_found_is_recorded(self, capsys):
        joined = _joined(patterns_and_their_limits, capsys)
        assert "used to exhaust the host stack" in joined
        assert "counts its run instead" in joined

    def test_a_long_ordinary_subject_matches_to_the_end(self, capsys):
        joined = _joined(patterns_and_their_limits, capsys)
        assert "over  5000 characters reached  5000" in joined

    def test_finding_every_match_gives_the_numbers(self, capsys):
        joined = _joined(patterns_and_their_limits, capsys)
        assert "['66', '1024', '7']" in joined

    def test_it_admits_the_limit_refuses_slow_and_runaway_alike(self, capsys):
        joined = _joined(patterns_and_their_limits, capsys)
        assert "does not distinguish a slow match from a runaway one" in joined


class TestNothingIsUnrun:
    def test_every_example_module_is_covered_by_a_test(self):
        # a new example added and never run is the failure this guards against, and
        # it is invisible otherwise, because an unimported module cannot fail
        folder = Path(__file__).resolve().parent.parent / "examples"
        on_disk = {
            path.stem
            for path in folder.glob("*.py")
            if not path.stem.startswith("_")
        }
        covered = {module.__name__.split(".")[-1] for module in EXAMPLES + LATER}
        assert on_disk == covered, on_disk ^ covered

    def test_the_two_lists_do_not_overlap(self):
        assert not set(EXAMPLES) & set(LATER)

    def test_every_example_defines_a_main_that_takes_nothing(self):
        for module in EXAMPLES + LATER:
            assert callable(module.main), module.__name__
            assert not inspect.signature(module.main).parameters, module.__name__
