"""Measuring what a program costs, in instructions rather than in seconds.

A benchmark that reports seconds measures the machine it ran on as much as the program it ran,
and on a machine doing other things it measures those too. Run the same program twice and the
numbers differ; run it on another machine and they differ more. That makes a timing useful for
answering is this fast enough here and today, and close to useless for answering did this change
make it better, which is the question anyone optimising is actually asking.

So what is counted here is instructions dispatched, and the property that makes it worth
counting is that it is exact. The same program on the same input dispatches the same number of
instructions every time, on every machine, so two measurements can be compared and a difference
of one percent is a real difference rather than noise. A change that removes instructions has
removed work, and the number says how much.

What it does not say is how long anything takes, and that gap is real rather than a
technicality. Instructions are not equal: a call sets up a frame, an addition adds, and a
native that sorts a list of a thousand elements is one instruction. A program that replaces
a loop with one call to a sorting native shows far fewer instructions and may well be
slower. So the count answers did this do less work inside the machine, and anything about
wall clock time needs a clock and the caveats that come with one.

The comparison is the part worth having. Two programs computing the same answer can be measured
against each other, and the report gives the ratio as well as the counts, since a difference of
four hundred instructions means nothing without knowing whether the total was five hundred or
five million. Each measured program is also run for its output, and a comparison whose two
sides print different things is reported as such rather than compared: two programs that do
not agree are not two ways of doing one thing, and calling one of them faster would be
meaningless. A program that faults partway through is measured up to the fault, which is a
real count of real work, while a program that does not compile is not measured at all,
because nothing ran.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ember.builtins import install_builtins
from ember.errors import EmberError
from ember.interpreter import build
from ember.vm import VM


@dataclass(frozen=True)
class Measurement:
    """What one program cost, and what it printed while doing it."""

    label: str
    instructions: int
    stack_high_water: int
    output: tuple[str, ...] = ()
    refusal: str | None = None

    @property
    def refused(self) -> bool:
        return self.refusal is not None

    def render(self) -> str:
        if self.refused:
            return f"{self.label}: refused after {self.instructions} instructions"
        return (
            f"{self.label}: {self.instructions} instructions, "
            f"{self.stack_high_water} deep at the tallest"
        )


def measure(source: str, label: str = "program", **options) -> Measurement:
    """Run a program once and count what the machine dispatched.

    Compiling happens before the counting begins, so a program that does not compile
    reaches the caller as a fault rather than as a measurement of zero: there is no
    program to have measured, and reporting one that refused after no instructions
    would read as though it had run.
    """
    function = build(source, **options)
    machine = VM()
    install_builtins(machine)
    refusal: str | None = None
    try:
        machine.interpret(function)
    except EmberError as faulted:
        refusal = str(faulted)
    return Measurement(
        label=label,
        instructions=machine.instruction_count,
        stack_high_water=machine.max_stack,
        output=tuple(machine.output),
        refusal=refusal,
    )


def is_repeatable(source: str, times: int = 3, **options) -> bool:
    """Whether repeated runs dispatch the same count, which is why this is worth counting."""
    counts = {measure(source, **options).instructions for _ in range(times)}
    return len(counts) == 1


@dataclass
class Comparison:
    """Two programs measured against each other, or a note that they disagree."""

    first: Measurement
    second: Measurement
    disagreed: bool = False

    @property
    def difference(self) -> int:
        return self.second.instructions - self.first.instructions

    @property
    def ratio(self) -> float:
        # a difference means nothing without knowing what it is a difference from
        if self.first.instructions == 0:
            return 1.0
        return self.second.instructions / self.first.instructions

    @property
    def better(self) -> str:
        if self.disagreed:
            return "neither, because they do not agree"
        if self.difference == 0:
            return "neither, because they cost the same"
        return self.second.label if self.difference < 0 else self.first.label

    def render(self) -> list[str]:
        lines = [self.first.render(), self.second.render()]
        if self.disagreed:
            # two programs that do not agree are not two ways of doing one thing
            lines.append("these print different things, so their costs are not comparable")
            lines.append(f"{self.first.label} printed {list(self.first.output)}")
            lines.append(f"{self.second.label} printed {list(self.second.output)}")
            return lines
        share = round(self.ratio * 100)
        lines.append(
            f"{self.second.label} costs {share} percent of {self.first.label}, "
            f"a difference of {abs(self.difference)} instructions"
        )
        lines.append(f"the cheaper is {self.better}")
        return lines


def compare(
    first: str, second: str, labels: tuple[str, str] = ("first", "second")
) -> Comparison:
    """Measure two programs and refuse to rank them when they print different things."""
    one = measure(first, labels[0])
    other = measure(second, labels[1])
    disagreed = one.output != other.output or one.refused != other.refused
    return Comparison(first=one, second=other, disagreed=disagreed)


@dataclass
class Suite:
    """Several programs measured together, so their costs sit side by side."""

    measurements: list[Measurement] = field(default_factory=list)

    @property
    def total(self) -> int:
        return sum(one.instructions for one in self.measurements)

    def cheapest(self) -> Measurement | None:
        working = [one for one in self.measurements if not one.refused]
        return min(working, key=lambda one: one.instructions) if working else None

    def dearest(self) -> Measurement | None:
        working = [one for one in self.measurements if not one.refused]
        return max(working, key=lambda one: one.instructions) if working else None

    def render(self) -> list[str]:
        widest = max((len(one.label) for one in self.measurements), default=0)
        lines: list[str] = []
        for one in self.measurements:
            if one.refused:
                lines.append(f"{one.label.ljust(widest)}  refused")
                continue
            lines.append(f"{one.label.ljust(widest)}  {one.instructions} instructions")
        if self.measurements:
            lines.append(f"{self.total} instructions altogether")
        return lines


def run_suite(programs: dict[str, str], **options) -> Suite:
    found = Suite()
    for label, source in programs.items():
        found.measurements.append(measure(source, label, **options))
    return found


def optimiser_effect(source: str) -> Suite:
    """The same program under each optimiser, which is what the passes are for."""
    settings = (
        ("plain", {}),
        ("folded", {"optimize": True}),
        ("peephole", {"peephole": True}),
        ("blocks", {"blocks": True}),
        ("all three", {"optimize": True, "peephole": True, "blocks": True}),
    )
    found = Suite()
    for label, options in settings:
        found.measurements.append(measure(source, label, **options))
    return found


def saved_by_optimising(source: str) -> int:
    """How many instructions the optimisers remove from one run of a program."""
    found = optimiser_effect(source)
    plain = found.measurements[0].instructions
    best = min(one.instructions for one in found.measurements)
    return plain - best
