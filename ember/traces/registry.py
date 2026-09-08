"""The registry: the one list of traces, so nothing can be written and then forgotten.

A trace that is not registered is a trace nobody runs, and a set of claims
that quietly stops being swept is worse than no claims at all, because it
still reads as though it were being checked. So the registry is a single
tuple naming every trace, and it is the only thing the command line and the
tests consult. Keeping it as an explicit list rather than discovering modules
by scanning the package is deliberate: automatic discovery would make adding
a trace slightly easier and would also silently drop one whose import broke,
which is exactly the failure this list exists to prevent. Adding a trace
means adding a line here, and a trace whose import fails takes the whole
sweep down loudly instead of vanishing from it.
"""

from __future__ import annotations

from collections.abc import Callable

from ember.traces import (
    agreetrace,
    aritytrace,
    closuretrace,
    costtrace,
    foldtrace,
    inherittrace,
    pooltrace,
    prunetrace,
    serializetrace,
    sharedtrace,
    slottrace,
)
from ember.traces.finding import Finding

TRACES: tuple[Callable[[], Finding], ...] = (
    foldtrace.run,
    prunetrace.run,
    slottrace.run,
    pooltrace.run,
    closuretrace.run,
    sharedtrace.run,
    inherittrace.run,
    aritytrace.run,
    costtrace.run,
    serializetrace.run,
    agreetrace.run,
)


def run_all() -> list[Finding]:
    return [trace() for trace in TRACES]


def broken(findings: list[Finding] | None = None) -> list[Finding]:
    checked = findings if findings is not None else run_all()
    return [finding for finding in checked if not finding.holds]
