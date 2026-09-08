from __future__ import annotations

from ember.cli import main

FIB_SOURCE = """fn fib(n) {
  if (n < 2) return n;
  return fib(n - 1) + fib(n - 2);
}
print fib(8);
"""


class TestTraceCommands:
    def test_traces_prints_every_claim_and_succeeds(self, capsys):
        code = main(["traces"])
        captured = capsys.readouterr()
        assert code == 0
        assert "11 traces, 0 broken" in captured.out
        assert "[holds] fold:" in captured.out

    def test_check_reports_that_all_hold(self, capsys):
        code = main(["check"])
        assert code == 0
        assert "all traces hold" in capsys.readouterr().out

    def test_summary_counts_the_traces(self, capsys):
        code = main(["summary"])
        assert code == 0
        assert "11 traces (0 broken)" in capsys.readouterr().out


class TestEval:
    def test_eval_prints_program_output(self, capsys):
        code = main(["eval", 'print 1 + 2; print "hi";'])
        captured = capsys.readouterr()
        assert code == 0
        assert captured.out.splitlines() == ["3", "hi"]

    def test_a_runtime_fault_is_reported_without_a_python_traceback(self, capsys):
        code = main(["eval", "print 1 / 0;"])
        captured = capsys.readouterr()
        assert code == 1
        assert "division by zero" in captured.err
        assert "Traceback" not in captured.err

    def test_a_syntax_fault_is_reported(self, capsys):
        code = main(["eval", "print 1 +;"])
        assert code == 1
        assert "error:" in capsys.readouterr().err


class TestFileCommands:
    def test_run_executes_a_file(self, capsys, tmp_path):
        path = tmp_path / "program.ember"
        path.write_text("let x = 1 + 2;\nprint x;\n", encoding="utf-8")
        code = main(["run", str(path)])
        captured = capsys.readouterr()
        assert code == 0
        assert captured.out.strip() == "3"

    def test_disassemble_shows_instructions(self, capsys, tmp_path):
        path = tmp_path / "program.ember"
        path.write_text("let x = 1 + 2;\nprint x;\n", encoding="utf-8")
        code = main(["disassemble", str(path)])
        captured = capsys.readouterr()
        assert code == 0
        assert "== script ==" in captured.out
        assert "ADD" in captured.out

    def test_optimized_shows_the_folded_form(self, capsys, tmp_path):
        path = tmp_path / "program.ember"
        path.write_text("let x = 1 + 2;\nprint x;\n", encoding="utf-8")
        code = main(["optimized", str(path)])
        captured = capsys.readouterr()
        assert code == 0
        assert "== optimized ==" in captured.out
        # the addition folded away, so no ADD survives
        assert "ADD" not in captured.out

    def test_a_missing_file_is_reported(self, capsys, tmp_path):
        code = main(["run", str(tmp_path / "nope.ember")])
        assert code == 2
        assert "there is no file at" in capsys.readouterr().err


class TestProfile:
    def test_profile_reports_where_the_work_went(self, capsys, tmp_path):
        path = tmp_path / "program.ember"
        path.write_text(FIB_SOURCE, encoding="utf-8")
        code = main(["profile", str(path)])
        captured = capsys.readouterr()
        assert code == 0
        assert "21" in captured.out
        assert "instructions dispatched" in captured.out
        assert "by instruction:" in captured.out
        assert "by line:" in captured.out

    def test_a_fault_while_profiling_is_reported(self, capsys, tmp_path):
        path = tmp_path / "bad.ember"
        path.write_text("print 1 / 0;", encoding="utf-8")
        code = main(["profile", str(path)])
        assert code == 1
        assert "error:" in capsys.readouterr().err


class TestFormat:
    def test_format_prints_a_canonical_layout(self, capsys, tmp_path):
        path = tmp_path / "messy.ember"
        path.write_text('let x=1+2*3;if(x>3){print "big";}', encoding="utf-8")
        code = main(["format", str(path)])
        captured = capsys.readouterr()
        assert code == 0
        assert "let x = 1 + 2 * 3;" in captured.out
        assert "if (x > 3) {" in captured.out
        assert '  print "big";' in captured.out

    def test_a_syntax_fault_is_reported(self, capsys, tmp_path):
        path = tmp_path / "bad.ember"
        path.write_text("let x = ;", encoding="utf-8")
        code = main(["format", str(path)])
        assert code == 1
        assert "error:" in capsys.readouterr().err


class TestRepl:
    def test_it_evaluates_lines_and_ends_on_end_of_input(self, capsys, monkeypatch):
        lines = iter(["1 + 2;", "fn dbl(x) { return x * 2; }", "dbl(4);"])

        def fake_input(prompt: str = "") -> str:
            print(prompt, end="")
            try:
                return next(lines)
            except StopIteration:
                raise EOFError from None

        monkeypatch.setattr("builtins.input", fake_input)
        code = main(["repl"])
        captured = capsys.readouterr()
        assert code == 0
        assert "3" in captured.out
        assert "8" in captured.out

    def test_a_fault_does_not_end_the_session(self, capsys, monkeypatch):
        lines = iter(["1 / 0;", "let n = 4;", "n + 1;"])

        def fake_input(_prompt: str = "") -> str:
            try:
                return next(lines)
            except StopIteration:
                raise EOFError from None

        monkeypatch.setattr("builtins.input", fake_input)
        assert main(["repl"]) == 0
        captured = capsys.readouterr()
        assert "division by zero" in captured.err
        assert "5" in captured.out


class TestUsage:
    def test_no_arguments_prints_usage(self, capsys):
        assert main([]) == 2
        assert "usage:" in capsys.readouterr().err

    def test_an_unknown_command_prints_usage(self, capsys):
        assert main(["bogus"]) == 2
        assert "unknown command" in capsys.readouterr().err

    def test_a_command_missing_its_argument_is_reported(self, capsys):
        assert main(["run"]) == 2
        assert "needs an argument" in capsys.readouterr().err
