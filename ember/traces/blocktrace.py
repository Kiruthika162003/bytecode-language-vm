"""The block pass measured: the dead code every other analysis has had to work around.

The verifier has reported unreachable instructions since it was written, and every
measurement taken since has had to phrase itself carefully because of them: reachable
blocks only, the path count over live nodes, coverage of emitted lines. The reports were
never wrong. The compiler ends every function with a nil-and-return epilogue, and a body
that already returns on every path can never reach it, so the dead instructions were real
and simply not worth removing until something could see the whole function.

This trace is the number that closes that. On the same corpus the verifier uses, the
unoptimised output carries thirteen unreachable instructions, the peephole pass removes all
but one of them by looking at neighbours, and the block pass removes the last as well, so
nothing unreachable survives. The count going to zero rather than nearly zero is the point:
an analysis that has to exclude dead blocks and an analysis that has none to exclude are
different to write, and after this pass the exclusions are precaution rather than
necessity.

The other half is that nothing changed. Removing an instruction no path reaches cannot alter
a run, and that argument is sound and is not evidence, so the trace runs every program in
the corpus both ways and compares the printed output. It also verifies the result, because a
pass that edits jumps can produce something that runs and is wrong, and the verifier is what
notices a target that landed one instruction out.
"""

from __future__ import annotations

from ember.builtins import install_builtins
from ember.interpreter import build, run_output
from ember.traces.finding import Finding
from ember.traces.verifytrace import CORPUS
from ember.verifier import faults_deeply, warnings_deeply
from ember.vm import VM

NAME = "blocks"


def _dead_in(**options) -> int:
    return sum(len(warnings_deeply(build(source, **options))) for source in CORPUS)


def _faults_after_the_pass() -> int:
    return sum(len(faults_deeply(build(source, blocks=True))) for source in CORPUS)


def _outputs_agree() -> int:
    agreed = 0
    for source in CORPUS:
        expected = run_output(source)
        function = build(source, blocks=True)
        machine = VM()
        install_builtins(machine)
        machine.interpret(function)
        if machine.output == expected:
            agreed += 1
    return agreed


def run() -> Finding:
    plain = _dead_in()
    peeped = _dead_in(peephole=True)
    blocked = _dead_in(blocks=True)
    agreed = _outputs_agree()
    faults = _faults_after_the_pass()
    holds = (
        plain > 0
        and blocked == 0
        and peeped > blocked
        and agreed == len(CORPUS)
        and faults == 0
    )
    claim = (
        f"the {plain} unreachable instructions the compiler leaves across {len(CORPUS)} "
        f"programs fall to {peeped} under the peephole pass and to {blocked} under the "
        f"block pass, and all {agreed} programs still print exactly what they printed "
        f"before, with {faults} faults in the result"
    )
    return Finding(NAME, claim, holds)
