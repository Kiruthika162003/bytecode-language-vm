from __future__ import annotations

import pytest

from ember.builtins import install_builtins
from ember.diagnostics import (
    describe,
    excerpt,
    format_call_stack,
    format_frame,
    line_text,
)
from ember.errors import EmberError
from ember.interpreter import build
from ember.vm import VM

SOURCE = 'let x = 1;\nprint x + "a";\nprint 2;'


class TestLineText:
    def test_it_returns_the_requested_line(self):
        assert line_text(SOURCE, 2) == 'print x + "a";'

    def test_line_zero_is_refused(self):
        with pytest.raises(EmberError):
            line_text(SOURCE, 0)

    def test_a_line_past_the_end_is_refused(self):
        with pytest.raises(EmberError):
            line_text(SOURCE, 99)


class TestExcerpt:
    def test_it_numbers_the_line_and_shows_the_text(self):
        rendered = excerpt(SOURCE, 2)
        assert 'print x + "a";' in rendered
        assert rendered.startswith("2 | ")

    def test_a_caret_sits_under_the_column(self):
        rendered = excerpt(SOURCE, 2, 9)
        caret_line = rendered.splitlines()[1]
        text_line = rendered.splitlines()[0]
        assert caret_line.strip() == "^"
        # the caret's index matches the character it points at
        assert text_line[caret_line.index("^")] == "+"

    def test_context_includes_neighbouring_lines(self):
        rendered = excerpt(SOURCE, 2, context=1)
        assert "let x = 1;" in rendered
        assert "print 2;" in rendered

    def test_no_caret_when_no_column_is_given(self):
        assert "^" not in excerpt(SOURCE, 2)

    def test_a_line_out_of_range_is_refused(self):
        with pytest.raises(EmberError):
            excerpt(SOURCE, 99, 1)

    def test_a_column_below_one_is_refused(self):
        with pytest.raises(EmberError):
            excerpt(SOURCE, 2, 0)

    def test_negative_context_is_refused(self):
        with pytest.raises(EmberError):
            excerpt(SOURCE, 2, context=-1)


class TestDescribe:
    def test_it_puts_the_message_above_the_excerpt(self):
        rendered = describe(SOURCE, "cannot add these", 2, 9)
        assert rendered.splitlines()[0] == "cannot add these"
        assert "^" in rendered


class TestCallStack:
    def test_a_frame_is_named_and_placed(self):
        assert format_frame("inner", 7) == "  in inner at line 7"

    def test_an_unnamed_frame_is_the_script(self):
        assert "script" in format_frame("", 1)

    def test_the_stack_lists_frames_innermost_first(self):
        rendered = format_call_stack([("inner", 7), ("outer", 3), ("", 1)])
        lines = rendered.splitlines()
        assert "inner" in lines[0]
        assert "outer" in lines[1]
        assert "script" in lines[2]


class TestVirtualMachineReporting:
    def test_the_machine_reports_the_line_it_faulted_on(self):
        machine = VM()
        install_builtins(machine)
        with pytest.raises(EmberError):
            machine.interpret(build("print 1;\nprint 2;\nprint 1 / 0;"))
        assert machine.current_line() == 3

    def test_the_call_stack_names_every_active_function(self):
        source = "fn inner() { return 1 / 0; }\nfn outer() { return inner(); }\nprint outer();"
        machine = VM()
        install_builtins(machine)
        with pytest.raises(EmberError):
            machine.interpret(build(source))
        stack = machine.call_stack()
        assert [name for name, _ in stack] == ["inner", "outer", ""]
        assert [line for _, line in stack] == [1, 2, 3]

    def test_a_clean_run_still_reports_a_stack(self):
        machine = VM()
        install_builtins(machine)
        machine.interpret(build("print 1;"))
        assert machine.call_stack() == []
