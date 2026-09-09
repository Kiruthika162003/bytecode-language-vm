"""Random programs measured: five ways to run them, one answer, and a check on the check.

This is the trace with the largest claim behind it, and the reason it is worth
recording as a number is that the claim is easy to make and easy to make
meaninglessly. Two hundred generated programs run through five configurations, the
tree walker and the compiled machine with each combination of the two optimisers, is
a thousand executions, and every one of them producing identical output says the
implementations agree across the region of the language the generator reaches. What
it does not say, on its own, is that the comparison would have noticed if they had
not, and a differential test that cannot fail is worse than none because it reports
success either way.

So the trace measures its own detection power in the same breath. It breaks the tree
walker deliberately, by perturbing one printed line, and counts how many of the same
programs are then reported as disagreements. That figure has to be all of them, and
the attribution has to name the compiled side rather than shrugging, because a
disagreement report nobody can act on is only marginally better than no report.
Running both halves together means the trace cannot drift into vacuous success: if
the comparison ever stops working, the second number falls and the trace breaks even
though the first number still looks perfect.
"""

from __future__ import annotations

from ember import interpreter
from ember.differential import campaign, compare
from ember.generator import program_for
from ember.traces.finding import Finding

NAME = "fuzz"
COUNT = 200
PROBED = 25


def _with_a_broken_walker() -> int:
    """How many programs are caught as disagreements when a backend is sabotaged."""
    real = interpreter.run_treewalk_output

    def perturbed(source, **options):
        printed = real(source, **options)
        return ["999", *printed[1:]] if printed else printed

    interpreter.run_treewalk_output = perturbed
    try:
        return sum(
            1
            for seed in range(PROBED)
            if compare(program_for(seed), seed=seed) is not None
        )
    finally:
        # the sabotage is restored whatever happens, so a fault here cannot leave
        # every later trace running against a broken backend
        interpreter.run_treewalk_output = real


def run() -> Finding:
    result = campaign(COUNT)
    caught = _with_a_broken_walker()
    holds = result.clean and result.agreed == COUNT and caught == PROBED
    claim = (
        f"{result.agreed} random programs run five ways, walked and compiled with "
        f"each pairing of the two optimisers, give one answer every time, and "
        f"sabotaging a backend is caught on {caught} of {PROBED} of the same "
        "programs, so the agreement is measured rather than assumed"
    )
    return Finding(NAME, claim, holds)
