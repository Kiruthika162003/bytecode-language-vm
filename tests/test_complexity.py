from __future__ import annotations

from ember.cfg import build_graph, graph_of
from ember.complexity import (
    Measurement,
    complexity_of,
    edge_count,
    exit_count,
    folding_removed,
    measure_source,
    most_complex,
    node_count,
    report,
    total_paths,
)
from ember.function import Function
from ember.instructions import Program
from ember.interpreter import build

NEWLINE = chr(10)

STRAIGHT = "print 1;"
ONE_IF = "fn f(a) { if (a > 0) return 1; return 0; }" + NEWLINE + "print f(1);"
TWO_IFS = (
    "fn f(a) { if (a > 0) return 1; if (a < 0) return 0 - 1; return 0; }"
    + NEWLINE
    + "print f(1);"
)
IF_ELSE = "fn f(a) { if (a > 0) { return 1; } else { return 0; } }" + NEWLINE + "print f(1);"
LOOP = (
    "fn f(n) { let s = 0; while (n > 0) { s = s + n; n = n - 1; } return s; }"
    + NEWLINE
    + "print f(3);"
)
NESTED = (
    "fn f() { for (let i=0;i<2;i=i+1) { for (let j=0;j<2;j=j+1) { print i; } } }"
    + NEWLINE
    + "f();"
)
MATCH = (
    "fn f(a) { match (a) { case 1: return 1; case 2: return 2; default: return 0; } }"
    + NEWLINE
    + "print f(1);"
)
FOLDED = "fn f() { if (1 < 2) return 1; return 0; }" + NEWLINE + "print f();"


def paths_of(source: str, name: str) -> int:
    return next(one.paths for one in measure_source(source) if one.name == name)


class TestTheFormula:
    def test_a_straight_line_has_one_path(self):
        assert paths_of(STRAIGHT, "<script>") == 1

    def test_one_branch_gives_two_paths(self):
        # the case that exposed the textbook formula: two returns means two exits
        assert paths_of(ONE_IF, "f") == 2

    def test_two_branches_give_three_paths(self):
        assert paths_of(TWO_IFS, "f") == 3

    def test_an_if_else_gives_two_paths(self):
        assert paths_of(IF_ELSE, "f") == 2

    def test_a_loop_gives_two_paths(self):
        assert paths_of(LOOP, "f") == 2

    def test_two_nested_loops_give_three_paths(self):
        assert paths_of(NESTED, "f") == 3

    def test_a_match_with_three_arms_gives_three_paths(self):
        assert paths_of(MATCH, "f") == 3

    def test_no_score_is_ever_below_one(self):
        for source in (STRAIGHT, ONE_IF, TWO_IFS, IF_ELSE, LOOP, NESTED, MATCH, FOLDED):
            for one in measure_source(source):
                assert one.paths >= 1

    def test_an_empty_graph_scores_one(self):
        # nothing to walk is the empty path rather than a negative score
        assert complexity_of(build_graph(Program())) == 1


class TestCountingReachableOnly:
    def test_an_unreachable_epilogue_does_not_count_as_a_node(self):
        # the compiler leaves a dead nil-and-return behind a body that always returns
        graph = _graph_for(ONE_IF, "f")
        assert node_count(graph) < graph.count

    def test_the_peephole_pass_removes_the_difference(self):
        graph = _graph_for(ONE_IF, "f", peephole=True)
        assert node_count(graph) == graph.count

    def test_removing_it_does_not_change_the_score(self):
        plain = paths_of(ONE_IF, "f")
        swept = next(
            one.paths for one in measure_source(ONE_IF, peephole=True) if one.name == "f"
        )
        assert plain == swept

    def test_an_edge_into_an_unreachable_block_is_not_counted(self):
        graph = _graph_for(ONE_IF, "f")
        assert edge_count(graph) <= sum(len(b.successors) for b in graph.blocks)

    def test_a_function_returning_from_two_places_has_two_exits(self):
        assert exit_count(_graph_for(IF_ELSE, "f")) == 2

    def test_a_straight_line_has_one_exit(self):
        assert exit_count(_graph_for(STRAIGHT, "<script>")) == 1


def _graph_for(source: str, name: str, **options):
    program = build(source, **options)
    if name == "<script>":
        return graph_of(program)
    inner = next(
        c
        for c in program.chunk.constants
        if isinstance(c, Function) and c.name == name
    )
    return graph_of(inner)


class TestMeasurements:
    def test_the_script_is_measured(self):
        assert any(one.name == "<script>" for one in measure_source(STRAIGHT))

    def test_a_nested_function_is_measured(self):
        assert any(one.name == "f" for one in measure_source(ONE_IF))

    def test_a_method_is_measured(self):
        source = "class A { m(a) { if (a) return 1; return 0; } }" + NEWLINE + "print A().m(1);"
        assert any(one.name == "m" for one in measure_source(source))

    def test_loops_are_counted(self):
        found = next(one for one in measure_source(LOOP) if one.name == "f")
        assert found.loops == 1

    def test_nesting_is_reported(self):
        found = next(one for one in measure_source(NESTED) if one.name == "f")
        assert found.nesting == 2

    def test_the_tests_needed_is_the_path_count(self):
        found = next(one for one in measure_source(TWO_IFS) if one.name == "f")
        assert found.tests_needed() == found.paths

    def test_the_most_complex_function_can_be_asked_for(self):
        assert most_complex(TWO_IFS).name == "f"

    def test_the_total_adds_up_the_functions(self):
        found = measure_source(TWO_IFS)
        assert total_paths(TWO_IFS) == sum(one.paths for one in found)


class TestFolding:
    def test_folding_removes_a_decision_that_was_never_one(self):
        assert folding_removed(FOLDED) == 1

    def test_folding_removes_nothing_from_a_real_branch(self):
        assert folding_removed(ONE_IF) == 0

    def test_the_report_says_what_folding_removed(self):
        assert any("folding removes 1" in line for line in report(FOLDED))

    def test_the_report_stays_quiet_when_folding_removes_nothing(self):
        assert not any("folding removes" in line for line in report(ONE_IF))


class TestRendering:
    def test_a_measurement_renders_its_numbers(self):
        rendered = Measurement(
            name="f", paths=3, blocks=7, edges=9, loops=1, nesting=1
        ).render()
        assert "f: 3 paths through 7 blocks" in rendered
        assert "1 loop," in rendered

    def test_one_path_reads_in_the_singular(self):
        rendered = Measurement(
            name="f", paths=1, blocks=1, edges=0, loops=0, nesting=0
        ).render()
        assert "1 path through 1 block" in rendered
        assert "0 loops" in rendered

    def test_the_report_has_a_line_per_function_plus_a_total(self):
        assert len(report(STRAIGHT)) == 2

    def test_the_report_totals_the_program(self):
        assert any("in the program altogether" in line for line in report(TWO_IFS))
