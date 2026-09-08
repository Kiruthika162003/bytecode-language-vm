from __future__ import annotations

from ember.function import NativeFunction
from ember.interpreter import run, run_output


class TestFacade:
    def test_run_returns_the_machine(self):
        machine = run("print 1;")
        assert machine.output == ["1"]

    def test_run_output_returns_only_the_lines(self):
        assert run_output("print 1; print 2;") == ["1", "2"]

    def test_builtins_are_installed_by_default(self):
        machine = run("print len([1, 2]);")
        assert machine.output == ["2"]
        assert isinstance(machine.globals["len"], NativeFunction)

    def test_builtins_can_be_turned_off(self):
        machine = run("print 1;", with_builtins=False)
        assert "len" not in machine.globals


class TestEndToEnd:
    def test_a_small_program_computes_a_factorial(self):
        source = (
            "fn fact(n) { if (n <= 1) return 1; return n * fact(n - 1); }"
            " print fact(5);"
        )
        assert run_output(source) == ["120"]

    def test_a_loop_summing_a_list(self):
        source = (
            "let a = [1, 2, 3, 4]; let total = 0;"
            " for (let i = 0; i < len(a); i = i + 1) total = total + a[i];"
            " print total;"
        )
        assert run_output(source) == ["10"]
