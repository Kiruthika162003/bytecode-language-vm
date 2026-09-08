from __future__ import annotations

from ember.cli import main


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
