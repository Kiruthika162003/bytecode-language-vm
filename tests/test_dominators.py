from __future__ import annotations

from ember.cfg import build_graph, graph_of
from ember.dominators import (
    Loop,
    back_edges,
    deepest_nesting,
    dominates,
    dominator_tree,
    dominators,
    immediate_dominator,
    loop_depth,
    loops,
)
from ember.function import Function
from ember.instructions import Program
from ember.interpreter import build

WHILE = "let n = 0; while (n < 3) { n = n + 1; } print n;"
COUNTED = "let s = 0; for (let i = 0; i < 5; i = i + 1) s = s + i; print s;"
NESTED = "for (let i=0;i<3;i=i+1) { for (let j=0;j<3;j=j+1) { print i+j; } }"
BRANCH = 'if (c) print "a"; else print "b"; print "after";'


def graph_for(source: str, **options):
    return graph_of(build(source, **options))


class TestBasicDominance:
    def test_the_entry_dominates_itself_and_nothing_else_dominates_it(self):
        graph = graph_for(BRANCH)
        assert dominators(graph)[0] == {0}

    def test_the_entry_dominates_every_reachable_block(self):
        graph = graph_for(BRANCH)
        found = dominators(graph)
        assert all(0 in found[block] for block in found)

    def test_a_block_dominates_itself(self):
        graph = graph_for(BRANCH)
        found = dominators(graph)
        assert all(block in found[block] for block in found)

    def test_a_straight_line_program_dominates_in_order(self):
        graph = graph_for("print 1; print 2;")
        assert dominators(graph) == {0: {0}}

    def test_an_empty_graph_has_no_dominators(self):
        assert dominators(build_graph(Program())) == {}


class TestBranchDominance:
    def test_the_test_block_dominates_both_arms(self):
        graph = graph_for(BRANCH)
        found = dominators(graph)
        forking = next(b for b in graph.blocks if len(b.successors) == 2)
        arms = [b.index for b in graph.blocks if forking.index in b.predecessors]
        assert all(forking.index in found[arm] for arm in arms)

    def test_neither_arm_dominates_the_join(self):
        graph = graph_for(BRANCH)
        found = dominators(graph)
        joining = next(b for b in graph.blocks if len(b.predecessors) == 2)
        for arm in joining.predecessors:
            assert arm not in found[joining.index]

    def test_dominates_answers_the_question_directly(self):
        graph = graph_for(BRANCH)
        assert dominates(graph, 0, graph.count - 1)

    def test_a_later_block_does_not_dominate_an_earlier_one(self):
        graph = graph_for(BRANCH)
        assert not dominates(graph, graph.count - 1, 0)


class TestImmediateDominator:
    def test_the_entry_has_none(self):
        assert immediate_dominator(graph_for(BRANCH), 0) is None

    def test_every_other_block_has_one(self):
        graph = graph_for(BRANCH)
        for block in graph.blocks:
            if block.index == 0:
                continue
            assert immediate_dominator(graph, block.index) is not None

    def test_the_immediate_dominator_dominates_the_block(self):
        graph = graph_for(COUNTED)
        for block in graph.blocks:
            parent = immediate_dominator(graph, block.index)
            if parent is not None:
                assert dominates(graph, parent, block.index)

    def test_the_tree_has_a_parent_for_all_but_the_entry(self):
        graph = graph_for(BRANCH)
        tree = dominator_tree(graph)
        children = {child for listed in tree.values() for child in listed}
        assert 0 not in children
        assert len(children) == graph.count - 1

    def test_the_tree_covers_every_block(self):
        graph = graph_for(COUNTED)
        assert set(dominator_tree(graph)) == {block.index for block in graph.blocks}


class TestBackEdges:
    def test_a_while_loop_has_one(self):
        assert len(back_edges(graph_for(WHILE))) == 1

    def test_a_straight_program_has_none(self):
        assert back_edges(graph_for("print 1;")) == []

    def test_a_branch_alone_has_none(self):
        assert back_edges(graph_for(BRANCH)) == []

    def test_a_nested_loop_has_two(self):
        assert len(back_edges(graph_for(NESTED))) == 2

    def test_the_destination_dominates_the_source(self):
        graph = graph_for(WHILE)
        for latch, header in back_edges(graph):
            assert dominates(graph, header, latch)


class TestLoopRecords:
    def test_a_loop_body_holds_its_header_and_latch(self):
        graph = graph_for(WHILE)
        found = loops(graph)[0]
        assert found.header in found.body
        assert found.latch in found.body

    def test_a_loop_describes_itself(self):
        rendered = loops(graph_for(WHILE))[0].describe()
        assert "loop headed at block" in rendered

    def test_containment_recovers_nesting(self):
        outer = Loop(header=1, latch=5, body={1, 2, 3, 4, 5})
        inner = Loop(header=2, latch=3, body={2, 3})
        assert outer.contains(inner)
        assert not inner.contains(outer)

    def test_a_loop_does_not_contain_itself(self):
        same = Loop(header=1, latch=2, body={1, 2})
        assert not same.contains(same)

    def test_size_is_the_body_count(self):
        assert Loop(header=0, latch=1, body={0, 1, 2}).size == 3


class TestFindingLoops:
    def test_a_while_loop_is_found(self):
        assert len(loops(graph_for(WHILE))) == 1

    def test_a_counted_loop_is_found(self):
        assert len(loops(graph_for(COUNTED))) == 1

    def test_a_foreach_loop_is_found(self):
        assert len(loops(graph_for("for (x in [1,2,3]) print x;"))) == 1

    def test_a_nested_pair_is_found_outer_first(self):
        found = loops(graph_for(NESTED))
        assert len(found) == 2
        assert found[0].size >= found[1].size

    def test_the_outer_loop_contains_the_inner_one(self):
        outer, inner = loops(graph_for(NESTED))
        assert outer.contains(inner)

    def test_a_program_with_no_loop_finds_none(self):
        assert loops(graph_for(BRANCH)) == []


class TestNestingDepth:
    def test_a_straight_program_has_depth_zero(self):
        assert deepest_nesting(graph_for("print 1;")) == 0

    def test_one_loop_has_depth_one(self):
        assert deepest_nesting(graph_for(WHILE)) == 1

    def test_two_nested_loops_have_depth_two(self):
        assert deepest_nesting(graph_for(NESTED)) == 2

    def test_three_nested_loops_have_depth_three(self):
        source = (
            "for (let i=0;i<2;i=i+1) { for (let j=0;j<2;j=j+1) { "
            "for (let k=0;k<2;k=k+1) { print i+j+k; } } }"
        )
        assert deepest_nesting(graph_for(source)) == 3

    def test_two_loops_side_by_side_stay_at_depth_one(self):
        source = "for (let i=0;i<2;i=i+1) print i; for (let j=0;j<2;j=j+1) print j;"
        assert deepest_nesting(graph_for(source)) == 1

    def test_a_block_outside_a_loop_has_depth_zero(self):
        graph = graph_for(WHILE)
        depth = loop_depth(graph)
        assert depth[0] == 0

    def test_the_loop_body_has_depth_one(self):
        graph = graph_for(WHILE)
        depth = loop_depth(graph)
        body = loops(graph)[0].body
        assert all(depth[block] == 1 for block in body)

    def test_an_empty_graph_has_depth_zero(self):
        assert deepest_nesting(build_graph(Program())) == 0


class TestInsideFunctions:
    def test_a_recursive_function_body_has_no_loop(self):
        # recursion is a call, not a branch, so the graph of one body has no cycle
        source = "fn fib(n) { if (n<2) return n; return fib(n-1)+fib(n-2); } print fib(5);"
        program = build(source)
        inner = next(c for c in program.chunk.constants if isinstance(c, Function))
        assert loops(graph_of(inner)) == []

    def test_a_loop_inside_a_function_is_found(self):
        source = "fn total(n) { let s = 0; while (n > 0) { s = s + n; n = n - 1; } return s; }"
        program = build(source)
        inner = next(c for c in program.chunk.constants if isinstance(c, Function))
        assert len(loops(graph_of(inner))) == 1

    def test_a_method_body_gets_a_graph(self):
        source = "class A { m(n) { if (n > 0) return 1; return 0; } } print A().m(1);"
        program = build(source)
        cls = next(c for c in program.chunk.constants if isinstance(c, Function))
        assert graph_of(cls).count >= 1
