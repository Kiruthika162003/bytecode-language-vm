from __future__ import annotations

import pytest

from ember.errors import Arithmetic, TypeMismatch
from ember.interpreter import run_output, run_treewalk_output
from ember.statelib import Check, Gap, check_machine, state_names

QUOTE = chr(34)

DOOR = {
    "closed": {"open": "opened", "lock": "locked"},
    "opened": {"close": "closed"},
    "locked": {"unlock": "closed"},
}
ALL_EVENTS = ["open", "close", "lock", "unlock"]


def quoted(text: str) -> str:
    return QUOTE + text + QUOTE


def machine_source(machine: dict[str, dict[str, str]]) -> str:
    states = []
    for state, transitions in machine.items():
        inner = ", ".join(
            f"{quoted(event)}: {quoted(target)}" for event, target in transitions.items()
        )
        states.append(f"{quoted(state)}: {{{inner}}}")
    return "{" + ", ".join(states) + "}"


DOOR_SOURCE = machine_source(DOOR)


def evaluate(expression: str) -> str:
    return run_output(f"print {expression};")[0]


class TestRegistration:
    def test_the_functions_are_named(self):
        assert "move" in state_names()
        assert "checkMachine" in state_names()

    def test_the_names_are_sorted(self):
        assert state_names() == sorted(state_names())

    def test_there_are_twelve_of_them(self):
        assert len(state_names()) == 12


class TestInspecting:
    def test_the_states_are_listed(self):
        assert evaluate(f"states({DOOR_SOURCE})") == '["closed", "locked", "opened"]'

    def test_the_events_are_gathered_from_every_state(self):
        found = evaluate(f"events({DOOR_SOURCE})")
        assert found == '["close", "lock", "open", "unlock"]'

    def test_a_machine_describes_itself(self):
        lines = run_output(f"for (line in describeMachine({DOOR_SOURCE})) print line;")
        assert "closed on open becomes opened" in lines

    def test_a_terminal_state_is_described_as_stopping(self):
        machine = machine_source({"a": {"go": "b"}, "b": {}})
        lines = run_output(f"for (line in describeMachine({machine})) print line;")
        assert "b is where it stops" in lines

    def test_the_terminal_states_are_found(self):
        machine = machine_source({"a": {"go": "b"}, "b": {}})
        assert evaluate(f"terminalStates({machine})") == '["b"]'

    def test_a_machine_with_no_terminal_states_finds_none(self):
        assert evaluate(f"terminalStates({DOOR_SOURCE})") == "[]"


class TestMoving:
    def test_an_event_moves_to_the_next_state(self):
        source = f"move({DOOR_SOURCE}, {quoted('closed')}, {quoted('open')})"
        assert evaluate(source) == "opened"

    def test_a_possible_move_is_recognised(self):
        source = f"canMove({DOOR_SOURCE}, {quoted('closed')}, {quoted('open')})"
        assert evaluate(source) == "true"

    def test_an_impossible_move_is_recognised(self):
        source = f"canMove({DOOR_SOURCE}, {quoted('opened')}, {quoted('lock')})"
        assert evaluate(source) == "false"

    def test_an_undecided_event_is_refused(self):
        # ignoring it is how a program reaches a mode nobody can explain
        source = f"move({DOOR_SOURCE}, {quoted('opened')}, {quoted('lock')})"
        with pytest.raises(Arithmetic) as caught:
            run_output(f"print {source};")
        assert "no transition for" in str(caught.value)

    def test_the_refusal_says_what_the_state_does_handle(self):
        source = f"move({DOOR_SOURCE}, {quoted('opened')}, {quoted('lock')})"
        with pytest.raises(Arithmetic) as caught:
            run_output(f"print {source};")
        assert "it handles close" in str(caught.value)

    def test_a_state_that_is_not_in_the_machine_is_refused(self):
        source = f"move({DOOR_SOURCE}, {quoted('ajar')}, {quoted('open')})"
        with pytest.raises(Arithmetic) as caught:
            run_output(f"print {source};")
        assert "no state called" in str(caught.value)

    def test_a_program_can_catch_the_refusal_and_ignore_it(self):
        source = "try { print move(" + DOOR_SOURCE + ", " + quoted("opened")
        source += ", " + quoted("lock") + "); } catch (e) { print " + quoted("ignored") + "; }"
        assert run_output(source) == ["ignored"]

    def test_a_transition_to_the_same_state_is_a_real_transition(self):
        # staying put on an event is a decision, unlike not having decided
        machine = machine_source({"a": {"stay": "a"}})
        source = f"move({machine}, {quoted('a')}, {quoted('stay')})"
        assert evaluate(source) == "a"

    def test_a_terminal_state_refuses_every_event(self):
        machine = machine_source({"a": {}})
        with pytest.raises(Arithmetic) as caught:
            run_output(f"print move({machine}, {quoted('a')}, {quoted('go')});")
        assert "it handles nothing" in str(caught.value)


class TestFollowing:
    def test_a_sequence_of_events_gives_every_state(self):
        events = f"[{quoted('open')}, {quoted('close')}, {quoted('lock')}]"
        source = f"follow({DOOR_SOURCE}, {quoted('closed')}, {events})"
        assert evaluate(source) == '["closed", "opened", "closed", "locked"]'

    def test_following_no_events_gives_the_starting_state(self):
        source = f"follow({DOOR_SOURCE}, {quoted('closed')}, [])"
        assert evaluate(source) == '["closed"]'

    def test_an_impossible_step_refuses_the_whole_sequence(self):
        events = f"[{quoted('open')}, {quoted('lock')}]"
        with pytest.raises(Arithmetic):
            run_output(f"print follow({DOOR_SOURCE}, {quoted('closed')}, {events});")

    def test_a_round_trip_returns_to_where_it_began(self):
        events = f"[{quoted('open')}, {quoted('close')}]"
        source = f"follow({DOOR_SOURCE}, {quoted('closed')}, {events})"
        assert evaluate(source).endswith('"closed"]')


class TestCompleteness:
    def test_a_machine_missing_transitions_is_incomplete(self):
        found = check_machine(DOOR, ALL_EVENTS, "closed")
        assert not found.complete
        assert found.gaps

    def test_every_missing_pair_is_reported(self):
        found = check_machine(DOOR, ALL_EVENTS, "closed")
        # three states and four events is twelve pairs, and the door writes four
        # transitions, so eight pairs are undecided
        assert len(found.gaps) == 3 * 4 - 4

    def test_a_gap_names_its_state_and_event(self):
        found = check_machine(DOOR, ALL_EVENTS, "closed")
        assert any(gap.state == "opened" and gap.event == "lock" for gap in found.gaps)

    def test_a_gap_renders_readably(self):
        assert Gap("opened", "lock").render() == "opened has no transition for lock"

    def test_a_machine_handling_everything_is_complete(self):
        machine = {"a": {"go": "b", "stop": "a"}, "b": {"go": "b", "stop": "a"}}
        assert check_machine(machine, ["go", "stop"], "a").complete

    def test_a_complete_check_says_so(self):
        machine = {"a": {"go": "a"}}
        rendered = check_machine(machine, ["go"], "a").render()[0]
        assert "every state handles every event" in rendered

    def test_an_empty_check_is_complete(self):
        assert Check().complete

    def test_a_program_can_ask_whether_a_machine_is_complete(self):
        events = "[" + ", ".join(quoted(one) for one in ALL_EVENTS) + "]"
        source = f"machineComplete({DOOR_SOURCE}, {events}, {quoted('closed')})"
        assert evaluate(source) == "false"

    def test_a_program_can_ask_for_the_gaps(self):
        events = "[" + ", ".join(quoted(one) for one in ALL_EVENTS) + "]"
        source = f"machineGaps({DOOR_SOURCE}, {events}, {quoted('closed')})"
        assert '["opened", "lock"]' in evaluate(source)

    def test_the_summary_counts_the_problems(self):
        found = check_machine(DOOR, ALL_EVENTS, "closed")
        assert "8 undecided" in found.summary()

    def test_a_complete_machine_summarises_as_complete(self):
        assert check_machine({"a": {"go": "a"}}, ["go"], "a").summary() == "complete"


class TestReachability:
    def test_every_state_of_a_connected_machine_is_reachable(self):
        assert check_machine(DOOR, [], "closed").unreachable == []

    def test_a_stranded_state_is_reported(self):
        machine = {"a": {}, "orphan": {}}
        assert check_machine(machine, [], "a").unreachable == ["orphan"]

    def test_a_program_can_ask_for_the_unreachable_states(self):
        machine = machine_source({"a": {}, "orphan": {}})
        assert evaluate(f"unreachableStates({machine}, {quoted('a')})") == '["orphan"]'

    def test_a_program_can_ask_what_is_reachable(self):
        source = f"reachableStates({DOOR_SOURCE}, {quoted('closed')})"
        assert evaluate(source) == '["closed", "locked", "opened"]'

    def test_reachability_from_a_state_that_is_absent_is_refused(self):
        with pytest.raises(Arithmetic):
            run_output(f"print reachableStates({DOOR_SOURCE}, {quoted('ajar')});")

    def test_a_state_reached_only_indirectly_counts(self):
        machine = machine_source({"a": {"go": "b"}, "b": {"go": "c"}, "c": {}})
        assert evaluate(f"reachableStates({machine}, {quoted('a')})") == '["a", "b", "c"]'


class TestDanglingTargets:
    def test_a_transition_to_a_state_that_does_not_exist_is_reported(self):
        machine = {"a": {"go": "nowhere"}}
        found = check_machine(machine, ["go"], "a")
        assert found.dangling == ["nowhere"]

    def test_the_report_explains_it(self):
        machine = {"a": {"go": "nowhere"}}
        lines = check_machine(machine, ["go"], "a").render()
        assert any("has no state of its own" in line for line in lines)

    def test_a_machine_with_no_dangling_targets_reports_none(self):
        assert check_machine(DOOR, [], "closed").dangling == []

    def test_a_dangling_target_makes_a_machine_incomplete(self):
        machine = {"a": {"go": "nowhere"}}
        assert not check_machine(machine, ["go"], "a").complete


class TestRefusals:
    def test_a_machine_that_is_not_a_map_is_refused(self):
        with pytest.raises(TypeMismatch) as caught:
            run_output("print states(5);")
        assert "machine as a map" in str(caught.value)

    def test_a_state_mapping_to_something_else_is_refused(self):
        source = "{" + quoted("a") + ": 5}"
        with pytest.raises(TypeMismatch) as caught:
            run_output(f"print states({source});")
        assert "map events to states" in str(caught.value)

    def test_a_transition_to_a_number_is_refused(self):
        source = "{" + quoted("a") + ": {" + quoted("go") + ": 5}}"
        with pytest.raises(TypeMismatch) as caught:
            run_output(f"print states({source});")
        assert "transition to name a state" in str(caught.value)

    def test_a_state_name_that_is_not_a_string_is_refused(self):
        with pytest.raises(TypeMismatch):
            run_output("print states({1: {}});")

    def test_a_starting_state_that_is_not_a_string_is_refused(self):
        with pytest.raises(TypeMismatch):
            run_output(f"print reachableStates({DOOR_SOURCE}, 5);")

    def test_a_list_of_events_that_is_not_a_list_is_refused(self):
        with pytest.raises(TypeMismatch):
            run_output(f"print machineGaps({DOOR_SOURCE}, 5, {quoted('closed')});")


class TestBothBackendsAgree:
    @pytest.mark.parametrize(
        "expression",
        [
            f"states({DOOR_SOURCE})",
            f"events({DOOR_SOURCE})",
            f"canMove({DOOR_SOURCE}, {quoted('closed')}, {quoted('open')})",
            f"move({DOOR_SOURCE}, {quoted('closed')}, {quoted('lock')})",
            f"follow({DOOR_SOURCE}, {quoted('closed')}, [{quoted('open')}])",
            f"terminalStates({DOOR_SOURCE})",
            f"describeMachine({DOOR_SOURCE})",
            f"reachableStates({DOOR_SOURCE}, {quoted('closed')})",
            f"unreachableStates({DOOR_SOURCE}, {quoted('closed')})",
            f"machineComplete({DOOR_SOURCE}, [{quoted('open')}], {quoted('closed')})",
            f"machineGaps({DOOR_SOURCE}, [{quoted('open')}], {quoted('closed')})",
            f"checkMachine({DOOR_SOURCE}, [{quoted('open')}], {quoted('closed')})",
        ],
    )
    def test_the_two_backends_agree(self, expression):
        source = f"print {expression};"
        assert run_output(source) == run_treewalk_output(source)
