"""State machines as data: the transitions written down, and the ones that are missing found.

A program with a mode, a connection that is opening or open or closed, a parser between
tokens, a game between turns, usually grows that mode as a variable and a scattering of
conditions. What goes wrong is not the conditions but the ones nobody wrote: the combination of
a state and an event that was never considered, which arrives eventually and does something
undefined. A machine written down as data can be asked which combinations are missing before
any of them arrives.

The machine is a map from a state to a map from an event to the next state, so it prints,
serialises through the JSON library, and can be built at run time from a table. Nothing here
holds a function, for the same reason nothing else in this library does: a machine holding
callbacks could not be printed or checked, and the point is to make the shape inspectable.
Anything a transition should cause is done by the caller, which sees the state it moved to.

The completeness check is the reason this exists. Given a machine and the events it should
handle, it reports every state and event pair with no transition, which is the list of things a
program has not decided. That list is usually surprising, and it is far better to see it while
writing than to meet one of its entries in production. Unreachable states are reported the same
way: a state no transition leads to is either dead or evidence of a transition nobody wrote,
and both are worth knowing.

Two decisions about how a machine behaves. An event with no transition from the current state
is refused rather than ignored, because ignoring an unexpected event is how a program ends up
in a mode nobody can explain, and a caller who wants to ignore it can catch the refusal and say
so. And a transition to the state a machine is already in is allowed and is a real transition,
because a machine that stays put on an event has decided to stay put, which is different from
not having decided.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from ember.errors import Arithmetic, TypeMismatch
from ember.valueops import type_name


def _machine_of(value: Any, who: str) -> dict[str, dict[str, str]]:
    """A map from a state to a map from an event to the next state."""
    if not isinstance(value, dict):
        raise TypeMismatch(f"{who} needs a machine as a map, not a {type_name(value)}")
    found: dict[str, dict[str, str]] = {}
    for state, transitions in value.items():
        if not isinstance(state, str):
            raise TypeMismatch(f"{who} needs state names to be strings, and {state!r} is not")
        if not isinstance(transitions, dict):
            raise TypeMismatch(
                f"{who} needs each state to map events to states, and {state!r} maps "
                f"to a {type_name(transitions)}"
            )
        inner: dict[str, str] = {}
        for event, target in transitions.items():
            if not isinstance(event, str):
                raise TypeMismatch(
                    f"{who} needs event names to be strings, and {event!r} is not"
                )
            if not isinstance(target, str):
                raise TypeMismatch(
                    f"{who} needs a transition to name a state, and {state!r} on "
                    f"{event!r} names a {type_name(target)}"
                )
            inner[event] = target
        found[state] = inner
    return found


def _text(value: Any, who: str, what: str) -> str:
    if not isinstance(value, str):
        raise TypeMismatch(f"{who} needs a {what} name as a string, not a {type_name(value)}")
    return value


def _events_of(value: Any, who: str) -> list[str]:
    if not isinstance(value, list):
        raise TypeMismatch(f"{who} needs a list of events, not a {type_name(value)}")
    return [_text(one, who, "event") for one in value]


@dataclass
class Gap:
    """One state and event pair the machine has not decided about."""

    state: str
    event: str

    def render(self) -> str:
        return f"{self.state} has no transition for {self.event}"


@dataclass
class Check:
    """What a machine does not handle, and what it cannot reach."""

    gaps: list[Gap] = field(default_factory=list)
    unreachable: list[str] = field(default_factory=list)
    dangling: list[str] = field(default_factory=list)

    @property
    def complete(self) -> bool:
        return not self.gaps and not self.unreachable and not self.dangling

    def render(self) -> list[str]:
        if self.complete:
            return ["every state handles every event, and every state can be reached"]
        lines = [gap.render() for gap in self.gaps]
        for state in self.unreachable:
            lines.append(f"{state} cannot be reached from the starting state")
        for state in self.dangling:
            lines.append(f"{state} is named by a transition but has no state of its own")
        return lines

    def summary(self) -> str:
        if self.complete:
            return "complete"
        parts: list[str] = []
        if self.gaps:
            parts.append(f"{len(self.gaps)} undecided")
        if self.unreachable:
            parts.append(f"{len(self.unreachable)} unreachable")
        if self.dangling:
            parts.append(f"{len(self.dangling)} dangling")
        return ", ".join(parts)


def _states_of(args: list[Any]) -> list[str]:
    return sorted(_machine_of(args[0], "states"))


def _events_in(args: list[Any]) -> list[str]:
    machine = _machine_of(args[0], "events")
    found: set[str] = set()
    for transitions in machine.values():
        found |= set(transitions)
    return sorted(found)


def _can_move(args: list[Any]) -> bool:
    machine = _machine_of(args[0], "canMove")
    state = _text(args[1], "canMove", "state")
    event = _text(args[2], "canMove", "event")
    return event in machine.get(state, {})


def _move(args: list[Any]) -> str:
    """The state an event moves to, refusing an event the state has not decided about."""
    machine = _machine_of(args[0], "move")
    state = _text(args[1], "move", "state")
    event = _text(args[2], "move", "event")
    if state not in machine:
        raise Arithmetic(f"this machine has no state called {state!r}")
    transitions = machine[state]
    if event not in transitions:
        # ignoring an unexpected event is how a program reaches a mode nobody can
        # explain, so it refuses and a caller who wants to ignore it can catch this
        known = ", ".join(sorted(transitions)) or "nothing"
        raise Arithmetic(
            f"{state!r} has no transition for {event!r}; it handles {known}"
        )
    return transitions[event]


def _follow(args: list[Any]) -> list[str]:
    """Every state a sequence of events passes through, starting from one."""
    machine = args[0]
    state = _text(args[1], "follow", "state")
    events = _events_of(args[2], "follow")
    visited = [state]
    for event in events:
        state = _move([machine, state, event])
        visited.append(state)
    return visited


def _reachable_from(machine: dict[str, dict[str, str]], start: str) -> set[str]:
    seen = {start}
    pending = [start]
    while pending:
        state = pending.pop()
        for target in machine.get(state, {}).values():
            if target not in seen:
                seen.add(target)
                pending.append(target)
    return seen


def check_machine(
    machine: dict[str, dict[str, str]], events: list[str], start: str
) -> Check:
    """Every pair with no transition, every state nothing reaches, every target absent."""
    found = Check()
    for state in sorted(machine):
        for event in events:
            if event not in machine[state]:
                found.gaps.append(Gap(state=state, event=event))
    if start in machine:
        reached = _reachable_from(machine, start)
        found.unreachable = sorted(state for state in machine if state not in reached)
    named: set[str] = set()
    for transitions in machine.values():
        named |= set(transitions.values())
    found.dangling = sorted(state for state in named if state not in machine)
    return found


def _check(args: list[Any]) -> list[str]:
    machine = _machine_of(args[0], "checkMachine")
    events = _events_of(args[1], "checkMachine")
    start = _text(args[2], "checkMachine", "state")
    return check_machine(machine, events, start).render()


def _is_complete(args: list[Any]) -> bool:
    machine = _machine_of(args[0], "machineComplete")
    events = _events_of(args[1], "machineComplete")
    start = _text(args[2], "machineComplete", "state")
    return check_machine(machine, events, start).complete


def _gaps_of(args: list[Any]) -> list[list[str]]:
    machine = _machine_of(args[0], "machineGaps")
    events = _events_of(args[1], "machineGaps")
    start = _text(args[2], "machineGaps", "state")
    return [[gap.state, gap.event] for gap in check_machine(machine, events, start).gaps]


def _unreachable_of(args: list[Any]) -> list[str]:
    machine = _machine_of(args[0], "unreachableStates")
    start = _text(args[1], "unreachableStates", "state")
    return check_machine(machine, [], start).unreachable


def _reachable_of(args: list[Any]) -> list[str]:
    machine = _machine_of(args[0], "reachableStates")
    start = _text(args[1], "reachableStates", "state")
    if start not in machine:
        raise Arithmetic(f"this machine has no state called {start!r}")
    return sorted(_reachable_from(machine, start))


def _terminal_states(args: list[Any]) -> list[str]:
    """States with no way out, which is where a machine can only stop."""
    machine = _machine_of(args[0], "terminalStates")
    return sorted(state for state, transitions in machine.items() if not transitions)


def _describe(args: list[Any]) -> list[str]:
    machine = _machine_of(args[0], "describeMachine")
    lines: list[str] = []
    for state in sorted(machine):
        transitions = machine[state]
        if not transitions:
            lines.append(f"{state} is where it stops")
            continue
        for event in sorted(transitions):
            lines.append(f"{state} on {event} becomes {transitions[event]}")
    return lines


_REGISTRY: dict[str, tuple[int, Any]] = {
    "states": (1, _states_of),
    "events": (1, _events_in),
    "canMove": (3, _can_move),
    "move": (3, _move),
    "follow": (3, _follow),
    "checkMachine": (3, _check),
    "machineComplete": (3, _is_complete),
    "machineGaps": (3, _gaps_of),
    "unreachableStates": (2, _unreachable_of),
    "reachableStates": (2, _reachable_of),
    "terminalStates": (1, _terminal_states),
    "describeMachine": (1, _describe),
}


def install_state_library(machine: Any) -> None:
    for name, (arity, handler) in _REGISTRY.items():
        machine.define_native(name, arity, handler)


def state_names() -> list[str]:
    return sorted(_REGISTRY)
