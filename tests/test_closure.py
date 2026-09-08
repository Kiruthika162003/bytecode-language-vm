from __future__ import annotations

from ember.chunk import Chunk
from ember.closure import Closure, Upvalue
from ember.function import Function
from ember.interpreter import run, run_output

COUNTER = "fn make() { let c = 0; fn inc() { c = c + 1; return c; } return inc; }"


class TestUpvalueObject:
    def test_an_open_upvalue_reads_through_to_the_stack(self):
        stack = [10, 20, 30]
        upvalue = Upvalue(1)
        assert upvalue.get(stack) == 20

    def test_an_open_upvalue_writes_through_to_the_stack(self):
        stack = [10, 20, 30]
        upvalue = Upvalue(1)
        upvalue.set(stack, 99)
        assert stack[1] == 99

    def test_closing_copies_the_value_out_of_the_stack(self):
        stack = [10, 20, 30]
        upvalue = Upvalue(1)
        upvalue.close(stack)
        assert upvalue.is_closed
        stack[1] = 0  # the stack slot is gone as far as the upvalue cares
        assert upvalue.get(stack) == 20

    def test_a_closed_upvalue_writes_to_itself(self):
        stack = [10, 20]
        upvalue = Upvalue(1)
        upvalue.close(stack)
        upvalue.set(stack, 7)
        assert upvalue.get(stack) == 7
        assert stack[1] == 20

    def test_closing_twice_keeps_the_first_value(self):
        stack = [5]
        upvalue = Upvalue(0)
        upvalue.close(stack)
        stack[0] = 9
        upvalue.close(stack)
        assert upvalue.get(stack) == 5


class TestClosureObject:
    def test_it_forwards_name_and_arity(self):
        function = Function("add", 2, Chunk())
        closure = Closure(function)
        assert closure.name == "add"
        assert closure.arity == 2

    def test_it_starts_with_no_upvalues(self):
        assert Closure(Function("f", 0, Chunk())).upvalues == []

    def test_the_repr_names_the_function(self):
        assert "add" in repr(Closure(Function("add", 2, Chunk())))


class TestCapturingBehavior:
    def test_a_counter_keeps_state_across_calls(self):
        assert run_output(COUNTER + " let f = make(); print f(); print f(); print f();") == [
            "1",
            "2",
            "3",
        ]

    def test_two_closures_have_independent_state(self):
        source = COUNTER + " let a = make(); let b = make(); print a(); print a(); print b();"
        assert run_output(source) == ["1", "2", "1"]

    def test_a_parameter_can_be_captured(self):
        source = (
            "fn adder(n) { fn add(x) { return x + n; } return add; }"
            " let add5 = adder(5); print add5(3); print add5(10);"
        )
        assert run_output(source) == ["8", "15"]

    def test_capture_reaches_through_two_levels(self):
        source = (
            "fn outer() { let x = 7;"
            " fn mid() { fn inner() { return x; } return inner(); } return mid(); }"
            " print outer();"
        )
        assert run_output(source) == ["7"]

    def test_two_closures_share_one_captured_variable(self):
        source = (
            "fn pair() { let n = 0;"
            " fn up() { n = n + 1; return n; } fn get() { return n; }"
            " up(); up(); return get(); }"
            " print pair();"
        )
        assert run_output(source) == ["2"]

    def test_a_closure_outlives_the_frame_it_captured(self):
        # make() has already returned when inc() runs, so the captured variable
        # cannot still be living in make's stack window
        machine = run(COUNTER + " let f = make(); print f(); print f();")
        assert machine.output == ["1", "2"]
        closure = machine.globals["f"]
        assert closure.upvalues[0].is_closed


class TestUpvalueBookkeeping:
    def test_open_upvalues_are_closed_by_the_time_the_script_ends(self):
        machine = run(COUNTER + " let f = make(); f();")
        assert not [u for u in machine.open_upvalues if not u.is_closed]
