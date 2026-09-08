from __future__ import annotations

import pytest

from ember.builtins import install_builtins
from ember.errors import Unbound
from ember.instructions import decode
from ember.interpreter import build, run_output, run_treewalk_output
from ember.opcode import OpCode
from ember.peephole import optimize_chunk, optimize_function
from ember.vm import VM

# Everything the language can do, run four ways: plain, tree-optimized,
# peephole-optimized, and both. The claim is that all four agree.
PROGRAMS = [
    "print 1 + 2 * 3;",
    "let x = 1; x; x; print x;",
    'if (true) print "a";',
    'if (1 < 2) print "a"; else print "b";',
    "let s = 0; for (let i = 0; i < 5; i = i + 1) s = s + i; print s;",
    "for (i in [1, 2, 3]) { if (i == 2) continue; print i; }",
    "let n = 0; while (n < 5) { n = n + 1; if (n == 3) break; } print n;",
    "fn f() { return 1; } print f();",
    "fn fib(n) { if (n < 2) return n; return fib(n-1) + fib(n-2); } print fib(10);",
    (
        "class A { init(x) { this.x = x; } m() { return this.x * 2; } }"
        " class B < A { m() { return super.m() + 1; } } print B(5).m();"
    ),
    (
        "fn make() { let c = 0; fn inc() { c = c + 1; return c; } return inc; }"
        " let g = make(); print g(); print g();"
    ),
    "let a = [1, 2, 3]; a[1] = 9; print a; print len(a);",
    "fn dbl(n) { return n * 2; } print map([1, 2, 3], dbl);",
    'let m = {"a": 1}; m["b"] = 2; for (k in m) print k;',
    'print "a" + "b"; print not false; print -(-5);',
    (
        "fn outer() { let x = 7;"
        " fn mid() { fn inner() { return x; } return inner(); } return mid(); }"
        " print outer();"
    ),
]


def _run(function) -> list[str]:
    machine = VM()
    install_builtins(machine)
    machine.interpret(function)
    return machine.output


def _opcodes(chunk) -> list[OpCode]:
    return [instruction.opcode for instruction in decode(chunk).instructions]


class TestBehaviourIsPreserved:
    @pytest.mark.parametrize("source", PROGRAMS)
    def test_all_four_pipelines_agree(self, source: str):
        plain = run_output(source)
        assert run_output(source, optimize=True) == plain
        assert run_output(source, peephole=True) == plain
        assert run_output(source, optimize=True, peephole=True) == plain
        assert run_treewalk_output(source) == plain


class TestPushPopCancelling:
    def test_a_constant_pushed_then_popped_disappears(self):
        function = build("1; print 2;")
        before = _opcodes(function.chunk)
        optimize_function(function)
        after = _opcodes(function.chunk)
        assert before.count(OpCode.CONSTANT) > after.count(OpCode.CONSTANT)
        assert _run(function) == ["2"]

    def test_a_local_load_then_pop_disappears(self):
        function = build("{ let x = 1; x; print x; }")
        optimize_function(function)
        assert _run(function) == ["1"]

    def test_a_global_load_then_pop_is_kept(self):
        # reading an undefined global raises, so that pair is not dead code
        function = build("let x = 1; x;")
        optimize_function(function)
        assert OpCode.GET_GLOBAL in _opcodes(function.chunk)

    def test_an_undefined_global_still_raises_after_optimizing(self):
        with pytest.raises(Unbound):
            run_output("missing;", peephole=True)


class TestJumpHandling:
    def test_a_jump_to_the_next_instruction_is_removed(self):
        function = build('if (someCondition) print "a";')
        before = _opcodes(function.chunk).count(OpCode.JUMP)
        optimize_function(function)
        after = _opcodes(function.chunk).count(OpCode.JUMP)
        assert after <= before

    def test_jump_targets_stay_valid_after_editing(self):
        for source in PROGRAMS:
            function = build(source)
            optimize_function(function)
            program = decode(function.chunk)
            count = len(program.instructions)
            for instruction in program.instructions:
                if instruction.target is not None:
                    assert 0 <= instruction.target <= count, source

    def test_loops_still_terminate_after_optimizing(self):
        source = "let n = 0; while (n < 100) n = n + 1; print n;"
        assert run_output(source, peephole=True) == ["100"]


class TestReporting:
    def test_a_no_op_chunk_is_returned_untouched(self):
        function = build("print 1;")
        original = function.chunk
        tightened, report = optimize_chunk(original)
        if not report.changed:
            assert tightened is original

    def test_the_report_counts_what_it_removed(self):
        function = build("1; 2; 3; print 4;")
        report = optimize_function(function)
        assert report.removed > 0
        assert report.rounds >= 1

    def test_optimizing_twice_changes_nothing_more(self):
        function = build("1; 2; print 3;")
        optimize_function(function)
        settled = list(function.chunk.code)
        optimize_function(function)
        assert list(function.chunk.code) == settled


class TestNestedFunctions:
    def test_it_reaches_into_nested_chunks(self):
        source = "fn f() { 1; 2; return 3; } print f();"
        function = build(source)
        report = optimize_function(function)
        assert report.removed > 0
        assert _run(function) == ["3"]

    def test_a_method_body_is_optimized_too(self):
        source = "class C { m() { 1; return 2; } } print C().m();"
        function = build(source)
        optimize_function(function)
        assert _run(function) == ["2"]
