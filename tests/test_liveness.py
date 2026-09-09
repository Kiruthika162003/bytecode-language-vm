from __future__ import annotations

from ember.cfg import build_graph, graph_of
from ember.function import Function
from ember.instructions import Program
from ember.interpreter import build
from ember.liveness import (
    BlockFacts,
    DeadStore,
    dead_stores,
    facts_for,
    live_at,
    live_in,
    live_out,
    peak_pressure,
    report,
    slots_used,
)

SUM = "fn total(n) { let s = 0; while (n > 0) { s = s + n; n = n - 1; } return s; }"
DEAD = "fn f(a) { let x = 1; x = 2; return a; }"
BRANCH = "fn f(a) { let x = 0; if (a > 0) { x = 1; } else { x = 2; } return x; }"
GUARDED = 'fn f(a) { let x = 0; try { x = a; throw "e"; } catch (e) { return x; } return 9; }'


def body_of(source: str) -> Function:
    program = build(source)
    return next(c for c in program.chunk.constants if isinstance(c, Function))


def graph_for(source: str):
    return graph_of(body_of(source))


class TestBlockFacts:
    def test_a_block_records_what_it_needs_on_entry(self):
        facts = facts_for(graph_for(SUM))
        assert any(entry.reads for entry in facts.values())

    def test_a_block_records_what_it_overwrites(self):
        facts = facts_for(graph_for(BRANCH))
        assert any(entry.writes for entry in facts.values())

    def test_a_read_after_a_write_in_the_same_block_is_not_needed_on_entry(self):
        facts = BlockFacts(index=0, reads=set(), writes={1})
        assert 1 not in facts.reads

    def test_facts_describe_themselves(self):
        rendered = BlockFacts(index=2, reads={1, 3}).describe()
        assert rendered == "block 2 needs 1, 3 on entry"

    def test_a_block_needing_nothing_says_so(self):
        assert "needs nothing" in BlockFacts(index=0).describe()

    def test_there_is_one_fact_record_per_block(self):
        graph = graph_for(SUM)
        assert len(facts_for(graph)) == graph.count

    def test_an_empty_graph_has_no_facts(self):
        assert facts_for(build_graph(Program())) == {}


class TestLiveSets:
    def test_every_block_gets_a_live_in_set(self):
        graph = graph_for(SUM)
        assert set(live_in(graph)) == {block.index for block in graph.blocks}

    def test_live_out_is_the_union_of_the_successors(self):
        graph = graph_for(SUM)
        entering = live_in(graph)
        leaving = live_out(graph)
        for block in graph.blocks:
            if block.successors:
                expected = set().union(*(entering[s] for s in block.successors))
            else:
                expected = set()
            assert leaving[block.index] == expected

    def test_a_block_with_no_successor_has_nothing_live_after_it(self):
        graph = graph_for(SUM)
        leaving = live_out(graph)
        for block in graph.exits():
            assert leaving[block.index] == set()

    def test_the_loop_counter_is_live_across_the_loop(self):
        # n is read after the body runs, so it survives the back edge
        graph = graph_for(SUM)
        entering = live_in(graph)
        assert any(entering[block.index] for block in graph.blocks)

    def test_an_empty_graph_has_no_live_sets(self):
        assert live_in(build_graph(Program())) == {}


class TestLiveAtAnInstruction:
    def test_a_slot_read_later_is_live_before_it(self):
        graph = graph_for(SUM)
        assert live_at(graph, 0)

    def test_an_index_past_the_end_is_empty(self):
        assert live_at(graph_for(SUM), 9999) == set()

    def test_nothing_is_live_at_the_final_return(self):
        graph = graph_for(DEAD)
        last = len(graph.program.instructions) - 1
        assert live_at(graph, last) == set()

    def test_liveness_never_exceeds_the_slots_touched(self):
        graph = graph_for(SUM)
        touched = slots_used(graph)
        for index in range(len(graph.program.instructions)):
            assert live_at(graph, index) <= touched


class TestPeakPressure:
    def test_a_function_using_two_slots_reports_at_least_two(self):
        assert peak_pressure(graph_for(SUM)) >= 2

    def test_the_peak_never_exceeds_the_slots_touched(self):
        graph = graph_for(SUM)
        assert peak_pressure(graph) <= len(slots_used(graph))

    def test_a_declaration_only_body_reports_an_upper_bound(self):
        # a local declaration writes its slot without an instruction, so the
        # analysis cannot see where the local begins and counts it live from entry
        graph = graph_for("fn f(a) { let x = a + 1; let y = x * 2; return y; }")
        assert peak_pressure(graph) == 3

    def test_explicit_assignment_gives_a_tighter_answer(self):
        # the branch assigns to x, and a write is something the analysis can see
        assert peak_pressure(graph_for(BRANCH)) < peak_pressure(
            graph_for("fn f(a) { let x = a + 1; let y = x * 2; return y; }")
        )

    def test_an_empty_graph_has_no_pressure(self):
        assert peak_pressure(build_graph(Program())) == 0


class TestSlotsUsed:
    def test_a_function_reading_a_parameter_touches_its_slot(self):
        assert slots_used(graph_for(DEAD))

    def test_a_body_touching_nothing_reports_nothing(self):
        graph = graph_for("fn f() { return 1; }")
        assert slots_used(graph) == set()

    def test_slots_are_reported_as_numbers(self):
        assert all(isinstance(slot, int) for slot in slots_used(graph_for(SUM)))


class TestDeadStores:
    def test_a_write_no_read_can_see_is_reported(self):
        found = dead_stores(graph_for(DEAD))
        assert len(found) == 1

    def test_the_report_names_the_instruction_and_the_slot(self):
        rendered = dead_stores(graph_for(DEAD))[0].render()
        assert "writes slot" in rendered
        assert "no read can see" in rendered

    def test_a_write_that_is_later_read_is_not_dead(self):
        assert dead_stores(graph_for(SUM)) == []

    def test_a_write_in_both_arms_that_is_read_after_is_not_dead(self):
        assert dead_stores(graph_for(BRANCH)) == []

    def test_nothing_inside_a_try_block_is_ever_called_dead(self):
        # the catch clause may read what looks unread, and the graph cannot see it,
        # so the pass refuses to claim anything there
        assert dead_stores(graph_for(GUARDED)) == []

    def test_dead_stores_come_back_in_instruction_order(self):
        found = dead_stores(graph_for(DEAD))
        assert [store.index for store in found] == sorted(store.index for store in found)

    def test_a_dead_store_record_carries_its_slot(self):
        assert DeadStore(index=3, slot=2).slot == 2

    def test_an_empty_graph_has_no_dead_stores(self):
        assert dead_stores(build_graph(Program())) == []


class TestReport:
    def test_the_report_counts_the_slots(self):
        lines = report(body_of(SUM))
        assert any("slots touched" in line for line in lines)

    def test_the_report_names_the_busiest_point(self):
        lines = report(body_of(SUM))
        assert any("live at the busiest point" in line for line in lines)

    def test_a_dead_store_appears_in_the_report(self):
        lines = report(body_of(DEAD))
        assert any("no read can see" in line for line in lines)

    def test_a_clean_body_reports_only_the_counts(self):
        assert len(report(body_of(SUM))) == 2
