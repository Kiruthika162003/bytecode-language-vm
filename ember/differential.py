"""Differential testing: run the same program five ways and insist on one answer.

Two backends and three optimisers give six ways to execute a program, and every one
of them is supposed to produce identical output. The compiled machine unoptimised,
the compiled machine after tree folding, after the bytecode peephole pass, after the
block pass, after all three together, and the tree walking interpreter, which shares
no execution code with any of them. When these disagree the language is wrong
somewhere, and which pair disagrees narrows down where: a difference between the
walker and every compiled form points
at the compiler or the machine, while a difference that appears only under one
optimiser points at that optimiser, because the unoptimised form is the definition
of what the program means.

Output is the only thing compared, and the reason is that output is the only thing
the language promises. Comparing stack shapes or instruction counts across five
configurations would compare implementation detail and fail on differences that are
not bugs, which is exactly how a differential test becomes noise nobody reads. The
comparison is also exact rather than approximate, including on floats: the two
backends do the same arithmetic in the same order on the same Python values, so a
difference in the last digit would mean one of them reordered an operation, which is
a bug worth hearing about rather than a rounding artifact to tolerate.

A refusal counts as a result too, which is the subtlety here. If one configuration
faults and another prints a value, that is a disagreement, and if all of them refuse
then the program is simply invalid and proves nothing about the backends. So a
faulted run records the error's text as its outcome and comparison proceeds
normally, which turns the differential test into a check on the error paths as well:
every configuration must agree about what fails, not only about what succeeds.

The first campaign of eleven hundred generated programs found nothing, and a test
that finds nothing is indistinguishable from a test that cannot find anything, so
the next thing measured was the harness itself. Breaking the tree walker on purpose,
by perturbing one printed line, was caught on fifty seeds out of fifty, and the
suspect attribution named the compiler side correctly every time. Breaking the
folding pass instead, so only that one configuration differed, was attributed to the
folding pass. That is the result that makes the clean campaigns worth reporting: the
agreement is real rather than an artifact of a comparison that never fires. What the
clean run does not establish is absence of bugs in general, only in the region of the
language the generator reaches, which is why its restrictions are written down where
the generation happens.
"""

from __future__ import annotations

from dataclasses import dataclass, field

# imported as a module rather than by name so that a test can replace a backend on
# the module and have this code see the replacement
from ember import interpreter
from ember.errors import EmberError
from ember.generator import program_for

WALKED = "walked"
PLAIN = "compiled"
FOLDED = "compiled+folded"
PEEPED = "compiled+peephole"
BOTH = "compiled+both"
BLOCKED = "compiled+blocks"

CONFIGURATIONS = (WALKED, PLAIN, FOLDED, PEEPED, BLOCKED, BOTH)


@dataclass
class Outcome:
    """What one configuration did with a program: printed lines, or a refusal."""

    label: str
    output: list[str] = field(default_factory=list)
    refusal: str | None = None

    @property
    def refused(self) -> bool:
        return self.refusal is not None

    def comparable(self) -> tuple[str, ...]:
        # a refusal compares as its message, so they must agree about failure too
        if self.refusal is not None:
            return ("refused", self.refusal)
        return ("printed", *self.output)

    def describe(self) -> str:
        if self.refusal is not None:
            return f"{self.label} refused: {self.refusal}"
        return f"{self.label} printed {self.output}"


@dataclass
class Disagreement:
    """A program the configurations did not agree on, with what each one did."""

    source: str
    outcomes: list[Outcome] = field(default_factory=list)
    seed: int | None = None

    def groups(self) -> dict[tuple[str, ...], list[str]]:
        found: dict[tuple[str, ...], list[str]] = {}
        for outcome in self.outcomes:
            found.setdefault(outcome.comparable(), []).append(outcome.label)
        return found

    def suspect(self) -> str:
        """Which part of the system the split points at, read from the grouping."""
        grouped = self.groups()
        labels = {label for listed in grouped.values() for label in listed}
        alone = [listed[0] for listed in grouped.values() if len(listed) == 1]
        if alone == [WALKED]:
            return "the compiler or the machine, since only the walker differs"
        if alone in ([FOLDED], [PEEPED], [BLOCKED]):
            return f"the {alone[0]} pass, since only it differs"
        if WALKED in labels and len(grouped) == 2:
            return "one side of the divide between walking and compiling"
        return "more than one component, since the split is not a clean pair"

    def render(self) -> list[str]:
        lines = [f"seed {self.seed}: the configurations disagree"] if self.seed else []
        lines.append(f"suspect: {self.suspect()}")
        lines.extend(outcome.describe() for outcome in self.outcomes)
        lines.append("source:")
        lines.extend("  " + line for line in self.source.splitlines())
        return lines


def _run_one(source: str, label: str) -> Outcome:
    try:
        if label == WALKED:
            printed = interpreter.run_treewalk_output(source)
        elif label == PLAIN:
            printed = interpreter.run_output(source)
        elif label == FOLDED:
            printed = interpreter.run_output(source, optimize=True)
        elif label == PEEPED:
            printed = interpreter.run_output(source, peephole=True)
        elif label == BLOCKED:
            printed = interpreter.run_output(source, blocks=True)
        else:
            printed = interpreter.run_output(
                source, optimize=True, peephole=True, blocks=True
            )
    except EmberError as refused:
        return Outcome(label=label, refusal=str(refused))
    return Outcome(label=label, output=list(printed))


def outcomes_for(source: str) -> list[Outcome]:
    """What each of the five configurations does with one program."""
    return [_run_one(source, label) for label in CONFIGURATIONS]


def compare(source: str, seed: int | None = None) -> Disagreement | None:
    """None when every configuration agrees, otherwise the disagreement."""
    found = outcomes_for(source)
    shapes = {outcome.comparable() for outcome in found}
    if len(shapes) == 1:
        return None
    return Disagreement(source=source, outcomes=found, seed=seed)


def all_refused(source: str) -> bool:
    """Whether every configuration refused, which means the program proves nothing."""
    return all(outcome.refused for outcome in outcomes_for(source))


@dataclass
class Campaign:
    """The result of comparing many generated programs."""

    checked: int = 0
    agreed: int = 0
    refused: int = 0
    disagreements: list[Disagreement] = field(default_factory=list)

    @property
    def clean(self) -> bool:
        return not self.disagreements

    def summary(self) -> str:
        return (
            f"{self.checked} programs checked, {self.agreed} agreed, "
            f"{self.refused} refused by every backend, "
            f"{len(self.disagreements)} disagreed"
        )


def campaign(count: int, first_seed: int = 0, statements: int = 6) -> Campaign:
    """Generate programs from consecutive seeds and compare every configuration."""
    result = Campaign()
    for offset in range(count):
        seed = first_seed + offset
        source = program_for(seed, statements)
        found = compare(source, seed=seed)
        result.checked += 1
        if found is not None:
            result.disagreements.append(found)
            continue
        if outcomes_for(source)[0].refused:
            result.refused += 1
        else:
            result.agreed += 1
    return result
