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
        assert "23 traces, 0 broken" in captured.out
        assert "[holds] fold:" in captured.out

    def test_check_reports_that_all_hold(self, capsys):
        code = main(["check"])
        assert code == 0
        assert "all traces hold" in capsys.readouterr().out

    def test_summary_counts_the_traces(self, capsys):
        code = main(["summary"])
        assert code == 0
        assert "23 traces (0 broken)" in capsys.readouterr().out


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


class TestLint:
    def test_lint_reports_what_a_reader_would_question(self, capsys, tmp_path):
        path = tmp_path / "smelly.ember"
        path.write_text(
            "fn f(a, b) { let scratch = 1; return a; }" + chr(10) + "print f(1, 2);",
            encoding="utf-8",
        )
        code = main(["lint", str(path)])
        captured = capsys.readouterr()
        # advice, not a failure, so the status stays zero
        assert code == 0
        assert "unused-local" in captured.out
        assert "unused-parameter" in captured.out
        assert "diagnostics" in captured.out

    def test_clean_code_reports_nothing(self, capsys, tmp_path):
        path = tmp_path / "clean.ember"
        path.write_text("fn add(a, b) { return a + b; } print add(1, 2);", encoding="utf-8")
        code = main(["lint", str(path)])
        assert code == 0
        assert "nothing to report" in capsys.readouterr().out

    def test_a_syntax_fault_is_reported(self, capsys, tmp_path):
        path = tmp_path / "bad.ember"
        path.write_text("let x = ;", encoding="utf-8")
        assert main(["lint", str(path)]) == 1
        assert "error:" in capsys.readouterr().err


class TestVerify:
    def test_well_formed_bytecode_says_so(self, capsys, tmp_path):
        path = tmp_path / "plain.ember"
        path.write_text("print 1 + 2;", encoding="utf-8")
        code = main(["verify", str(path)])
        assert code == 0
        assert "well formed" in capsys.readouterr().out

    def test_a_dead_epilogue_is_reported_without_failing(self, capsys, tmp_path):
        path = tmp_path / "returns.ember"
        path.write_text("fn f() { return 1; } print f();", encoding="utf-8")
        code = main(["verify", str(path)])
        captured = capsys.readouterr()
        # a warning is not a fault, so the status stays zero
        assert code == 0
        assert "unreachable-code" in captured.out
        assert "0 of them faults" in captured.out

    def test_the_count_reads_as_a_sentence(self, capsys, tmp_path):
        path = tmp_path / "returns.ember"
        path.write_text("fn f() { return 1; } print f();", encoding="utf-8")
        main(["verify", str(path)])
        assert "1 problem," in capsys.readouterr().out

    def test_a_syntax_fault_is_reported(self, capsys, tmp_path):
        path = tmp_path / "bad.ember"
        path.write_text("let x = ;", encoding="utf-8")
        assert main(["verify", str(path)]) == 1
        assert "error:" in capsys.readouterr().err

    def test_verify_needs_an_argument(self, capsys):
        assert main(["verify"]) == 2
        assert "needs an argument" in capsys.readouterr().err

    def test_a_missing_file_is_refused(self, capsys, tmp_path):
        assert main(["verify", str(tmp_path / "nowhere.ember")]) == 2
        assert "there is no file" in capsys.readouterr().err

    def test_the_usage_mentions_it(self, capsys):
        main([])
        assert "verify <file>" in capsys.readouterr().err


class TestTestCommand:
    def test_a_passing_suite_succeeds(self, capsys, tmp_path):
        path = tmp_path / "suite.ember"
        path.write_text(
            "fn add(a, b) { return a + b; }"
            + chr(10)
            + "fn testAdds() { if (add(1, 2) != 3) throw 1; }",
            encoding="utf-8",
        )
        code = main(["test", str(path)])
        captured = capsys.readouterr()
        assert code == 0
        assert "testAdds: passed" in captured.out
        assert "1 tests: 1 passed" in captured.out

    def test_a_failing_suite_fails_the_command(self, capsys, tmp_path):
        # a failing test is a failing command, which is what a build needs
        path = tmp_path / "suite.ember"
        path.write_text('fn testWrong() { throw "no"; }', encoding="utf-8")
        code = main(["test", str(path)])
        assert code == 1
        assert "failed: no" in capsys.readouterr().out

    def test_a_faulting_test_is_reported_as_an_error(self, capsys, tmp_path):
        path = tmp_path / "suite.ember"
        path.write_text("fn testFaults() { print 1 / 0; }", encoding="utf-8")
        assert main(["test", str(path)]) == 1
        assert "errored" in capsys.readouterr().out

    def test_a_program_with_no_tests_says_so(self, capsys, tmp_path):
        path = tmp_path / "plain.ember"
        path.write_text("print 1;", encoding="utf-8")
        assert main(["test", str(path)]) == 0
        assert "no tests found" in capsys.readouterr().out

    def test_a_syntax_fault_is_reported(self, capsys, tmp_path):
        path = tmp_path / "bad.ember"
        path.write_text("let x = ;", encoding="utf-8")
        assert main(["test", str(path)]) == 1
        assert "error:" in capsys.readouterr().err

    def test_the_usage_mentions_it(self, capsys):
        main([])
        assert "test <file>" in capsys.readouterr().err


class TestCoverageCommand:
    def test_a_fully_covered_program_reports_everything_ran(self, capsys, tmp_path):
        path = tmp_path / "full.ember"
        path.write_text("print 1;" + chr(10) + "print 2;" + chr(10), encoding="utf-8")
        code = main(["coverage", str(path)])
        captured = capsys.readouterr()
        assert code == 0
        assert "100 percent" in captured.out

    def test_a_missed_line_is_named_and_shown(self, capsys, tmp_path):
        path = tmp_path / "partial.ember"
        path.write_text(
            "if (false) {" + chr(10) + '  print "never";' + chr(10) + "}" + chr(10),
            encoding="utf-8",
        )
        code = main(["coverage", str(path)])
        captured = capsys.readouterr()
        # coverage is information, not a verdict, so it still succeeds
        assert code == 0
        assert "never ran" in captured.out
        assert 'print "never";' in captured.out

    def test_a_syntax_fault_is_reported(self, capsys, tmp_path):
        path = tmp_path / "bad.ember"
        path.write_text("let x = ;", encoding="utf-8")
        assert main(["coverage", str(path)]) == 1
        assert "error:" in capsys.readouterr().err

    def test_coverage_needs_an_argument(self, capsys):
        assert main(["coverage"]) == 2
        assert "needs an argument" in capsys.readouterr().err

    def test_the_usage_mentions_it(self, capsys):
        main([])
        assert "coverage <file>" in capsys.readouterr().err


class TestDocsCommand:
    def test_a_reference_is_printed(self, capsys, tmp_path):
        path = tmp_path / "lib.ember"
        path.write_text(
            "// Add two numbers."
            + chr(10)
            + "fn add(a, b) { return a + b; }"
            + chr(10),
            encoding="utf-8",
        )
        code = main(["docs", str(path)])
        captured = capsys.readouterr()
        assert code == 0
        assert "add(a, b)" in captured.out
        assert "Add two numbers." in captured.out

    def test_the_documented_share_is_reported(self, capsys, tmp_path):
        path = tmp_path / "lib.ember"
        path.write_text("fn bare() { return 1; }", encoding="utf-8")
        main(["docs", str(path)])
        assert "0 percent" in capsys.readouterr().out

    def test_a_program_declaring_nothing_says_so(self, capsys, tmp_path):
        path = tmp_path / "plain.ember"
        path.write_text("print 1;", encoding="utf-8")
        assert main(["docs", str(path)]) == 0
        assert "declares nothing" in capsys.readouterr().out

    def test_a_syntax_fault_is_reported(self, capsys, tmp_path):
        path = tmp_path / "bad.ember"
        path.write_text("let x = ;", encoding="utf-8")
        assert main(["docs", str(path)]) == 1
        assert "error:" in capsys.readouterr().err

    def test_the_usage_mentions_it(self, capsys):
        main([])
        assert "docs <file>" in capsys.readouterr().err


class TestTypesCommand:
    def test_a_clean_program_succeeds(self, capsys, tmp_path):
        path = tmp_path / "clean.ember"
        path.write_text("let a = 1; print a + 2;", encoding="utf-8")
        code = main(["types", str(path)])
        captured = capsys.readouterr()
        assert code == 0
        assert "not a proof" in captured.out

    def test_a_definite_mistake_fails_the_command(self, capsys, tmp_path):
        path = tmp_path / "wrong.ember"
        path.write_text('print "a" - 1;', encoding="utf-8")
        code = main(["types", str(path)])
        captured = capsys.readouterr()
        assert code == 1
        assert "not-a-number" in captured.out

    def test_the_count_is_reported(self, capsys, tmp_path):
        path = tmp_path / "wrong.ember"
        path.write_text('print "a" - 1;', encoding="utf-8")
        main(["types", str(path)])
        assert "1 definite mistake" in capsys.readouterr().out

    def test_a_syntax_fault_is_reported(self, capsys, tmp_path):
        path = tmp_path / "bad.ember"
        path.write_text("let x = ;", encoding="utf-8")
        assert main(["types", str(path)]) == 1
        assert "error:" in capsys.readouterr().err

    def test_types_needs_an_argument(self, capsys):
        assert main(["types"]) == 2
        assert "needs an argument" in capsys.readouterr().err

    def test_the_usage_mentions_it(self, capsys):
        main([])
        assert "types <file>" in capsys.readouterr().err


class TestStepCommand:
    def test_the_instructions_are_listed(self, capsys, tmp_path):
        path = tmp_path / "plain.ember"
        path.write_text("print 1 + 2;", encoding="utf-8")
        code = main(["step", str(path)])
        captured = capsys.readouterr()
        assert code == 0
        assert "ADD" in captured.out
        assert "PRINT" in captured.out

    def test_what_the_program_printed_is_shown(self, capsys, tmp_path):
        path = tmp_path / "plain.ember"
        path.write_text("print 1 + 2;", encoding="utf-8")
        main(["step", str(path)])
        captured = capsys.readouterr()
        assert "what it printed:" in captured.out
        assert "  3" in captured.out

    def test_a_runtime_fault_is_part_of_the_trace(self, capsys, tmp_path):
        path = tmp_path / "bad.ember"
        path.write_text("print 1 / 0;", encoding="utf-8")
        code = main(["step", str(path)])
        captured = capsys.readouterr()
        assert code == 1
        assert "then it faulted" in captured.out
        assert "DIVIDE" in captured.out

    def test_a_compile_fault_is_reported_instead(self, capsys, tmp_path):
        path = tmp_path / "bad.ember"
        path.write_text("let x = ;", encoding="utf-8")
        assert main(["step", str(path)]) == 1
        assert "error:" in capsys.readouterr().err

    def test_step_needs_an_argument(self, capsys):
        assert main(["step"]) == 2
        assert "needs an argument" in capsys.readouterr().err

    def test_the_usage_mentions_it(self, capsys):
        main([])
        assert "step <file>" in capsys.readouterr().err


class TestAssembleCommand:
    def test_the_listing_is_printed(self, capsys, tmp_path):
        path = tmp_path / "plain.ember"
        path.write_text("print 1 + 2;", encoding="utf-8")
        code = main(["assemble", str(path)])
        captured = capsys.readouterr()
        assert code == 0
        assert ".function f0" in captured.out
        assert "ADD" in captured.out

    def test_a_nested_function_gets_a_section(self, capsys, tmp_path):
        path = tmp_path / "fn.ember"
        path.write_text("fn add(a, b) { return a + b; } print add(1, 2);", encoding="utf-8")
        main(["assemble", str(path)])
        captured = capsys.readouterr()
        assert ".function f1" in captured.out
        assert chr(34) + "add" + chr(34) in captured.out

    def test_a_syntax_fault_is_reported(self, capsys, tmp_path):
        path = tmp_path / "bad.ember"
        path.write_text("let x = ;", encoding="utf-8")
        assert main(["assemble", str(path)]) == 1
        assert "error:" in capsys.readouterr().err

    def test_assemble_needs_an_argument(self, capsys):
        assert main(["assemble"]) == 2
        assert "needs an argument" in capsys.readouterr().err

    def test_the_usage_mentions_it(self, capsys):
        main([])
        assert "assemble <file>" in capsys.readouterr().err


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
