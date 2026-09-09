"""The assembly round trip measured: every program written out and read back unchanged.

A text format that claims to be reversible either is or is not, and the claim is cheap to
check: write every program out, read it back, and compare the bytecode. This trace does that
over the corpus and a hundred generated programs, comparing whole function trees rather than
just the top level chunk, because a program's nested functions are where a format that half
works goes wrong.

The number that mattered was twenty one out of twenty two. The one failure was a program with
two classes each having a method called m, which is not an unusual program at all, and it
failed because the first version of the format used a function's own name as its section
label and so could not tell the two apart. That is the whole value of measuring a round trip
on real programs rather than on a couple of examples: the case that breaks the format is one a
language with classes produces constantly, and no amount of reading the code would have shown
it. Sections carry a generated label now and the count is complete.

The trace also runs the reassembled programs. Comparing bytecode proves the format reversible
and says nothing about whether the encoder that rebuilt it produced something the machine can
execute, and those are different claims: an encoder that computed a jump distance wrongly
would produce identical bytes for most programs and land one instruction out on some. So the
printed output of each reassembled program is compared against the original, and the verifier
runs over the result.
"""

from __future__ import annotations

from ember.assembly import from_assembly, to_assembly
from ember.builtins import install_builtins
from ember.function import Function
from ember.generator import program_for
from ember.interpreter import build, run_output
from ember.traces.finding import Finding
from ember.traces.verifytrace import CORPUS
from ember.verifier import faults_deeply
from ember.vm import VM

NAME = "assemble"
GENERATED = 100


def _same_tree(one: Function, other: Function) -> bool:
    if list(one.chunk.code) != list(other.chunk.code):
        return False
    ours = [c for c in one.chunk.constants if isinstance(c, Function)]
    theirs = [c for c in other.chunk.constants if isinstance(c, Function)]
    if len(ours) != len(theirs):
        return False
    return all(_same_tree(a, b) for a, b in zip(ours, theirs, strict=True))


def _round_trips(sources: tuple[str, ...]) -> int:
    found = 0
    for source in sources:
        original = build(source)
        if _same_tree(original, from_assembly(to_assembly(original))):
            found += 1
    return found


def _still_runs() -> tuple[int, int]:
    """How many reassembled programs print the same, and how many faults remain."""
    agreed = 0
    faults = 0
    for source in CORPUS:
        expected = run_output(source)
        rebuilt = from_assembly(to_assembly(build(source)))
        faults += len(faults_deeply(rebuilt))
        machine = VM()
        install_builtins(machine)
        machine.interpret(rebuilt)
        if machine.output == expected:
            agreed += 1
    return agreed, faults


def run() -> Finding:
    generated = tuple(program_for(seed) for seed in range(GENERATED))
    corpus_trips = _round_trips(CORPUS)
    generated_trips = _round_trips(generated)
    agreed, faults = _still_runs()
    holds = (
        corpus_trips == len(CORPUS)
        and generated_trips == GENERATED
        and agreed == len(CORPUS)
        and faults == 0
    )
    claim = (
        f"all {corpus_trips} corpus programs and {generated_trips} generated ones write "
        "out as assembly and read back to identical bytecode, nested functions included, "
        f"and all {agreed} reassembled programs still print what they printed before with "
        f"{faults} faults in the result"
    )
    return Finding(NAME, claim, holds)
