"""Profiling a program, and why the answer is a count rather than a duration.

Asked where a program spends its effort, most tools answer with time. This one
answers with counts, and the choice is worth defending before the numbers are
read. A timing here would mostly measure the Python interpreter hosting this
machine, would differ between computers, and would differ between two runs on
the same computer, so it would be a fact about the host rather than about the
program. A count of instructions dispatched is a property of the program and its
input, identical every run, which is why a test can assert on it and why the
number below will be the same for any reader. The profile is reported two ways
because they answer different questions. The instruction tally says what kind of
work dominated: a program dominated by loads is moving values, one dominated by
calls is paying for the calling itself. The line tally says which line was
responsible, and it is usually not the line a reader would have guessed. The
example profiles naive Fibonacci, where the guess and the answer happen to
agree, and then a loop where they do not. It ends on what profiling costs: the
line attribution walks a run-length table per instruction, which is why it is
off unless asked for.
"""

from __future__ import annotations

from ember.builtins import install_builtins
from ember.interpreter import build
from ember.profiler import Profile, render
from ember.vm import VM

FIB = """fn fib(n) {
  if (n < 2) return n;
  return fib(n - 1) + fib(n - 2);
}
print fib(10);
"""

LOOP = """let total = 0;
let squares = [];
for (let i = 0; i < 30; i = i + 1) {
  total = total + i;
  push(squares, i * i);
}
print total;
print len(squares);
"""


def _profiled(source: str) -> tuple[Profile, VM]:
    machine = VM()
    install_builtins(machine)
    profile = machine.enable_profiling()
    machine.interpret(build(source))
    return profile, machine


def main() -> None:
    print("naive fibonacci, where the guess and the answer agree")
    profile, machine = _profiled(FIB)
    print(f"  printed {machine.output}")
    print(f"  {profile.total} instructions, {profile.frames_entered} frames entered")
    opcode, count = profile.hottest_opcode()
    line, line_count = profile.hottest_line()
    share = round(100 * profile.share_of(opcode))
    print(f"  hottest instruction: {opcode.name} at {count} ({share}% of all work)")
    print(f"  hottest line: {line}, executed {line_count} times")
    print("  a recursive function's own body dominating is the expected answer")

    print()
    print("a loop, where the interesting line is not the one that looks busiest")
    loop_profile, loop_machine = _profiled(LOOP)
    print(f"  printed {loop_machine.output}")
    print(f"  {loop_profile.total} instructions, "
          f"{loop_profile.frames_entered} frames entered")
    for line_number, executions in loop_profile.by_line(4):
        text = LOOP.splitlines()[line_number - 1].strip()
        print(f"  line {line_number}: {executions:5d}  {text}")
    print("  the loop header runs as often as the body, because the condition and")
    print("  the increment are both attributed to the line they were written on")

    print()
    print("the full report for the loop:")
    for rendered in render(loop_profile, LOOP, limit=4).splitlines():
        print(f"  {rendered}")

    print()
    print("what profiling costs:")
    print("  the instruction tally is a dictionary bump, but attributing an")
    print("  instruction to its line walks the run-length line table, so it is a")
    print("  walk rather than a lookup; that is why profiling is off by default")
    print("  and the ordinary dispatch loop pays only one branch to skip it")


if __name__ == "__main__":
    main()
