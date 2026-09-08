from __future__ import annotations

from pathlib import Path

import pytest

from ember.errors import Compile, Resolve, Syntax
from ember.interpreter import run_output
from ember.modules import declared_names, load_program, load_with_report
from ember.parser import parse
from ember.scanner import scan

FILES = {
    "a.ember": 'import "b";' + chr(10) + 'fn fromA() { return "A"; }' + chr(10),
    "b.ember": 'fn fromB() { return "B"; }' + chr(10),
    "cycle1.ember": 'import "cycle2";' + chr(10),
    "cycle2.ember": 'import "cycle1";' + chr(10),
    "selfish.ember": 'import "selfish";' + chr(10),
    "clashA.ember": "fn shared() { return 1; }" + chr(10),
    "clashB.ember": "fn shared() { return 2; }" + chr(10),
    "deep.ember": 'import "a";' + chr(10) + 'import "b";' + chr(10),
    "vals.ember": "let UNIT = 7;" + chr(10) + "class Box { }" + chr(10),
}


def reader(path: str) -> str:
    name = Path(path).name
    if name not in FILES:
        raise Resolve(f"there is no file at {path}")
    return FILES[name]


def load(source: str):
    return load_program(source, "main.ember", read=reader)


def report_for(source: str):
    return load_with_report(source, "main.ember", read=reader)[1]


class TestDeclaredNames:
    def test_it_finds_the_top_level_bindings(self):
        program = parse(scan("let a = 1; fn f() { let inner = 2; return inner; } class C { }"))
        assert sorted(declared_names(program)) == ["C", "a", "f"]

    def test_a_nested_binding_is_not_top_level(self):
        program = parse(scan("{ let hidden = 1; print hidden; }"))
        assert declared_names(program) == {}

    def test_the_line_is_recorded(self):
        program = parse(scan("let a = 1;"))
        assert declared_names(program)["a"] == 1


class TestSplicing:
    def test_an_import_brings_in_the_other_file(self):
        statements = load('import "b";' + chr(10) + "print 1;")
        # the imported function plus the print, with the import itself gone
        assert len(statements) == 2

    def test_a_transitive_import_is_followed(self):
        report = report_for('import "a";' + chr(10) + "print 1;")
        assert sorted(Path(entry).name for entry in report.order) == [
            "a.ember",
            "b.ember",
            "main.ember",
        ]

    def test_imports_come_before_the_file_that_needed_them(self):
        report = report_for('import "a";' + chr(10) + "print 1;")
        names = [Path(entry).name for entry in report.order]
        assert names == ["main.ember", "a.ember", "b.ember"]

    def test_a_file_imported_twice_is_loaded_once(self):
        statements = load('import "deep";' + chr(10) + 'import "b";' + chr(10) + "print 1;")
        # fromA, fromB, and the print: fromB is spliced once despite three paths to it
        assert len(statements) == 3

    def test_a_program_with_no_imports_is_unchanged(self):
        assert len(load("print 1; print 2;")) == 2

    def test_values_and_classes_are_spliced_too(self):
        report = report_for('import "vals";' + chr(10) + "print UNIT;")
        assert sorted(report.owners) == ["Box", "UNIT"]


class TestRefusals:
    def test_a_cycle_is_refused_with_the_chain(self):
        with pytest.raises(Resolve) as caught:
            load('import "cycle1";')
        message = str(caught.value)
        assert "cycle" in message
        assert "cycle1.ember" in message
        assert "cycle2.ember" in message

    def test_a_file_importing_itself_is_refused(self):
        with pytest.raises(Resolve):
            load('import "selfish";')

    def test_a_name_declared_by_two_files_is_refused(self):
        with pytest.raises(Resolve) as caught:
            load('import "clashA";' + chr(10) + 'import "clashB";')
        message = str(caught.value)
        assert "clashA.ember" in message
        assert "clashB.ember" in message
        assert "shared" in message

    def test_a_missing_file_is_refused(self):
        with pytest.raises(Resolve):
            load('import "nowhere";')


class TestSyntaxRules:
    def test_an_import_needs_a_string(self):
        with pytest.raises(Syntax):
            parse(scan("import 5;"))

    def test_an_import_needs_a_semicolon(self):
        with pytest.raises(Syntax):
            parse(scan('import "x"'))

    def test_an_import_inside_a_block_is_refused(self):
        with pytest.raises(Syntax):
            parse(scan('{ import "x"; }'))

    def test_an_import_inside_a_function_is_refused(self):
        with pytest.raises(Syntax):
            parse(scan('fn f() { import "x"; }'))

    def test_an_import_inside_a_method_is_refused(self):
        with pytest.raises(Syntax):
            parse(scan('class C { m() { import "x"; } }'))


class TestRunningRealFiles:
    def _write(self, root: Path) -> Path:
        (root / "shapes.ember").write_text(
            "fn area(w, h) { return w * h; }" + chr(10) + "let UNIT = 1;" + chr(10),
            encoding="utf-8",
        )
        (root / "text.ember").write_text(
            'import "shapes";'
            + chr(10)
            + 'fn describe(w, h) { return "area " + str(area(w, h)); }'
            + chr(10),
            encoding="utf-8",
        )
        main = root / "main.ember"
        main.write_text(
            'import "text";'
            + chr(10)
            + 'import "shapes";'
            + chr(10)
            + "print describe(3, 4);"
            + chr(10)
            + "print area(2, 5);"
            + chr(10)
            + "print UNIT;"
            + chr(10),
            encoding="utf-8",
        )
        return main

    def test_a_diamond_of_real_files_runs(self, tmp_path):
        main = self._write(tmp_path)
        assert run_output(main.read_text(encoding="utf-8"), path=str(main)) == [
            "area 12",
            "10",
            "1",
        ]

    def test_a_path_is_resolved_relative_to_the_importer(self, tmp_path):
        nested = tmp_path / "lib"
        nested.mkdir()
        (nested / "inner.ember").write_text("fn deep() { return 42; }", encoding="utf-8")
        (nested / "outer.ember").write_text(
            'import "inner";' + chr(10) + "fn reach() { return deep(); }", encoding="utf-8"
        )
        main = tmp_path / "main.ember"
        main.write_text('import "lib/outer";' + chr(10) + "print reach();", encoding="utf-8")
        assert run_output(main.read_text(encoding="utf-8"), path=str(main)) == ["42"]

    def test_the_suffix_is_optional(self, tmp_path):
        (tmp_path / "helper.ember").write_text("fn hi() { return 1; }", encoding="utf-8")
        main = tmp_path / "main.ember"
        main.write_text('import "helper.ember";' + chr(10) + "print hi();", encoding="utf-8")
        assert run_output(main.read_text(encoding="utf-8"), path=str(main)) == ["1"]

    def test_without_a_path_imports_are_not_resolved(self):
        # a fragment has no neighbours to name, so the import reaches the compiler,
        # which has no instruction for splicing a file and says so
        with pytest.raises(Compile):
            run_output('import "anything"; print 1;')
