from __future__ import annotations

import pytest

from ember.blockopt import (
    Report,
    optimise_deeply,
    optimise_program,
    remove_unreachable,
    thread_jumps,
)
from ember.builtins import install_builtins
from ember.cfg import graph_of
from ember.function import Function
from ember.generator import program_for
from ember.instructions import decode
from ember.interpreter import build, run_output
from ember.traces.verifytrace import CORPUS
from ember.verifier import faults_deeply, warnings_deeply
from ember.vm import VM

NESTED_IF = "let a = true; let b = false; "
NESTED_IF += "if (a) { if (b) { print 1; } else { print 2; } } else { print 3; }"


def optimised_output(source: str) -> list[str]:
    function = build(source)
    optimise_deeply(function)
    machine = VM()
    install_builtins(machine)
    machine.interpret(function)
    return machine.output


class TestBehaviourIsPreserved:
    @pytest.mark.parametrize("source", CORPUS)
    def test_the_output_is_unchanged_on_the_corpus(self, source):
        # an edit to a jump that lands one instruction out runs and is wrong
        assert optimised_output(source) == run_output(source)

    @pytest.mark.parametrize("seed", range(30))
    def test_the_output_is_unchanged_on_generated_programs(self, seed):
        source = program_for(seed)
        assert optimised_output(source) == run_output(source)

    def test_a_nested_if_still_takes_the_right_branch(self):
        assert optimised_output(NESTED_IF) == run_output(NESTED_IF)

    @pytest.mark.parametrize(
        "values,expected",
        [("true", "1"), ("false", "2")],
    )
    def test_every_branch_of_a_nested_if_still_works(self, values, expected):
        source = f"let a = true; let b = {values}; "
        source += "if (a) { if (b) { print 1; } else { print 2; } } else { print 3; }"
        assert optimised_output(source) == [expected]

    def test_the_outer_else_still_works(self):
        source = "let a = false; let b = true; "
        source += "if (a) { if (b) { print 1; } else { print 2; } } else { print 3; }"
        assert optimised_output(source) == ["3"]

    def test_a_loop_still_runs_the_same_number_of_times(self):
        source = "let s = 0; for (let i = 0; i < 5; i = i + 1) s = s + i; print s;"
        assert optimised_output(source) == ["10"]

    def test_a_break_still_leaves_the_loop(self):
        source = "let n = 0; while (n < 9) { n = n + 1; if (n == 3) break; } print n;"
        assert optimised_output(source) == ["3"]

    def test_a_continue_still_skips(self):
        source = "for (x in [1, 2, 3]) { if (x == 2) continue; print x; }"
        assert optimised_output(source) == ["1", "3"]

    def test_a_handler_still_catches(self):
        source = 'try { print 1 / 0; } catch (e) { print "caught"; } print "after";'
        assert optimised_output(source) == ["caught", "after"]

    def test_recursion_still_terminates(self):
        source = "fn fib(n) { if (n < 2) return n; return fib(n-1) + fib(n-2); } print fib(10);"
        assert optimised_output(source) == ["55"]


class TestDeadBlocks:
    def test_the_corpus_carries_dead_code_before_the_pass(self):
        found = sum(len(warnings_deeply(build(source))) for source in CORPUS)
        assert found > 0

    def test_the_pass_removes_all_of_it(self):
        # the reports the verifier has been making since it was written
        total = 0
        for source in CORPUS:
            function = build(source)
            optimise_deeply(function)
            total += len(warnings_deeply(function))
        assert total == 0

    def test_no_fault_is_introduced(self):
        for source in CORPUS:
            function = build(source)
            optimise_deeply(function)
            assert faults_deeply(function) == []

    def test_a_function_that_always_returns_loses_its_epilogue(self):
        function = build("fn f() { return 1; } print f();")
        report = optimise_deeply(function)
        assert report.instructions_removed > 0

    def test_nothing_unreachable_is_left(self):
        function = build("fn f() { return 1; } print f();")
        optimise_deeply(function)
        inner = next(c for c in function.chunk.constants if isinstance(c, Function))
        assert graph_of(inner).unreachable() == []

    def test_a_program_with_nothing_dead_is_left_alone(self):
        function = build("print 1 + 2;")
        report = optimise_deeply(function)
        assert report.instructions_removed == 0

    def test_removing_nothing_leaves_the_chunk_identical(self):
        function = build("print 1 + 2;")
        before = list(function.chunk.code)
        optimise_deeply(function)
        assert list(function.chunk.code) == before

    def test_an_empty_program_survives_the_pass(self):
        program = decode(build("print 1;").chunk)
        program.instructions.clear()
        assert remove_unreachable(program) == (0, 0)


class TestJumpThreading:
    def test_a_nested_if_else_has_one_chain_to_thread(self):
        # the one shape that produces a chain, which measuring found after the
        # nested loop story it was written for turned out not to
        function = build(NESTED_IF)
        assert optimise_deeply(function).jumps_threaded == 1

    def test_a_nested_break_produces_no_chain(self):
        source = "for (let i=0;i<3;i=i+1) { for (let j=0;j<3;j=j+1) { if (j==1) break; } }"
        function = build(source)
        program = decode(function.chunk)
        assert thread_jumps(program) == 0

    def test_a_plain_program_has_nothing_to_thread(self):
        program = decode(build("print 1 + 2;").chunk)
        assert thread_jumps(program) == 0

    def test_a_simple_if_has_nothing_to_thread(self):
        program = decode(build('if (c) print 1; else print 2;').chunk)
        assert thread_jumps(program) == 0

    def test_a_loop_target_is_never_followed_forward(self):
        # following a backward jump forward would leave the loop
        source = "let n = 0; while (n < 3) { n = n + 1; } print n;"
        program = decode(build(source).chunk)
        thread_jumps(program)
        assert optimised_output(source) == ["3"]

    def test_threading_is_idempotent(self):
        function = build(NESTED_IF)
        optimise_deeply(function)
        assert optimise_deeply(function).jumps_threaded == 0


class TestReports:
    def test_a_report_that_changed_nothing_says_so(self):
        assert not Report().changed

    def test_a_report_with_a_removal_says_it_changed(self):
        assert Report(blocks_removed=1, instructions_removed=2).changed

    def test_a_report_with_a_threaded_jump_says_it_changed(self):
        assert Report(jumps_threaded=1).changed

    def test_a_report_renders_its_counts(self):
        rendered = Report(blocks_removed=2, instructions_removed=5, jumps_threaded=1).render()
        assert "5 instructions in 2 unreachable blocks" in rendered
        assert "1 jumps threaded" in rendered

    def test_the_deep_pass_adds_up_the_nested_functions(self):
        source = "fn a() { return 1; } fn b() { return 2; } print a() + b();"
        report = optimise_deeply(build(source))
        assert report.blocks_removed >= 2

    def test_optimising_a_program_directly_reports_the_same_shape(self):
        program = decode(build("fn f() { return 1; } print f();").chunk)
        report = optimise_program(program)
        assert isinstance(report, Report)


class TestIdempotence:
    @pytest.mark.parametrize("source", CORPUS[:8])
    def test_running_the_pass_twice_changes_nothing_further(self, source):
        function = build(source)
        optimise_deeply(function)
        assert not optimise_deeply(function).changed

    @pytest.mark.parametrize("source", CORPUS[:8])
    def test_the_output_is_the_same_after_two_passes(self, source):
        function = build(source)
        optimise_deeply(function)
        optimise_deeply(function)
        machine = VM()
        install_builtins(machine)
        machine.interpret(function)
        assert machine.output == run_output(source)
