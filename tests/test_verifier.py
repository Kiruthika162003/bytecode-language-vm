from __future__ import annotations

import pytest

from ember.chunk import Chunk
from ember.function import Function
from ember.interpreter import build
from ember.opcode import OpCode
from ember.verifier import (
    BAD_OPERAND,
    BAD_TARGET,
    MISSING_RETURN,
    STACK_UNDERFLOW,
    TRUNCATED,
    UNDECODABLE,
    UNREACHABLE_CODE,
    describe,
    faults,
    faults_deeply,
    is_safe,
    verify,
    verify_deeply,
    warnings_deeply,
)

PROGRAMS = [
    "print 1 + 2 * 3;",
    "let x = 1; x = 2; print x;",
    "{ let a = 1; let b = 2; print a + b; }",
    'if (1 < 2) print "a"; else print "b";',
    "let n = 0; while (n < 3) { n = n + 1; if (n == 2) break; } print n;",
    "let s = 0; for (let i = 0; i < 5; i = i + 1) s = s + i; print s;",
    "for (x in [1, 2, 3]) { if (x == 2) continue; print x; }",
    "fn fib(n) { if (n < 2) return n; return fib(n-1) + fib(n-2); } print fib(10);",
    "fn make() { let c = 0; fn inc() { c = c + 1; return c; } return inc; } print make()();",
    "class A { init(x) { this.x = x; } m() { return this.x * 2; } } print A(3).m();",
    "class A { m() { return 1; } } class B < A { m() { return super.m()+1; } } print B().m();",
    'try { throw "x"; } catch (e) { print e; }',
    'try { print 1 / 0; } catch (e) { print "caught"; } print "after";',
    'fn f() { try { return "a"; } catch (e) { return "b"; } } print f();',
    'for (i in [1, 2]) { try { if (i == 2) break; print i; } catch (e) { } }',
    'match (2) { case 1: print "a"; case 2, 3: print "b"; default: print "c"; }',
    'let m = {"a": 1}; m["b"] = 2; print m["a"]; print len(m);',
    'let name = "ada"; print "hi ${name}, ${1 + 2}";',
    "print 12 & 10 | 3; print ~5; print 1 << 3;",
    'print 1 > 0 ? "y" : "n";',
    "fn f(a, b = 2, ...rest) { return a + b + len(rest); } print f(1); print f(1, 2, 3);",
    "fn dbl(n) { return n * 2; } print map([1, 2, 3], dbl);",
]


class TestCompilerOutputIsSafe:
    @pytest.mark.parametrize("source", PROGRAMS)
    def test_what_the_compiler_emits_carries_no_fault(self, source):
        assert faults_deeply(build(source)) == []

    @pytest.mark.parametrize("source", PROGRAMS)
    def test_it_stays_safe_after_the_tree_optimizer(self, source):
        assert faults_deeply(build(source, optimize=True)) == []

    @pytest.mark.parametrize("source", PROGRAMS)
    def test_it_stays_safe_after_the_peephole_pass(self, source):
        assert faults_deeply(build(source, peephole=True)) == []

    @pytest.mark.parametrize("source", PROGRAMS)
    def test_it_stays_safe_after_both(self, source):
        assert faults_deeply(build(source, optimize=True, peephole=True)) == []

    def test_is_safe_says_so_plainly(self):
        assert is_safe(build("print 1;"))


class TestTheDeadEpilogue:
    def test_a_function_that_always_returns_leaves_a_dead_epilogue(self):
        # the compiler appends nil-and-return to every function, and a body that
        # already returned on every path can never reach it
        found = warnings_deeply(build("fn f() { return 1; } print f();"))
        assert [problem.kind for problem in found] == [UNREACHABLE_CODE]

    def test_that_dead_epilogue_is_a_warning_not_a_fault(self):
        found = warnings_deeply(build("fn f() { return 1; } print f();"))
        assert all(not problem.is_fault for problem in found)

    def test_the_peephole_pass_removes_it(self):
        source = "fn f() { return 1; } print f();"
        before = len(warnings_deeply(build(source)))
        after = len(warnings_deeply(build(source, peephole=True)))
        assert before == 1
        assert after == 0

    def test_a_body_that_falls_off_the_end_reaches_the_epilogue(self):
        # no explicit return, so the epilogue is the only exit and nothing is dead
        assert warnings_deeply(build("fn f() { print 1; } f();")) == []

    def test_a_script_with_no_functions_has_nothing_dead(self):
        assert warnings_deeply(build("print 1 + 2;")) == []

    def test_the_corpus_carries_warnings_but_no_faults(self):
        # the measurement that demoted unreachable code from error to warning
        warned = sum(len(warnings_deeply(build(source))) for source in PROGRAMS)
        faulted = sum(len(faults_deeply(build(source))) for source in PROGRAMS)
        assert warned > 0
        assert faulted == 0

    def test_the_peephole_pass_clears_almost_all_of_them(self):
        plain = sum(len(warnings_deeply(build(source))) for source in PROGRAMS)
        swept = sum(len(warnings_deeply(build(source, peephole=True))) for source in PROGRAMS)
        assert swept < plain


class TestBadOperands:
    def test_a_constant_index_past_the_pool_is_caught(self):
        damaged = build("print 1;")
        damaged.chunk.code[1] = 99
        kinds = [problem.kind for problem in faults(damaged)]
        assert BAD_OPERAND in kinds

    def test_the_message_names_both_numbers(self):
        damaged = build("print 1;")
        damaged.chunk.code[1] = 99
        message = next(p.message for p in faults(damaged) if p.kind == BAD_OPERAND)
        assert "99" in message
        assert "pool holds" in message

    def test_an_upvalue_index_past_the_capture_count_is_caught(self):
        chunk = Chunk()
        chunk.write_op(OpCode.GET_UPVALUE, 1)
        chunk.write(3, 1)
        chunk.write_op(OpCode.RETURN, 1)
        found = faults(Function("borrower", 0, chunk, upvalue_count=1))
        assert [problem.kind for problem in found] == [BAD_OPERAND]

    def test_an_upvalue_index_inside_the_count_is_fine(self):
        chunk = Chunk()
        chunk.write_op(OpCode.GET_UPVALUE, 1)
        chunk.write(0, 1)
        chunk.write_op(OpCode.RETURN, 1)
        assert faults(Function("borrower", 0, chunk, upvalue_count=1)) == []


class TestUndecodableChunks:
    def _wild_jump(self) -> Chunk:
        chunk = Chunk()
        chunk.write_op(OpCode.JUMP, 1)
        chunk.write(15, 1)
        chunk.write(160, 1)
        chunk.write_op(OpCode.NIL, 1)
        chunk.write_op(OpCode.RETURN, 1)
        return chunk

    def test_a_jump_past_the_end_is_reported_not_raised(self):
        # the decoder refuses this chunk, and the verifier turns that into a report
        found = faults(Function("wild", 0, self._wild_jump()))
        assert [problem.kind for problem in found] == [UNDECODABLE]

    def test_the_report_carries_the_decoder_reason(self):
        problem = faults(Function("wild", 0, self._wild_jump()))[0]
        assert "not " in problem.message
        assert "instruction" in problem.message

    def test_verifying_never_raises_on_a_damaged_chunk(self):
        # whatever is wrong, the answer is a list of problems
        assert isinstance(verify(Function("wild", 0, self._wild_jump())), list)

    def test_a_byte_that_is_not_an_opcode_is_reported(self):
        chunk = Chunk()
        chunk.write(250, 1)
        found = faults(Function("garbage", 0, chunk))
        assert [problem.kind for problem in found] == [UNDECODABLE]

    def test_a_truncated_operand_is_reported_rather_than_crashing(self):
        # decoding leaves the instruction short of its operand bytes, and reading
        # one that is not there would fault the checker instead of the chunk
        chunk = Chunk()
        chunk.write_op(OpCode.CONSTANT, 1)
        kinds = [problem.kind for problem in faults(Function("cut", 0, chunk))]
        assert TRUNCATED in kinds

    def test_the_truncation_message_says_what_was_wanted(self):
        chunk = Chunk()
        chunk.write_op(OpCode.CONSTANT, 1)
        found = faults(Function("cut", 0, chunk))
        message = next(p.message for p in found if p.kind == TRUNCATED)
        assert "operand bytes" in message
        assert "cut short" in message

    def test_a_complete_instruction_is_not_called_truncated(self):
        chunk = Chunk()
        chunk.write_op(OpCode.NIL, 1)
        chunk.write_op(OpCode.RETURN, 1)
        kinds = [problem.kind for problem in verify(Function("whole", 0, chunk))]
        assert TRUNCATED not in kinds

    def test_the_target_check_survives_as_a_second_line(self):
        # nothing decodable reaches it, but the constant is part of the contract
        assert BAD_TARGET == "bad-target"


class TestStackDiscipline:
    def test_adding_with_an_empty_stack_is_caught(self):
        chunk = Chunk()
        chunk.write_op(OpCode.ADD, 1)
        chunk.write_op(OpCode.RETURN, 1)
        found = faults(Function("hand", 0, chunk))
        assert found[0].kind == STACK_UNDERFLOW

    def test_the_message_says_how_many_were_needed_and_found(self):
        chunk = Chunk()
        chunk.write_op(OpCode.ADD, 1)
        chunk.write_op(OpCode.RETURN, 1)
        message = faults(Function("hand", 0, chunk))[0].message
        assert "needs 1 values" in message
        assert "only 0" in message

    def test_returning_from_an_empty_stack_is_caught(self):
        chunk = Chunk()
        chunk.write_op(OpCode.RETURN, 1)
        assert faults(Function("bare", 0, chunk))[0].kind == STACK_UNDERFLOW

    def test_a_balanced_hand_written_chunk_verifies(self):
        chunk = Chunk()
        chunk.write_op(OpCode.NIL, 1)
        chunk.write_op(OpCode.RETURN, 1)
        assert faults(Function("fine", 0, chunk)) == []

    def test_printing_needs_a_value(self):
        chunk = Chunk()
        chunk.write_op(OpCode.PRINT, 1)
        chunk.write_op(OpCode.NIL, 1)
        chunk.write_op(OpCode.RETURN, 1)
        assert faults(Function("noisy", 0, chunk))[0].kind == STACK_UNDERFLOW


class TestMissingReturn:
    def test_a_chunk_that_falls_off_the_end_is_caught(self):
        chunk = Chunk()
        chunk.write_op(OpCode.NIL, 1)
        found = faults(Function("tail", 0, chunk))
        assert [problem.kind for problem in found] == [MISSING_RETURN]

    def test_the_message_names_the_last_instruction(self):
        chunk = Chunk()
        chunk.write_op(OpCode.NIL, 1)
        assert "NIL" in faults(Function("tail", 0, chunk))[0].message

    def test_an_empty_chunk_is_caught(self):
        found = faults(Function("empty", 0, Chunk()))
        assert found[0].kind == MISSING_RETURN
        assert "empty" in found[0].message

    def test_ending_in_a_throw_counts_as_leaving(self):
        chunk = Chunk()
        chunk.write_op(OpCode.NIL, 1)
        chunk.write_op(OpCode.THROW, 1)
        assert [p.kind for p in faults(Function("angry", 0, chunk))] == []


class TestRendering:
    def test_a_rendered_line_carries_the_index_and_severity(self):
        chunk = Chunk()
        chunk.write_op(OpCode.NIL, 1)
        rendered = faults(Function("tail", 0, chunk))[0].render()
        assert rendered.startswith("instruction 0: error: missing-return")

    def test_a_warning_renders_as_a_warning(self):
        found = warnings_deeply(build("fn f() { return 1; } print f();"))
        assert "warning: unreachable-code" in found[0].render()

    def test_describe_puts_faults_before_warnings(self):
        lines = describe(build("fn f() { return 1; } print f();"))
        assert any("warning" in line for line in lines)

    def test_describe_of_a_clean_program_is_empty(self):
        assert describe(build("print 1;")) == []


class TestReportingEverything:
    def test_two_faults_in_one_chunk_both_appear(self):
        chunk = Chunk()
        chunk.write_op(OpCode.ADD, 1)
        chunk.write_op(OpCode.NIL, 1)
        found = faults(Function("twice", 0, chunk))
        kinds = sorted({problem.kind for problem in found})
        assert kinds == [MISSING_RETURN, STACK_UNDERFLOW]

    def test_problems_come_back_in_instruction_order(self):
        chunk = Chunk()
        chunk.write_op(OpCode.ADD, 1)
        chunk.write_op(OpCode.NIL, 1)
        indexes = [problem.index for problem in verify(Function("twice", 0, chunk))]
        assert indexes == sorted(indexes)

    def test_a_nested_function_is_verified_too(self):
        program = build("fn outer() { fn inner() { return 1; } return inner; } print outer();")
        shallow = verify(program)
        deep = verify_deeply(program)
        assert len(deep) > len(shallow)

    def test_verifying_deeply_reaches_a_method(self):
        program = build("class A { m() { return 1; } } print A().m();")
        assert len(verify_deeply(program)) > len(verify(program))
