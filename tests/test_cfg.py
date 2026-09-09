from __future__ import annotations

from ember.cfg import Block, build_graph, graph_of
from ember.chunk import Chunk
from ember.function import Function
from ember.instructions import Program, decode
from ember.interpreter import build
from ember.opcode import OpCode


def graph_for(source: str, **options):
    return graph_of(build(source, **options))


class TestBlockRecords:
    def test_a_block_knows_the_span_it_covers(self):
        block = Block(index=0, start=3, end=7)
        assert block.length == 4
        assert block.covers(3)
        assert block.covers(6)

    def test_a_block_does_not_cover_the_instruction_after_it(self):
        block = Block(index=0, start=3, end=7)
        assert not block.covers(7)
        assert not block.covers(2)

    def test_a_block_describes_where_it_goes(self):
        block = Block(index=1, start=2, end=4, successors=[2, 3])
        rendered = block.describe()
        assert "block 1" in rendered
        assert "2..3" in rendered
        assert "goes to 2, 3" in rendered

    def test_a_block_with_no_successor_says_nothing_follows(self):
        assert "goes to nothing" in Block(index=0, start=0, end=1).describe()


class TestStraightLine:
    def test_a_program_with_no_jumps_is_one_block(self):
        assert graph_for("print 1 + 2;").count == 1

    def test_that_block_covers_every_instruction(self):
        graph = graph_for("print 1 + 2; print 3;")
        program = decode(build("print 1 + 2; print 3;").chunk)
        assert graph.blocks[0].end == len(program.instructions)

    def test_the_entry_is_the_first_block(self):
        graph = graph_for("print 1;")
        assert graph.entry() is graph.blocks[0]

    def test_a_straight_program_has_one_exit(self):
        assert len(graph_for("print 1;").exits()) == 1

    def test_an_empty_program_has_no_blocks(self):
        graph = build_graph(Program())
        assert graph.count == 0
        assert graph.entry() is None
        assert graph.reachable() == set()


class TestBranching:
    def test_an_if_else_splits_into_four_blocks(self):
        # the test, the then arm, the else arm, and where they rejoin
        assert graph_for('if (1 < 2) print "a"; else print "b";').count == 4

    def test_the_test_block_has_two_successors(self):
        graph = graph_for('if (c) print "a"; else print "b";')
        forking = [block for block in graph.blocks if len(block.successors) == 2]
        assert len(forking) == 1

    def test_the_arms_rejoin_at_one_block(self):
        graph = graph_for('if (c) print "a"; else print "b";')
        joining = [block for block in graph.blocks if len(block.predecessors) == 2]
        assert len(joining) == 1

    def test_every_block_of_a_branch_is_reachable(self):
        assert graph_for('if (c) print "a"; else print "b";').unreachable() == []

    def test_a_conditional_expression_also_branches(self):
        assert graph_for('print c ? "y" : "n";').count > 1


class TestLoops:
    def test_a_while_loop_has_a_backward_edge(self):
        graph = graph_for("let n = 0; while (n < 3) { n = n + 1; } print n;")
        backward = [
            (block.index, successor)
            for block in graph.blocks
            for successor in block.successors
            if successor <= block.index
        ]
        assert backward

    def test_a_while_loop_is_fully_reachable(self):
        graph = graph_for("let n = 0; while (n < 3) { n = n + 1; } print n;")
        assert graph.unreachable() == []

    def test_a_counted_for_loop_is_fully_reachable(self):
        graph = graph_for("let s = 0; for (let i = 0; i < 5; i = i + 1) s = s + i; print s;")
        assert graph.unreachable() == []

    def test_a_foreach_loop_is_fully_reachable(self):
        assert graph_for("for (x in [1, 2, 3]) print x;").unreachable() == []

    def test_a_nested_loop_makes_more_blocks_than_one_loop(self):
        single = graph_for("for (let i=0;i<3;i=i+1) { print i; }").count
        nested = graph_for(
            "for (let i=0;i<3;i=i+1) { for (let j=0;j<3;j=j+1) { print i+j; } }"
        ).count
        assert nested > single


class TestHandlerEdges:
    def test_pushing_a_handler_forks_the_graph(self):
        # the fix that mattered: a handler push in the middle of a block left the
        # whole try region without edges, so it all looked unreachable
        graph = graph_for('try { print 1 / 0; } catch (e) { print "c"; } print "after";')
        assert graph.unreachable() == []

    def test_the_handler_block_has_a_predecessor(self):
        graph = graph_for('try { print 1 / 0; } catch (e) { print "c"; }')
        assert all(block.predecessors or block.index == 0 for block in graph.blocks)

    def test_a_try_whose_body_always_throws_leaves_its_pop_handler_dead(self):
        # the throw ends the path, so the instruction that would retire the handler
        # can never run, which the verifier reports the same way
        graph = graph_for('try { throw "x"; } catch (e) { print e; }')
        assert len(graph.unreachable()) == 1

    def test_a_loop_with_a_try_inside_it_is_reachable_apart_from_dead_jumps(self):
        graph = graph_for('for (i in [1, 2]) { try { print i; } catch (e) { } }')
        assert graph.unreachable() == []


class TestDeadJumps:
    def test_a_then_arm_ending_in_break_leaves_the_over_jump_dead(self):
        # an if without an else still emits a jump past the missing else, and a then
        # arm that already jumped away can never reach it
        graph = graph_for("let n=0; while (n<9) { n=n+1; if (n==2) break; } print n;")
        assert len(graph.unreachable()) == 1

    def test_the_peephole_pass_removes_it(self):
        source = "let n=0; while (n<9) { n=n+1; if (n==2) break; } print n;"
        assert graph_for(source, peephole=True).unreachable() == []

    def test_a_continue_leaves_the_same_shape(self):
        graph = graph_for("for (x in [1,2,3]) { if (x==2) continue; print x; }")
        assert len(graph.unreachable()) == 1


class TestLookup:
    def test_a_block_can_be_found_by_instruction(self):
        graph = graph_for("let n = 0; while (n < 3) { n = n + 1; } print n;")
        found = graph.block_at(0)
        assert found is not None
        assert found.index == 0

    def test_an_index_past_the_end_finds_nothing(self):
        assert graph_for("print 1;").block_at(9999) is None

    def test_every_instruction_belongs_to_exactly_one_block(self):
        source = "for (let i=0;i<3;i=i+1) { if (i==1) continue; print i; }"
        program = decode(build(source).chunk)
        graph = graph_for(source)
        for index in range(len(program.instructions)):
            owners = [block for block in graph.blocks if block.covers(index)]
            assert len(owners) == 1

    def test_the_blocks_are_in_instruction_order(self):
        graph = graph_for("let s = 0; for (let i = 0; i < 5; i = i + 1) s = s + i;")
        starts = [block.start for block in graph.blocks]
        assert starts == sorted(starts)


class TestReachability:
    def test_a_block_after_a_return_is_unreachable(self):
        chunk = Chunk()
        chunk.write_op(OpCode.NIL, 1)
        chunk.write_op(OpCode.RETURN, 1)
        chunk.write_op(OpCode.NIL, 1)
        chunk.write_op(OpCode.RETURN, 1)
        graph = graph_of(Function("split", 0, chunk))
        assert graph.unreachable() == [1]

    def test_reachable_always_holds_the_entry(self):
        assert 0 in graph_for("print 1;").reachable()

    def test_describe_lists_one_line_per_block(self):
        graph = graph_for('if (c) print "a"; else print "b";')
        assert len(graph.describe()) == graph.count

    def test_a_function_body_is_its_own_graph(self):
        program = build("fn f(n) { if (n < 1) return 0; return n; } print f(2);")
        inner = next(c for c in program.chunk.constants if isinstance(c, Function))
        assert graph_of(inner).count > 1
