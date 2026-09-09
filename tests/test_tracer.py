from __future__ import annotations

from ember.builtins import install_builtins
from ember.interpreter import build
from ember.opcode import OpCode
from ember.tracer import (
    Step,
    Trace,
    busiest_line,
    report,
    steps_at_line,
    trace,
    where_it_faulted,
)
from ember.vm import VM

NEWLINE = chr(10)

PLAIN = "let a = 1;" + NEWLINE + "let b = 2;" + NEWLINE + "print a + b;" + NEWLINE
LOOP = (
    "let s = 0;"
    + NEWLINE
    + "for (let i = 0; i < 20; i = i + 1) { s = s + i; }"
    + NEWLINE
    + "print s;"
    + NEWLINE
)
RECURSIVE = (
    "fn fib(n) { if (n < 2) return n; return fib(n-1) + fib(n-2); }"
    + NEWLINE
    + "print fib(6);"
    + NEWLINE
)
FAULTING = "print 1;" + NEWLINE + "print 1 / 0;" + NEWLINE


class TestWatchingTheRealMachine:
    def test_a_watched_run_produces_the_same_output(self):
        # the point of a callback rather than a second interpreter
        assert trace(PLAIN).output == ["3"]

    def test_a_watched_recursive_run_gives_the_right_answer(self):
        assert trace(RECURSIVE).output == ["8"]

    def test_a_watched_loop_gives_the_right_answer(self):
        assert trace(LOOP).output == ["190"]

    def test_the_watcher_is_detached_afterwards(self):
        machine = VM()
        install_builtins(machine)
        machine.watch(lambda _machine, _opcode: None)
        machine.watch(None)
        assert machine.watcher is None

    def test_a_machine_with_no_watcher_still_runs(self):
        machine = VM()
        install_builtins(machine)
        machine.interpret(build("print 1;"))
        assert machine.output == ["1"]

    def test_the_watcher_sees_every_instruction(self):
        seen: list[OpCode] = []
        machine = VM()
        install_builtins(machine)
        machine.watch(lambda _machine, opcode: seen.append(opcode))
        machine.interpret(build("print 1 + 2;"))
        assert OpCode.ADD in seen
        assert OpCode.PRINT in seen


class TestSteps:
    def test_a_step_is_recorded_for_each_instruction(self):
        assert trace(PLAIN).count == 10

    def test_the_steps_are_numbered_in_order(self):
        record = trace(PLAIN)
        assert [step.index for step in record.steps] == list(range(record.count))

    def test_a_step_carries_the_line_it_came_from(self):
        assert trace(PLAIN).steps[0].line == 1

    def test_a_step_carries_the_frame_depth(self):
        assert trace(PLAIN).steps[0].depth == 1

    def test_a_step_carries_the_stack_height(self):
        assert trace(PLAIN).steps[0].height == 1

    def test_a_step_shows_the_operands_not_the_result(self):
        # a step is recorded before its instruction runs
        record = trace("print 1 + 2;")
        adding = record.first_of(OpCode.ADD)
        assert adding is not None
        assert adding.top[0] == "2"
        assert adding.top[1] == "1"

    def test_the_effect_appears_in_the_following_step(self):
        record = trace("print 1 + 2;")
        printing = record.first_of(OpCode.PRINT)
        assert printing is not None
        assert printing.top[0] == "3"

    def test_a_step_renders_its_fields(self):
        rendered = Step(
            index=4, opcode=OpCode.ADD, line=7, depth=2, height=3, top=("1", "2")
        ).render()
        assert "line   7" in rendered
        assert "depth 2" in rendered
        assert "ADD" in rendered
        assert "[1, 2]" in rendered

    def test_a_step_with_an_empty_stack_says_so(self):
        rendered = Step(index=0, opcode=OpCode.NIL, line=1, depth=1, height=0).render()
        assert "[empty]" in rendered


class TestDepthAndHeight:
    def test_a_flat_program_never_leaves_one_frame(self):
        assert trace(PLAIN).deepest() == 1

    def test_recursion_reaches_several_frames(self):
        assert trace(RECURSIVE).deepest() > 1

    def test_the_depth_grows_with_the_recursion(self):
        shallow = trace("fn f(n) { if (n < 1) return 0; return f(n-1); } print f(2);")
        deeper = trace("fn f(n) { if (n < 1) return 0; return f(n-1); } print f(5);")
        assert deeper.deepest() > shallow.deepest()

    def test_the_tallest_stack_is_recorded(self):
        assert trace(PLAIN).tallest() >= 2

    def test_an_empty_trace_reports_no_depth(self):
        assert Trace().deepest() == 0
        assert Trace().tallest() == 0


class TestQuerying:
    def test_the_lines_touched_are_listed_in_order(self):
        assert trace(PLAIN).lines_touched() == [1, 2, 3]

    def test_the_opcodes_used_are_listed_in_first_use_order(self):
        used = trace("print 1 + 2;").opcodes_used()
        assert used[0] == OpCode.CONSTANT
        assert OpCode.ADD in used

    def test_an_opcode_appears_once_in_the_list(self):
        used = trace(LOOP).opcodes_used()
        assert len(used) == len(set(used))

    def test_the_counts_add_up_to_the_step_count(self):
        record = trace(LOOP)
        assert sum(record.counts().values()) == record.count

    def test_steps_can_be_asked_for_by_line(self):
        assert len(trace(PLAIN).at_line(3)) == 4

    def test_a_line_with_nothing_on_it_has_no_steps(self):
        assert trace(PLAIN).at_line(99) == []

    def test_the_count_at_a_line_can_be_asked_for_directly(self):
        assert steps_at_line(PLAIN, 3) == 4

    def test_the_first_instance_of_an_opcode_is_found(self):
        found = trace("print 1 + 2;").first_of(OpCode.ADD)
        assert found is not None
        assert found.opcode == OpCode.ADD

    def test_an_absent_opcode_is_not_found(self):
        assert trace("print 1;").first_of(OpCode.MODULO) is None

    def test_the_busiest_line_is_the_loop_body(self):
        line, count = busiest_line(LOOP)
        assert line == 2
        assert count > 100

    def test_an_empty_program_has_no_busiest_line(self):
        assert busiest_line("")[1] >= 0


class TestFaults:
    def test_a_faulting_program_records_its_refusal(self):
        record = trace(FAULTING)
        assert record.refused
        assert "division by zero" in record.refusal

    def test_the_steps_before_the_fault_are_kept(self):
        assert trace(FAULTING).count > 0

    def test_the_output_before_the_fault_is_kept(self):
        assert trace(FAULTING).output == ["1"]

    def test_the_last_step_is_the_instruction_that_faulted(self):
        step = where_it_faulted(FAULTING)
        assert step is not None
        assert step.opcode == OpCode.DIVIDE

    def test_the_faulting_step_shows_the_operands(self):
        step = where_it_faulted(FAULTING)
        assert step is not None
        assert step.top[0] == "0"

    def test_the_faulting_step_names_its_line(self):
        step = where_it_faulted(FAULTING)
        assert step is not None
        assert step.line == 2

    def test_a_clean_program_has_no_faulting_step(self):
        assert where_it_faulted(PLAIN) is None

    def test_the_summary_names_the_fault(self):
        assert "then it faulted" in trace(FAULTING).summary()

    def test_a_clean_trace_is_not_refused(self):
        assert not trace(PLAIN).refused


class TestCapping:
    def test_a_long_run_stops_at_the_cap(self):
        record = trace(LOOP, cap=50)
        assert record.count == 50
        assert record.capped

    def test_a_short_run_is_not_capped(self):
        assert not trace(PLAIN, cap=1000).capped

    def test_the_summary_says_the_run_was_longer(self):
        # rather than letting a reader assume the program ended there
        assert "the run was longer" in trace(LOOP, cap=50).summary()

    def test_a_capped_run_still_finishes(self):
        assert trace(LOOP, cap=10).output == ["190"]

    def test_a_cap_of_one_keeps_one_step(self):
        assert trace(LOOP, cap=1).count == 1


class TestRendering:
    def test_the_report_ends_with_the_summary(self):
        lines = report(PLAIN)
        assert "at the deepest" in lines[-1]

    def test_the_report_can_be_limited(self):
        lines = report(LOOP, limit=5)
        assert any("further steps not shown" in line for line in lines)

    def test_an_unlimited_render_shows_every_step(self):
        record = trace(PLAIN)
        assert len(record.render()) == record.count + 1

    def test_a_limited_render_shows_the_limit_plus_two(self):
        record = trace(LOOP)
        assert len(record.render(limit=5)) == 7

    def test_one_step_reads_in_the_singular(self):
        record = Trace(steps=[Step(index=0, opcode=OpCode.NIL, line=1, depth=1, height=0)])
        assert "1 step," in record.summary()

    def test_one_frame_reads_in_the_singular(self):
        assert "1 frame at the deepest" in trace(PLAIN).summary()


class TestUnderTheOptimiser:
    def test_folding_shortens_the_trace(self):
        plain = trace("print 1 + 2 * 3 - 4;").count
        folded = trace("print 1 + 2 * 3 - 4;", optimize=True).count
        assert folded < plain

    def test_the_answer_is_the_same_either_way(self):
        assert trace("print 1 + 2 * 3 - 4;").output == trace(
            "print 1 + 2 * 3 - 4;", optimize=True
        ).output
