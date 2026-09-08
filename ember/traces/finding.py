"""The finding: what a trace reports back, a sentence with numbers in it and a verdict.

A trace exists to make one claim about this runtime and then check it, and
this is the shape of what it returns. The claim is a sentence carrying the
measured numbers rather than an adjective, because a claim that says a
pass makes code smaller is unfalsifiable while one that says seventeen
bytes became five can be checked and can fail. The verdict is a plain
boolean saying whether the conditions the trace tested actually held when
it ran, which is what lets the whole set be swept and any breakage
reported. Keeping the claim as text built at run time from the measured
values, rather than as a static string, is the point of the design: the
numbers in the sentence are the numbers just observed, so a sentence can
never drift out of step with the behaviour it describes the way a comment
can. If a change to the runtime alters a measurement, the trace either
reports the new number or its verdict turns false, and both are visible.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Finding:
    name: str
    claim: str
    holds: bool

    def render(self) -> str:
        mark = "holds" if self.holds else "BROKEN"
        return f"[{mark}] {self.name}: {self.claim}"
