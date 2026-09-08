"""Profiling: count what a program actually executed, by instruction and by source line.

The machine already reports how many instructions a run dispatched, which
answers how much work happened but not where. A profile answers where. It
tallies executions two ways: by opcode, which says what kind of work dominated,
and by source line, which says which line of the program was responsible.
Those two views answer different questions and neither substitutes for the
other. A tally dominated by GET_LOCAL means the program spends its time moving
values rather than computing; a tally dominated by CALL means the cost is in
the calling itself. Meanwhile the line view finds the loop body worth looking
at, which is almost never the line a reader would have guessed. Counting
executions rather than measuring time is the deliberate choice here. A timing
would mostly reflect the Python interpreter hosting this machine and would
differ between runs and between computers, so it would be a fact about the
host; a count is a property of the program and its input, identical every
time, which is what makes it usable in a test. The honest cost is that
profiling is not free and cannot be, since something must be recorded per
instruction: the opcode tally is a dictionary bump, but attributing an
instruction to its line means consulting the run-length line table, which is a
walk rather than a lookup. That is precisely why profiling is opt-in and off
by default, so the ordinary dispatch loop pays only a single branch to skip it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ember.errors import EmberError
from ember.opcode import OpCode


@dataclass
class Profile:
    opcode_counts: dict[OpCode, int] = field(default_factory=dict)
    line_counts: dict[int, int] = field(default_factory=dict)
    frames_entered: int = 0

    def record(self, opcode: OpCode, line: int) -> None:
        self.opcode_counts[opcode] = self.opcode_counts.get(opcode, 0) + 1
        self.line_counts[line] = self.line_counts.get(line, 0) + 1

    def record_frame(self) -> None:
        self.frames_entered += 1

    @property
    def total(self) -> int:
        return sum(self.opcode_counts.values())

    def hottest_line(self) -> tuple[int, int]:
        if not self.line_counts:
            raise EmberError("nothing was profiled, so no line is hottest")
        # ties break toward the earlier line, so the answer is stable across runs
        return min(self.line_counts.items(), key=lambda pair: (-pair[1], pair[0]))

    def hottest_opcode(self) -> tuple[OpCode, int]:
        if not self.opcode_counts:
            raise EmberError("nothing was profiled, so no instruction is hottest")
        return min(
            self.opcode_counts.items(), key=lambda pair: (-pair[1], pair[0].value)
        )

    def by_opcode(self, limit: int | None = None) -> list[tuple[OpCode, int]]:
        ordered = sorted(
            self.opcode_counts.items(), key=lambda pair: (-pair[1], pair[0].value)
        )
        return ordered if limit is None else ordered[:limit]

    def by_line(self, limit: int | None = None) -> list[tuple[int, int]]:
        ordered = sorted(self.line_counts.items(), key=lambda pair: (-pair[1], pair[0]))
        return ordered if limit is None else ordered[:limit]

    def share_of(self, opcode: OpCode) -> float:
        total = self.total
        if total == 0:
            return 0.0
        return self.opcode_counts.get(opcode, 0) / total


def render(profile: Profile, source: str | None = None, limit: int = 8) -> str:
    lines = [
        f"{profile.total} instructions dispatched, "
        f"{profile.frames_entered} frames entered"
    ]
    lines.append("")
    lines.append("by instruction:")
    for opcode, count in profile.by_opcode(limit):
        share = 100.0 * count / profile.total if profile.total else 0.0
        lines.append(f"  {count:8d}  {share:5.1f}%  {opcode.name}")
    lines.append("")
    lines.append("by line:")
    text = source.splitlines() if source is not None else []
    for line, count in profile.by_line(limit):
        share = 100.0 * count / profile.total if profile.total else 0.0
        excerpt = ""
        if 1 <= line <= len(text):
            excerpt = f"  {text[line - 1].strip()}"
        lines.append(f"  {count:8d}  {share:5.1f}%  line {line}{excerpt}")
    return "\n".join(lines)
