"""The line table: recover the source line for a bytecode offset without storing one per byte.

When the machine faults at some bytecode offset, the error should name
the source line, which means the compiled form must remember, for every
byte of code, which line it came from. Storing a full line number beside
every byte would work and is simple, but it roughly doubles the size of
the compiled code to hold numbers that change only rarely, since a whole
expression's worth of bytecode usually shares one line. This module
stores the mapping compactly instead, as a run-length encoding: a list of
runs, each saying a line number and how many consecutive bytes belong to
it. Recording a byte appends to the current run when the line is
unchanged and starts a new run when it is not, so a long stretch on one
line costs a single run regardless of how many bytes it spans. Looking up
an offset walks the runs, subtracting each run's length until the offset
falls inside one. The honest tradeoff is that lookup is linear in the
number of runs rather than constant, which is the price of the
compression; for the error-reporting use, where a lookup happens once, at
the moment of a fault, and never in the hot path, that price is
irrelevant, and a runtime that needed frequent lookups would build a
prefix-sum index over the runs to make them binary-searchable. This
module records lines as bytes are emitted and answers the line for any
offset, refusing an offset past the end.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ember.errors import EmberError


@dataclass
class LineTable:
    _runs: list[list[int]] = field(default_factory=list)
    _length: int = 0

    def record(self, line: int) -> None:
        if line < 1:
            raise EmberError(
                f"a source line is numbered from one, but got {line}"
            )
        if self._runs and self._runs[-1][0] == line:
            self._runs[-1][1] += 1
        else:
            self._runs.append([line, 1])
        self._length += 1

    def line_at(self, offset: int) -> int:
        if offset < 0 or offset >= self._length:
            raise EmberError(
                f"offset {offset} is outside the recorded range of "
                f"{self._length} bytes; nothing maps to it"
            )
        remaining = offset
        for line, count in self._runs:
            if remaining < count:
                return line
            remaining -= count
        raise EmberError("the line table is inconsistent with its length")

    @property
    def length(self) -> int:
        return self._length

    @property
    def run_count(self) -> int:
        return len(self._runs)
