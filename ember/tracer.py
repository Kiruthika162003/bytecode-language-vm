"""Tracing execution: watch the machine run without reimplementing how it runs.

Understanding a program that misbehaves means seeing what the machine actually did,
and there are two ways to provide that. One is a second interpreter that steps rather
than runs, which is how a debugger is often built and which has the fatal property that
it can disagree with the real one: a bug that only appears under the stepping
interpreter, or only outside it, is then a bug in the tool. The other is a callback the
real dispatch loop invokes before each instruction, which is what this module uses. The
machine gained one field and one branch for it, and in exchange every trace is by
construction a trace of the same execution the program would have had.

What a step records is the instruction, the line it came from, the depth of the call
stack and the height of the value stack, plus the top few values. It deliberately does
not record the whole stack. A trace of a recursive function over a few thousand
instructions is already long, and copying the entire stack at each step would make it
both enormous and slow enough to change what it is measuring on anything larger. The top
of the stack is where nearly every instruction does its work, so a fixed window of it
answers most questions and the cost stays proportional to the number of steps rather
than to the size of the program's data.

Two limits matter when reading a trace. A step is recorded before its instruction runs,
so the values shown are the operands rather than the result, and the effect of an
instruction is visible in the step after it. And a trace can be capped, because a
program with a loop can produce more steps than anyone will read: when the cap is
reached the trace stops growing and records that it did, rather than silently keeping
the first thousand steps and letting a reader assume the program ended there.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ember.builtins import install_builtins
from ember.errors import EmberError
from ember.interpreter import build
from ember.opcode import OpCode
from ember.valueops import stringify
from ember.vm import VM

_WINDOW = 3
_DEFAULT_CAP = 10000


@dataclass(frozen=True)
class Step:
    """One instruction, recorded before it ran."""

    index: int
    opcode: OpCode
    line: int
    depth: int
    height: int
    top: tuple[str, ...] = ()

    def render(self) -> str:
        shown = ", ".join(self.top) if self.top else "empty"
        return (
            f"{self.index:5d}  line {self.line:3d}  depth {self.depth}  "
            f"{self.opcode.name:<18} stack {self.height} [{shown}]"
        )


@dataclass
class Trace:
    """Every step of one run, up to the cap."""

    steps: list[Step] = field(default_factory=list)
    cap: int = _DEFAULT_CAP
    capped: bool = False
    refusal: str | None = None
    output: list[str] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.steps)

    @property
    def refused(self) -> bool:
        return self.refusal is not None

    def deepest(self) -> int:
        return max((step.depth for step in self.steps), default=0)

    def tallest(self) -> int:
        return max((step.height for step in self.steps), default=0)

    def lines_touched(self) -> list[int]:
        return sorted({step.line for step in self.steps})

    def opcodes_used(self) -> list[OpCode]:
        seen: list[OpCode] = []
        for step in self.steps:
            if step.opcode not in seen:
                seen.append(step.opcode)
        return seen

    def counts(self) -> dict[OpCode, int]:
        found: dict[OpCode, int] = {}
        for step in self.steps:
            found[step.opcode] = found.get(step.opcode, 0) + 1
        return found

    def at_line(self, line: int) -> list[Step]:
        return [step for step in self.steps if step.line == line]

    def first_of(self, opcode: OpCode) -> Step | None:
        for step in self.steps:
            if step.opcode == opcode:
                return step
        return None

    def summary(self) -> str:
        if self.refused:
            return f"{self.count} steps, then it faulted: {self.refusal}"
        if self.capped:
            return f"{self.count} steps, which is the cap, so the run was longer"
        frames = "frame" if self.deepest() == 1 else "frames"
        steps = "step" if self.count == 1 else "steps"
        return f"{self.count} {steps}, {self.deepest()} {frames} at the deepest"

    def render(self, limit: int | None = None) -> list[str]:
        shown = self.steps if limit is None else self.steps[:limit]
        lines = [step.render() for step in shown]
        if limit is not None and len(self.steps) > limit:
            lines.append(f"... {len(self.steps) - limit} further steps not shown")
        lines.append(self.summary())
        return lines


def _window_of(machine: VM) -> tuple[str, ...]:
    # only the top few values: copying the whole stack at every step would make a
    # trace of a loop both enormous and slow enough to change what it measures
    top = machine.stack[-_WINDOW:]
    return tuple(stringify(value) for value in reversed(top))


def trace(source: str, cap: int = _DEFAULT_CAP, optimize: bool = False) -> Trace:
    """Run a program with a watcher attached and gather what the machine did."""
    # compiling happens before the watcher is attached, so a syntax fault travels out
    # to the caller rather than arriving as a trace of nothing: a program that never
    # compiled did not fault at instruction zero, it never reached instruction zero
    function = build(source, optimize=optimize)
    record = Trace(cap=cap)
    machine = VM()
    install_builtins(machine)

    def watcher(watched: VM, opcode: OpCode) -> None:
        if len(record.steps) >= record.cap:
            record.capped = True
            return
        record.steps.append(
            Step(
                index=len(record.steps),
                opcode=opcode,
                line=watched.current_line(),
                depth=len(watched.frames),
                height=len(watched.stack),
                top=_window_of(watched),
            )
        )

    machine.watch(watcher)
    try:
        machine.interpret(function)
    except EmberError as faulted:
        record.refusal = str(faulted)
    finally:
        # the watcher is detached whatever happened, so a faulted run leaves no hook
        # behind on a machine a caller might reuse
        machine.watch(None)
    record.output = list(machine.output)
    return record


def where_it_faulted(source: str) -> Step | None:
    """The last instruction a faulting program reached, which is where to look."""
    record = trace(source)
    if not record.refused or not record.steps:
        return None
    return record.steps[-1]


def steps_at_line(source: str, line: int) -> int:
    return len(trace(source).at_line(line))


def busiest_line(source: str) -> tuple[int, int]:
    """The line the most instructions came from, and how many."""
    record = trace(source)
    tally: dict[int, int] = {}
    for step in record.steps:
        tally[step.line] = tally.get(step.line, 0) + 1
    if not tally:
        return (0, 0)
    line = max(tally, key=lambda found: (tally[found], -found))
    return (line, tally[line])


def report(source: str, limit: int = 40) -> list[str]:
    return trace(source).render(limit=limit)
