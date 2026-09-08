from __future__ import annotations

import pytest

from examples import (
    closures_explained,
    first_program,
    handling_failure,
    objects_and_super,
    saving_bytecode,
    two_backends,
    what_folding_buys,
    where_time_goes,
)

EXAMPLES = (
    first_program,
    two_backends,
    what_folding_buys,
    closures_explained,
    objects_and_super,
    where_time_goes,
    saving_bytecode,
    handling_failure,
)


def _lines(module, capsys) -> list[str]:
    module.main()
    return capsys.readouterr().out.splitlines()


class TestEveryExampleRuns:
    @pytest.mark.parametrize("module", EXAMPLES, ids=lambda m: m.__name__.split(".")[-1])
    def test_it_prints_a_narrative(self, module, capsys):
        printed = _lines(module, capsys)
        assert len(printed) > 10, module.__name__

    @pytest.mark.parametrize("module", EXAMPLES, ids=lambda m: m.__name__.split(".")[-1])
    def test_it_ends_on_an_honest_note(self, module, capsys):
        printed = _lines(module, capsys)
        tail = " ".join(printed[-6:]).lower()
        # every example closes by naming a cost, a limit, or a refusal
        markers = ("cost", "not", "limit", "refus", "never", "price", "discard")
        assert any(marker in tail for marker in markers), printed[-6:]

    @pytest.mark.parametrize("module", EXAMPLES, ids=lambda m: m.__name__.split(".")[-1])
    def test_it_reports_a_measurement(self, module, capsys):
        printed = _lines(module, capsys)
        joined = " ".join(printed)
        assert any(character.isdigit() for character in joined), module.__name__


class TestFirstProgram:
    def test_it_shows_every_stage(self, capsys):
        printed = _lines(first_program, capsys)
        joined = chr(10).join(printed)
        assert "let total = 1 + 2 * 3;" in joined
        assert "LET IDENTIFIER EQUAL NUMBER PLUS NUMBER STAR NUMBER SEMICOLON EOF" in joined
        assert "a LetStmt" in joined
        assert "MULTIPLY" in joined
        assert "printed ['7']" in joined

    def test_it_reports_the_shrinking_as_discarding(self, capsys):
        joined = chr(10).join(_lines(first_program, capsys))
        assert "22 characters became 10 tokens became 12 bytes" in joined
        assert "discarding, not compression" in joined


class TestTwoBackends:
    def test_all_programs_agree(self, capsys):
        joined = chr(10).join(_lines(two_backends, capsys))
        assert "agreement: 6 of 6 programs" in joined
        assert "DISAGREE" not in joined

    def test_it_refuses_to_present_a_speed_ratio(self, capsys):
        joined = chr(10).join(_lines(two_backends, capsys))
        assert "not a speed ratio" in joined
        assert "agreement is not proof" in joined


class TestWhatFoldingBuys:
    def test_every_variant_prints_the_same(self, capsys):
        printed = _lines(what_folding_buys, capsys)
        assert not any("DIFFERENT" in line for line in printed)
        assert sum(1 for line in printed if "same:" in line) == 8

    def test_the_two_passes_show_different_columns(self, capsys):
        joined = chr(10).join(_lines(what_folding_buys, capsys))
        # tree folding collapses four constants into one
        assert "17b  4c      5b  1c" in joined
        # the peephole pass removes bytes while the pool stays
        assert "14b  1c     14b  1c      8b  1c" in joined


class TestClosuresExplained:
    def test_it_shows_independent_and_shared_capture(self, capsys):
        joined = chr(10).join(_lines(closures_explained, capsys))
        assert "['1', '2', '3', '1']" in joined
        assert "share one compiled body: True" in joined
        assert "hold different upvalues: True" in joined
        assert "upvalue is closed: True" in joined
        assert "['3']" in joined


class TestObjectsAndSuper:
    def test_it_separates_fields_from_methods(self, capsys):
        joined = chr(10).join(_lines(objects_and_super, capsys))
        assert "a square with 4 sides" in joined
        assert "'the method'" in joined
        assert "'the field'" in joined
        assert "['15', '30']" in joined
        assert "['1', '2', '3']" in joined


class TestWhereTimeGoes:
    def test_it_reports_counts_not_timings(self, capsys):
        joined = chr(10).join(_lines(where_time_goes, capsys))
        assert "2127 instructions, 177 frames entered" in joined
        assert "GET_LOCAL" in joined
        assert "off by default" in joined


class TestSavingBytecode:
    def test_everything_survives_the_round_trip(self, capsys):
        joined = chr(10).join(_lines(saving_bytecode, capsys))
        assert "disassembly identical: True" in joined
        assert "line table identical: True" in joined
        assert "output identical: True" in joined
        assert "'EMBR'" in joined

    def test_a_wrong_version_and_wrong_magic_are_refused(self, capsys):
        joined = chr(10).join(_lines(saving_bytecode, capsys))
        assert "which would be a bug" not in joined
        assert "recompile the source" in joined
        assert "magic number" in joined


class TestHandlingFailure:
    def test_runtime_faults_are_caught(self, capsys):
        joined = chr(10).join(_lines(handling_failure, capsys))
        assert "division by zero has no defined result" in joined
        assert "is not defined" in joined
        assert "outside a list of length 1" in joined

    def test_leaving_a_try_early_leaves_no_handler(self, capsys):
        joined = chr(10).join(_lines(handling_failure, capsys))
        assert "by returning: ['returned', 'later']" in joined
        assert "by breaking: ['1', 'later']" in joined
        assert "by continuing: ['2', 'later']" in joined

    def test_the_uncatchable_fault_is_not_caught(self, capsys):
        joined = chr(10).join(_lines(handling_failure, capsys))
        assert "call depth exceeded 1024 frames" in joined
        assert "which would be a bug" not in joined
