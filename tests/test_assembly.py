from __future__ import annotations

import pytest

from ember.assembly import from_assembly, round_trips, to_assembly
from ember.builtins import install_builtins
from ember.errors import Compile
from ember.function import Function
from ember.generator import program_for
from ember.interpreter import build, run_output
from ember.traces.verifytrace import CORPUS
from ember.verifier import faults_deeply
from ember.vm import VM

NEWLINE = chr(10)
QUOTE = chr(34)


def assembled_output(source: str) -> list[str]:
    """Write a program out, read it back, and run what came back."""
    function = from_assembly(to_assembly(build(source)))
    machine = VM()
    install_builtins(machine)
    machine.interpret(function)
    return machine.output


def nested_of(function: Function) -> list[Function]:
    return [c for c in function.chunk.constants if isinstance(c, Function)]


def same_tree(one: Function, other: Function) -> bool:
    if list(one.chunk.code) != list(other.chunk.code):
        return False
    ours, theirs = nested_of(one), nested_of(other)
    if len(ours) != len(theirs):
        return False
    return all(same_tree(a, b) for a, b in zip(ours, theirs, strict=True))


class TestTheRoundTrip:
    @pytest.mark.parametrize("source", CORPUS)
    def test_every_corpus_program_round_trips(self, source):
        # the only way to know a format claiming to be reversible is
        original = build(source)
        assert same_tree(original, from_assembly(to_assembly(original)))

    @pytest.mark.parametrize("seed", range(25))
    def test_every_generated_program_round_trips(self, seed):
        original = build(program_for(seed))
        assert same_tree(original, from_assembly(to_assembly(original)))

    @pytest.mark.parametrize("source", CORPUS)
    def test_the_reassembled_program_prints_the_same(self, source):
        assert assembled_output(source) == run_output(source)

    @pytest.mark.parametrize("source", CORPUS)
    def test_the_reassembled_program_verifies(self, source):
        assert faults_deeply(from_assembly(to_assembly(build(source)))) == []

    def test_round_trips_reports_it_directly(self):
        assert round_trips(build("print 1 + 2;"))

    def test_two_classes_can_share_a_method_name(self):
        # the case that made a section's label separate from its function's name
        source = "class A { m() { return 1; } } class B { m() { return 2; } } print A().m();"
        assert same_tree(build(source), from_assembly(to_assembly(build(source))))

    def test_that_case_still_runs_correctly(self):
        source = "class A { m() { return 1; } } class B { m() { return 2; } } print B().m();"
        assert assembled_output(source) == ["2"]

    def test_inheritance_survives(self):
        source = "class A { m() { return 1; } } class B < A { m() { return super.m()+1; } }"
        source += " print B().m();"
        assert assembled_output(source) == ["2"]

    def test_a_closure_with_upvalues_survives(self):
        source = "fn make() { let c = 0; fn inc() { c = c + 1; return c; } return inc; }"
        source += " let g = make(); print g(); print g();"
        assert assembled_output(source) == ["1", "2"]

    def test_defaults_survive(self):
        source = "fn f(a, b = 2) { return a + b; } print f(1);"
        assert assembled_output(source) == ["3"]

    def test_a_variadic_function_survives(self):
        source = "fn f(a, ...rest) { return a + len(rest); } print f(1, 2, 3);"
        assert assembled_output(source) == ["3"]

    def test_a_handler_survives(self):
        source = 'try { print 1 / 0; } catch (e) { print "caught"; }'
        assert assembled_output(source) == ["caught"]


class TestWhatIsWritten:
    def test_a_section_carries_a_generated_label(self):
        assert ".function f0" in to_assembly(build("print 1;"))

    def test_a_section_records_the_real_name(self):
        text = to_assembly(build("fn add(a, b) { return a + b; }"))
        assert "name=" + QUOTE + "add" + QUOTE in text

    def test_the_script_has_an_empty_name(self):
        assert "name=" + QUOTE + QUOTE in to_assembly(build("print 1;"))

    def test_the_arity_is_recorded(self):
        text = to_assembly(build("fn add(a, b) { return a + b; }"))
        assert "arity=2" in text

    def test_a_nested_function_gets_its_own_section(self):
        text = to_assembly(build("fn add(a, b) { return a + b; } print add(1, 2);"))
        assert ".function f1" in text

    def test_a_constant_names_the_section(self):
        text = to_assembly(build("fn add(a, b) { return a + b; } print add(1, 2);"))
        assert "fn f1" in text

    def test_a_variadic_function_is_marked(self):
        assert ".variadic" in to_assembly(build("fn f(...r) { return 1; }"))

    def test_a_plain_function_is_not_marked_variadic(self):
        assert ".variadic" not in to_assembly(build("fn f(a) { return a; }"))

    def test_a_default_is_written(self):
        assert ".default int 2" in to_assembly(build("fn f(a, b = 2) { return a; }"))

    def test_every_section_ends(self):
        text = to_assembly(build("fn a() { return 1; } fn b() { return 2; }"))
        assert text.count(".end") == 3

    def test_a_string_constant_is_quoted(self):
        text = to_assembly(build('print "hi";'))
        assert "string " + QUOTE + "hi" + QUOTE in text

    def test_an_integer_and_a_float_are_told_apart(self):
        text = to_assembly(build("print 1; print 1.5;"))
        assert "int 1" in text
        assert "float 1.5" in text

    def test_an_awkward_string_survives_quoting(self):
        awkward = "a" + QUOTE + "b"
        source = "print " + QUOTE + "a" + chr(92) + QUOTE + "b" + QUOTE + ";"
        rebuilt = from_assembly(to_assembly(build(source)))
        assert awkward in [c for c in rebuilt.chunk.constants if isinstance(c, str)]


class TestLabels:
    def test_a_jump_is_written_as_a_label(self):
        text = to_assembly(build("if (c) print 1; else print 2;"))
        assert "JUMP_IF_FALSE L" in text

    def test_a_label_is_defined_where_the_jump_lands(self):
        text = to_assembly(build("if (c) print 1; else print 2;"))
        assert "L0:" in text

    def test_a_program_with_no_jumps_has_no_labels(self):
        assert "L0" not in to_assembly(build("print 1 + 2;"))

    def test_only_targets_get_labels(self):
        # a listing carries no more names than it needs
        text = to_assembly(build("if (c) print 1;"))
        assert text.count(":") >= 1

    def test_a_loop_jumps_backwards_to_a_label(self):
        text = to_assembly(build("let n = 0; while (n < 3) { n = n + 1; }"))
        assert "LOOP L" in text

    def test_a_label_can_sit_past_the_last_instruction(self):
        # a jump can land just past the end, which needs a label of its own
        source = "let n = 0; while (n < 9) { n = n + 1; if (n == 3) break; }"
        assert round_trips(build(source))


class TestReadingByHand:
    def test_a_minimal_program_can_be_written_by_hand(self):
        text = NEWLINE.join(
            [
                '.function f0 name="" arity=0 upvalues=0',
                "  .const 0 int 7",
                "  CONSTANT 0",
                "  PRINT",
                "  NIL",
                "  RETURN",
                ".end",
            ]
        )
        function = from_assembly(text)
        machine = VM()
        install_builtins(machine)
        machine.interpret(function)
        assert machine.output == ["7"]

    def test_a_hand_written_jump_lands_on_its_label(self):
        text = NEWLINE.join(
            [
                '.function f0 name="" arity=0 upvalues=0',
                "  .const 0 int 1",
                "  .const 1 int 2",
                "  FALSE",
                "  JUMP_IF_FALSE other",
                "  POP",
                "  CONSTANT 0",
                "  PRINT",
                "  JUMP done",
                "other:",
                "  POP",
                "  CONSTANT 1",
                "  PRINT",
                "done:",
                "  NIL",
                "  RETURN",
                ".end",
            ]
        )
        machine = VM()
        install_builtins(machine)
        machine.interpret(from_assembly(text))
        assert machine.output == ["2"]

    def test_a_comment_line_is_ignored(self):
        text = NEWLINE.join(
            [
                "# this is a remark",
                '.function f0 name="" arity=0 upvalues=0',
                "  NIL",
                "  RETURN",
                ".end",
            ]
        )
        assert from_assembly(text).arity == 0

    def test_blank_lines_are_ignored(self):
        text = '.function f0 name="" arity=0 upvalues=0' + NEWLINE * 3
        text += "  NIL" + NEWLINE + "  RETURN" + NEWLINE + ".end"
        assert from_assembly(text).arity == 0


class TestRefusals:
    def test_text_with_no_sections_is_refused(self):
        with pytest.raises(Compile) as caught:
            from_assembly("# nothing here")
        assert "no function sections" in str(caught.value)

    def test_an_instruction_outside_a_section_is_refused(self):
        with pytest.raises(Compile) as caught:
            from_assembly("NIL")
        assert "outside any function section" in str(caught.value)

    def test_a_section_that_never_ends_is_refused(self):
        with pytest.raises(Compile) as caught:
            from_assembly('.function f0 name="" arity=0' + NEWLINE + "  NIL")
        assert "never ended" in str(caught.value)

    def test_a_section_inside_another_is_refused(self):
        text = '.function f0 name="" arity=0' + NEWLINE + '.function f1 name="" arity=0'
        with pytest.raises(Compile) as caught:
            from_assembly(text)
        assert "inside another" in str(caught.value)

    def test_two_sections_with_one_label_are_refused(self):
        text = '.function f0 name="" arity=0' + NEWLINE + "  NIL" + NEWLINE + ".end"
        text += NEWLINE + '.function f0 name="" arity=0' + NEWLINE + "  NIL" + NEWLINE + ".end"
        with pytest.raises(Compile) as caught:
            from_assembly(text)
        assert "has to be unique" in str(caught.value)

    def test_an_unknown_instruction_is_refused(self):
        text = '.function f0 name="" arity=0' + NEWLINE + "  FLYAWAY" + NEWLINE + ".end"
        with pytest.raises(Compile) as caught:
            from_assembly(text)
        assert "is not an instruction" in str(caught.value)

    def test_a_missing_section_reference_is_refused(self):
        text = '.function f0 name="" arity=0' + NEWLINE + "  .const 0 fn f9"
        text += NEWLINE + "  NIL" + NEWLINE + ".end"
        with pytest.raises(Compile) as caught:
            from_assembly(text)
        assert "which is absent" in str(caught.value)

    def test_an_unknown_constant_kind_is_refused(self):
        text = '.function f0 name="" arity=0' + NEWLINE + "  .const 0 colour red"
        text += NEWLINE + "  NIL" + NEWLINE + ".end"
        with pytest.raises(Compile) as caught:
            from_assembly(text)
        assert "not a kind of constant" in str(caught.value)

    def test_an_unquoted_string_constant_is_refused(self):
        text = '.function f0 name="" arity=0' + NEWLINE + "  .const 0 string bare"
        text += NEWLINE + "  NIL" + NEWLINE + ".end"
        with pytest.raises(Compile) as caught:
            from_assembly(text)
        assert "must be quoted" in str(caught.value)

    def test_an_unknown_header_setting_is_refused(self):
        text = '.function f0 colour=red' + NEWLINE + "  NIL" + NEWLINE + ".end"
        with pytest.raises(Compile) as caught:
            from_assembly(text)
        assert "unknown setting" in str(caught.value)

    def test_a_header_with_no_label_is_refused(self):
        with pytest.raises(Compile) as caught:
            from_assembly(".function" + NEWLINE + "  NIL" + NEWLINE + ".end")
        assert "no label" in str(caught.value)

    def test_the_wrong_number_of_operands_is_refused(self):
        text = '.function f0 name="" arity=0' + NEWLINE + "  CONSTANT" + NEWLINE + ".end"
        with pytest.raises(Compile) as caught:
            from_assembly(text)
        assert "takes 1 operands" in str(caught.value)

    def test_an_operand_that_is_neither_a_number_nor_a_label_is_refused(self):
        text = '.function f0 name="" arity=0' + NEWLINE + "  CONSTANT nowhere"
        text += NEWLINE + ".end"
        with pytest.raises(Compile) as caught:
            from_assembly(text)
        assert "neither a number nor a label" in str(caught.value)

    def test_a_name_that_never_closes_is_refused(self):
        text = ".function f0 name=" + QUOTE + "open" + NEWLINE + "  NIL" + NEWLINE + ".end"
        with pytest.raises(Compile) as caught:
            from_assembly(text)
        assert "never closed" in str(caught.value)
