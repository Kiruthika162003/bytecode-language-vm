from __future__ import annotations

import pytest

from ember.errors import StackFault, Syntax, Thrown
from ember.interpreter import run, run_output, run_treewalk_output

SHARED = [
    'try { throw "bad"; } catch (e) { print e; }',
    'try { print "ok"; } catch (e) { print "never"; } print "after";',
    'try { print 1 / 0; } catch (e) { print "caught"; }',
    'try { print missing; } catch (e) { print "caught"; }',
    'fn f() { throw "deep"; } try { f(); } catch (e) { print e; }',
    'fn g() { try { throw "inner"; } catch (e) { return "handled " + e; } } print g();',
    'try { try { throw "a"; } catch (e) { throw "b"; } } catch (e2) { print e2; }',
    "try { throw 42; } catch (e) { print e + 1; }",
    "try { throw [1, 2]; } catch (e) { print len(e); }",
    (
        "let n = 0; for (i in [1, 2, 3])"
        ' { try { if (i == 2) throw "skip"; n = n + i; } catch (e) { } } print n;'
    ),
    "for (i in [1, 2, 3]) { try { if (i == 2) break; print i; } catch (e) { } }",
    'class C { m() { throw "from method"; } } try { C().m(); } catch (e) { print e; }',
    'try { let a = [1]; print a[9]; } catch (e) { print "range caught"; }',
    'try { let x = 1; throw "x"; } catch (e) { print e; }',
]


class TestThrowAndCatch:
    def test_a_thrown_value_reaches_the_catch(self):
        assert run_output('try { throw "bad"; } catch (e) { print e; }') == ["bad"]

    def test_a_body_that_does_not_throw_skips_the_catch(self):
        source = 'try { print "ok"; } catch (e) { print "never"; } print "after";'
        assert run_output(source) == ["ok", "after"]

    def test_any_value_can_be_thrown(self):
        assert run_output("try { throw 42; } catch (e) { print e + 1; }") == ["43"]
        assert run_output("try { throw [1, 2]; } catch (e) { print len(e); }") == ["2"]

    def test_a_throw_crosses_a_call_boundary(self):
        source = 'fn f() { throw "deep"; } try { f(); } catch (e) { print e; }'
        assert run_output(source) == ["deep"]

    def test_a_throw_crosses_several_frames(self):
        source = (
            'fn deep() { throw "far"; } fn middle() { deep(); } fn outer() { middle(); }'
            " try { outer(); } catch (e) { print e; }"
        )
        assert run_output(source) == ["far"]

    def test_a_method_can_throw(self):
        source = (
            'class C { m() { throw "from method"; } }'
            " try { C().m(); } catch (e) { print e; }"
        )
        assert run_output(source) == ["from method"]


class TestRuntimeFaultsAreCatchable:
    def test_division_by_zero_can_be_caught(self):
        source = 'try { print 1 / 0; } catch (e) { print "caught: " + e; }'
        assert run_output(source) == ["caught: division by zero has no defined result"]

    def test_an_undefined_name_can_be_caught(self):
        assert run_output('try { print missing; } catch (e) { print "caught"; }') == ["caught"]

    def test_an_index_fault_can_be_caught(self):
        source = 'try { let a = [1]; print a[9]; } catch (e) { print "range"; }'
        assert run_output(source) == ["range"]

    def test_a_type_fault_can_be_caught(self):
        source = 'try { print 1 + "a"; } catch (e) { print "type"; }'
        assert run_output(source) == ["type"]

    def test_a_wrong_arity_call_can_be_caught(self):
        source = 'fn f(x) { return x; } try { f(); } catch (e) { print "arity"; }'
        assert run_output(source) == ["arity"]

    def test_an_internal_fault_is_not_catchable(self):
        # runaway recursion is a fault of the machine's limits, not the program's
        # logic, so a catch does not swallow it
        with pytest.raises(StackFault):
            run('fn f() { return f(); } try { f(); } catch (e) { print "no"; }')


class TestNesting:
    def test_an_inner_catch_can_rethrow_to_an_outer_one(self):
        source = 'try { try { throw "a"; } catch (e) { throw "b"; } } catch (e2) { print e2; }'
        assert run_output(source) == ["b"]

    def test_an_inner_try_handles_its_own(self):
        source = (
            'try { try { throw "inner"; } catch (e) { print "inner caught"; } }'
            ' catch (e2) { print "outer"; }'
        )
        assert run_output(source) == ["inner caught"]

    def test_a_catch_can_return_from_its_function(self):
        source = 'fn g() { try { throw "x"; } catch (e) { return "handled"; } } print g();'
        assert run_output(source) == ["handled"]


class TestLoopInteraction:
    def test_a_throw_inside_a_loop_is_caught_each_iteration(self):
        source = (
            "let n = 0; for (i in [1, 2, 3])"
            ' { try { if (i == 2) throw "skip"; n = n + i; } catch (e) { } } print n;'
        )
        assert run_output(source) == ["4"]

    def test_break_out_of_a_try_leaves_no_handler_behind(self):
        # if the handler survived the break, the later throw would be caught here
        source = (
            "for (i in [1, 2]) { try { if (i == 2) break; print i; } catch (e) { } }"
            ' try { throw "after"; } catch (e) { print e; }'
        )
        assert run_output(source) == ["1", "after"]

    def test_continue_out_of_a_try_leaves_no_handler_behind(self):
        source = (
            "for (i in [1, 2]) { try { if (i == 1) continue; print i; } catch (e) { } }"
            ' try { throw "after"; } catch (e) { print e; }'
        )
        assert run_output(source) == ["2", "after"]

    def test_a_return_out_of_a_try_leaves_no_handler_behind(self):
        source = (
            'fn f() { try { return "returned"; } catch (e) { return "no"; } }'
            ' print f(); try { throw "after"; } catch (e) { print e; }'
        )
        assert run_output(source) == ["returned", "after"]


class TestUncaught:
    def test_an_uncaught_throw_carries_its_value(self):
        with pytest.raises(Thrown) as caught:
            run('throw "nobody catches";')
        assert caught.value.value == "nobody catches"

    def test_an_uncaught_throw_renders_the_value_in_its_message(self):
        with pytest.raises(Thrown) as caught:
            run("throw 42;")
        assert "42" in str(caught.value)

    def test_a_throw_from_a_function_with_no_handler_escapes(self):
        with pytest.raises(Thrown):
            run('fn f() { throw "x"; } f();')


class TestSyntaxRules:
    def test_a_try_without_a_catch_is_refused(self):
        with pytest.raises(Syntax):
            run('try { throw "x"; }')

    def test_a_catch_without_a_name_is_refused(self):
        with pytest.raises(Syntax):
            run('try { throw "x"; } catch { print 1; }')

    def test_a_throw_needs_a_value(self):
        with pytest.raises(Syntax):
            run("throw;")

    def test_a_throw_needs_a_semicolon(self):
        with pytest.raises(Syntax):
            run('try { throw "x" } catch (e) { }')


class TestBothBackendsAgree:
    @pytest.mark.parametrize("source", SHARED)
    def test_agreement(self, source: str):
        assert run_output(source) == run_treewalk_output(source)

    @pytest.mark.parametrize("source", SHARED)
    def test_agreement_when_fully_optimized(self, source: str):
        assert run_output(source, optimize=True, peephole=True) == run_treewalk_output(
            source, optimize=True
        )
