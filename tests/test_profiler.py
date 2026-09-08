from __future__ import annotations

import pytest

from ember.builtins import install_builtins
from ember.errors import EmberError
from ember.interpreter import build
from ember.opcode import OpCode
from ember.profiler import Profile, render
from ember.vm import VM

FIB = """fn fib(n) {
  if (n < 2) return n;
  return fib(n - 1) + fib(n - 2);
}
print fib(10);
"""


def _profile(source: str) -> tuple[Profile, VM]:
    machine = VM()
    install_builtins(machine)
    profile = machine.enable_profiling()
    machine.interpret(build(source))
    return profile, machine


class TestProfileTallies:
    def test_recording_counts_both_views(self):
        profile = Profile()
        profile.record(OpCode.ADD, 3)
        profile.record(OpCode.ADD, 3)
        profile.record(OpCode.POP, 4)
        assert profile.opcode_counts[OpCode.ADD] == 2
        assert profile.line_counts[3] == 2
        assert profile.line_counts[4] == 1
        assert profile.total == 3

    def test_frames_are_counted_separately(self):
        profile = Profile()
        profile.record_frame()
        profile.record_frame()
        assert profile.frames_entered == 2

    def test_share_of_an_opcode(self):
        profile = Profile()
        profile.record(OpCode.ADD, 1)
        profile.record(OpCode.POP, 1)
        assert profile.share_of(OpCode.ADD) == 0.5
        assert profile.share_of(OpCode.MULTIPLY) == 0.0

    def test_share_of_an_empty_profile_is_zero(self):
        assert Profile().share_of(OpCode.ADD) == 0.0


class TestHottest:
    def test_the_hottest_line_is_the_most_executed(self):
        profile = Profile()
        for _ in range(5):
            profile.record(OpCode.ADD, 7)
        profile.record(OpCode.ADD, 2)
        assert profile.hottest_line() == (7, 5)

    def test_a_tie_breaks_toward_the_earlier_line(self):
        # stable across runs, which is what lets a test assert on it
        profile = Profile()
        profile.record(OpCode.ADD, 9)
        profile.record(OpCode.ADD, 4)
        assert profile.hottest_line() == (4, 1)

    def test_the_hottest_opcode_is_reported(self):
        profile = Profile()
        profile.record(OpCode.GET_LOCAL, 1)
        profile.record(OpCode.GET_LOCAL, 1)
        profile.record(OpCode.POP, 1)
        assert profile.hottest_opcode() == (OpCode.GET_LOCAL, 2)

    def test_an_empty_profile_has_no_hottest(self):
        with pytest.raises(EmberError):
            Profile().hottest_line()
        with pytest.raises(EmberError):
            Profile().hottest_opcode()


class TestOrdering:
    def test_by_opcode_is_sorted_by_count(self):
        profile = Profile()
        profile.record(OpCode.POP, 1)
        for _ in range(3):
            profile.record(OpCode.ADD, 1)
        assert profile.by_opcode()[0] == (OpCode.ADD, 3)

    def test_a_limit_truncates(self):
        profile = Profile()
        profile.record(OpCode.ADD, 1)
        profile.record(OpCode.POP, 2)
        assert len(profile.by_opcode(1)) == 1
        assert len(profile.by_line(1)) == 1


class TestAgainstTheMachine:
    def test_profiling_is_off_by_default(self):
        machine = VM()
        install_builtins(machine)
        machine.interpret(build("print 1;"))
        assert machine.profile is None

    def test_the_total_matches_the_machines_own_count(self):
        profile, machine = _profile(FIB)
        assert profile.total == machine.instruction_count

    def test_it_finds_the_recursive_line(self):
        profile, _ = _profile(FIB)
        line, count = profile.hottest_line()
        # lines 2 and 3 are the recursion; the base-case test runs most often
        assert line in (2, 3)
        assert count > 100

    def test_frames_match_the_call_count(self):
        profile, _ = _profile(FIB)
        # fib(10) makes 177 calls, one frame each
        assert profile.frames_entered == 177

    def test_profiling_does_not_change_the_output(self):
        profile, machine = _profile(FIB)
        plain = VM()
        install_builtins(plain)
        plain.interpret(build(FIB))
        assert machine.output == plain.output
        assert profile.total == plain.instruction_count

    def test_a_loop_body_dominates_a_loop(self):
        source = "let t = 0;\nfor (let i = 0; i < 50; i = i + 1) {\n  t = t + i;\n}\nprint t;"
        profile, machine = _profile(source)
        assert machine.output == ["1225"]
        assert profile.line_counts[3] > profile.line_counts[1]


class TestRender:
    def test_it_reports_totals_and_both_views(self):
        profile, _ = _profile(FIB)
        text = render(profile, FIB)
        assert "instructions dispatched" in text
        assert "by instruction:" in text
        assert "by line:" in text
        assert "GET_LOCAL" in text

    def test_it_quotes_the_source_line_when_given_the_source(self):
        profile, _ = _profile(FIB)
        assert "if (n < 2) return n;" in render(profile, FIB)

    def test_it_works_without_the_source(self):
        profile, _ = _profile(FIB)
        text = render(profile, None)
        assert "by line:" in text
        assert "if (n < 2)" not in text

    def test_an_empty_profile_renders_without_dividing_by_zero(self):
        assert "0 instructions dispatched" in render(Profile())
