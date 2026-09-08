"""The optimizer: run the tree passes in the order that lets each feed the next.

Neither of the passes here is worth much alone, and their value comes
almost entirely from being run in sequence and then repeated. Constant
folding turns computable expressions into literals, which is what makes a
condition decidable; dead code elimination then removes the branch that
condition selects against, which can expose a further expression to fold
inside what is left. So the passes are run in that order, and the pair is
repeated until a round changes nothing, a fixed point. Iterating rather
than making a single pass is the difference between collapsing one layer
and collapsing all of them, and the loop is bounded so that a pass with a
bug that keeps reporting change cannot spin forever. The optimizer reports
how many rounds it took and whether it changed anything, which is what
makes its effect measurable rather than assumed: a test can compile a
program twice, once optimised and once not, run both, and demand identical
output, which is the only claim an optimiser must never break. Comparing
the two chunk sizes then shows what the passes actually bought, and that
number is measured rather than estimated. The honest limit of this
optimiser is its altitude. It works entirely on the syntax tree, so it can
fold arithmetic and delete unreachable statements, but it cannot see the
bytecode and therefore cannot remove a redundant load, fuse two
instructions, or thread a jump that lands on another jump; those live at a
level this optimiser never reaches, and adding them would mean building an
instruction-level pass with its own jump-retargeting machinery.
"""

from __future__ import annotations

from dataclasses import dataclass

from ember import stmtnodes as s
from ember.constantfold import fold_program
from ember.deadcode import prune_program

_MAX_ROUNDS = 8


@dataclass(frozen=True)
class OptimizationReport:
    rounds: int
    changed: bool


def optimize(statements: list[s.Stmt]) -> tuple[list[s.Stmt], OptimizationReport]:
    current = statements
    rounds = 0
    changed = False
    for _ in range(_MAX_ROUNDS):
        folded = fold_program(current)
        pruned = prune_program(folded)
        rounds += 1
        if pruned == current:
            break
        changed = True
        current = pruned
    return current, OptimizationReport(rounds=rounds, changed=changed)


def optimize_program(statements: list[s.Stmt]) -> list[s.Stmt]:
    optimized, _ = optimize(statements)
    return optimized
