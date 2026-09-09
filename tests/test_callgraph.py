from __future__ import annotations

from ember.callgraph import (
    build_graph,
    deepest_chain,
    defined_functions,
    directly_recursive,
    has_cycle,
    never_called,
    reachable,
    recursive_functions,
    report,
)

CHAIN = "fn a() { return b(); } fn b() { return c(); } fn c() { return 1; } print a();"
UNUSED = "fn used() { return 1; } fn unused() { return 2; } print used();"
SELF = "fn fib(n) { if (n<2) return n; return fib(n-1)+fib(n-2); } print fib(5);"
MUTUAL = (
    "fn even(n) { if (n==0) return true; return odd(n-1); }"
    " fn odd(n) { if (n==0) return false; return even(n-1); } print even(4);"
)
INDIRECT = "fn make() { fn inner() { return 1; } return inner; } print make()();"


class TestBuildingTheGraph:
    def test_a_function_is_recorded(self):
        assert "a" in build_graph(CHAIN).names

    def test_the_script_is_a_caller_too(self):
        assert "<script>" in build_graph(CHAIN).names

    def test_a_call_becomes_an_edge(self):
        assert build_graph(CHAIN).called_by("a") == ["b"]

    def test_the_script_calls_what_it_names(self):
        assert "a" in build_graph(CHAIN).called_by("<script>")

    def test_a_function_calling_nothing_has_no_edges(self):
        assert build_graph(CHAIN).called_by("c") == []

    def test_callers_can_be_asked_for(self):
        assert build_graph(CHAIN).callers_of("b") == ["a"]

    def test_the_defined_functions_exclude_the_script(self):
        assert defined_functions(build_graph(CHAIN)) == ["a", "b", "c"]

    def test_a_program_with_no_functions_defines_none(self):
        assert defined_functions(build_graph("print 1;")) == []

    def test_the_graph_describes_itself(self):
        lines = build_graph(CHAIN).describe()
        assert any("a calls b" in line for line in lines)

    def test_a_function_calling_nothing_says_so(self):
        assert any("calls nothing" in line for line in build_graph(CHAIN).describe())


class TestWhereCallsAppear:
    def test_a_call_in_a_condition_is_found(self):
        graph = build_graph("fn p() { return true; } fn f() { if (p()) return 1; return 0; }")
        assert "p" in graph.called_by("f")

    def test_a_call_in_a_loop_is_found(self):
        source = "fn p() { return 1; } fn f() { while (false) { p(); } }"
        assert "p" in build_graph(source).called_by("f")

    def test_a_call_in_a_print_is_found(self):
        assert "p" in build_graph("fn p() { return 1; } print p();").called_by("<script>")

    def test_a_call_in_a_let_is_found(self):
        source = "fn p() { return 1; } let x = p();"
        assert "p" in build_graph(source).called_by("<script>")

    def test_a_call_in_an_argument_is_found(self):
        source = "fn p() { return 1; } fn q(x) { return x; } print q(p());"
        assert sorted(build_graph(source).called_by("<script>")) == ["p", "q"]

    def test_a_call_inside_a_try_is_found(self):
        source = "fn p() { return 1; } fn f() { try { p(); } catch (e) { } }"
        assert "p" in build_graph(source).called_by("f")

    def test_a_call_inside_a_catch_is_found(self):
        source = "fn p() { return 1; } fn f() { try { } catch (e) { p(); } }"
        assert "p" in build_graph(source).called_by("f")

    def test_a_call_inside_a_match_arm_is_found(self):
        source = "fn p() { return 1; } fn f(a) { match (a) { case 1: p(); default: } }"
        assert "p" in build_graph(source).called_by("f")

    def test_a_call_in_a_throw_is_found(self):
        source = "fn p() { return 1; } fn f() { throw p(); }"
        assert "p" in build_graph(source).called_by("f")

    def test_a_call_in_a_list_literal_is_found(self):
        source = "fn p() { return 1; } fn f() { return [p()]; }"
        assert "p" in build_graph(source).called_by("f")

    def test_a_call_in_a_map_value_is_found(self):
        source = 'fn p() { return 1; } fn f() { return {"k": p()}; }'
        assert "p" in build_graph(source).called_by("f")

    def test_a_call_in_a_conditional_arm_is_found(self):
        source = "fn p() { return 1; } fn f(c) { return c ? p() : 0; }"
        assert "p" in build_graph(source).called_by("f")

    def test_a_method_is_named_for_its_class(self):
        source = "class A { m() { return 1; } } print A().m();"
        assert "A.m" in build_graph(source).names

    def test_two_classes_may_share_a_method_name(self):
        source = "class A { m() { return 1; } } class B { m() { return 2; } }"
        names = build_graph(source).names
        assert "A.m" in names
        assert "B.m" in names


class TestUnreached:
    def test_a_function_nobody_names_is_reported(self):
        assert never_called(build_graph(UNUSED)) == ["unused"]

    def test_a_function_the_script_calls_is_not_reported(self):
        assert "used" not in never_called(build_graph(UNUSED))

    def test_a_function_reached_only_through_a_chain_is_not_reported(self):
        assert never_called(build_graph(CHAIN)) == []

    def test_everything_reachable_is_listed(self):
        assert reachable(build_graph(CHAIN)) == {"<script>", "a", "b", "c"}

    def test_a_closure_called_through_a_value_looks_unreached(self):
        # the honest limitation of building the graph from names
        assert never_called(build_graph(INDIRECT)) == ["inner"]

    def test_the_indirect_calls_are_counted_so_the_list_can_be_judged(self):
        assert build_graph(INDIRECT).indirect_total == 1

    def test_a_program_with_only_named_calls_counts_no_indirect_ones(self):
        assert build_graph(CHAIN).indirect_total == 0


class TestRecursion:
    def test_a_function_calling_itself_is_found(self):
        assert recursive_functions(build_graph(SELF)) == ["fib"]

    def test_direct_recursion_is_reported_separately(self):
        assert directly_recursive(build_graph(SELF)) == ["fib"]

    def test_mutual_recursion_is_found(self):
        assert recursive_functions(build_graph(MUTUAL)) == ["even", "odd"]

    def test_mutual_recursion_is_not_direct(self):
        assert directly_recursive(build_graph(MUTUAL)) == []

    def test_a_program_without_recursion_finds_none(self):
        assert recursive_functions(build_graph(CHAIN)) == []

    def test_a_cycle_is_reported_as_one(self):
        assert has_cycle(build_graph(SELF))

    def test_no_cycle_is_reported_when_there_is_none(self):
        assert not has_cycle(build_graph(CHAIN))


class TestChainDepth:
    def test_a_chain_of_three_measures_four_with_the_script(self):
        assert deepest_chain(build_graph(CHAIN)) == 4

    def test_a_program_with_one_call_measures_two(self):
        assert deepest_chain(build_graph("fn a() { return 1; } print a();")) == 2

    def test_a_program_with_no_calls_measures_one(self):
        assert deepest_chain(build_graph("print 1;")) == 1

    def test_recursion_makes_the_depth_unbounded(self):
        # a cycle makes the longest chain unbounded, so there is no number to give
        assert deepest_chain(build_graph(SELF)) == -1

    def test_mutual_recursion_is_unbounded_too(self):
        assert deepest_chain(build_graph(MUTUAL)) == -1


class TestReport:
    def test_the_report_counts_the_functions(self):
        assert any("3 functions defined" in line for line in report(CHAIN))

    def test_one_function_is_named_in_the_singular(self):
        assert any("1 function defined" in line for line in report(SELF))

    def test_the_report_names_unreached_functions(self):
        assert any("unused" in line for line in report(UNUSED))

    def test_the_report_names_recursive_functions(self):
        assert any("can reach themselves: fib" in line for line in report(SELF))

    def test_the_report_gives_the_chain_depth(self):
        assert any("4 deep" in line for line in report(CHAIN))

    def test_the_report_says_when_the_depth_is_unbounded(self):
        assert any("unbounded" in line for line in report(SELF))

    def test_the_report_warns_about_indirect_calls(self):
        assert any("through a value" in line for line in report(INDIRECT))

    def test_one_indirect_call_reads_in_the_singular(self):
        assert any("1 call goes through a value" in line for line in report(INDIRECT))

    def test_a_clean_report_does_not_warn(self):
        assert not any("through a value" in line for line in report(CHAIN))
