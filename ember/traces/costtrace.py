"""Recursion measured: what the tenth Fibonacci number costs each backend.

Naive Fibonacci is the standard way to make a runtime work hard for a small
answer, and it exposes different numbers in the two backends. The bytecode
machine reports instructions dispatched and the high-water mark of its value
stack; the tree-walker reports the nodes it visited. Both are exact counts
taken from inside, not timings, which is deliberate: a timing here would
mostly measure the Python interpreter hosting this runtime and would change
between machines, while a dispatch count is a property of the compiled
program and stays put. The stack figure is the one that makes recursion
visible, since the peak depth is what the nesting costs in memory rather
than in work. Comparing the two counts is interesting but not a fair race:
an instruction and a tree node are different units of work, so the honest
reading is that both backends compute the same answer with effort of the
same order, not that one is faster by the ratio of the numbers.
"""

from __future__ import annotations

from ember.interpreter import run as execute
from ember.interpreter import run_treewalk
from ember.traces.finding import Finding

NAME = "cost"
SOURCE = "fn fib(n) { if (n < 2) return n; return fib(n-1) + fib(n-2); } print fib(10);"


def run() -> Finding:
    machine = execute(SOURCE)
    walker = run_treewalk(SOURCE)
    holds = (
        machine.output == ["55"]
        and walker.output == ["55"]
        and machine.instruction_count == 2127
        and machine.max_stack == 24
        and walker.steps == 1947
    )
    claim = (
        f"fib(10) returns {machine.output[0]} from both backends, the machine "
        f"dispatching {machine.instruction_count} instructions and peaking at "
        f"{machine.max_stack} stack slots while the tree-walker visits "
        f"{walker.steps} nodes, counted from inside rather than timed"
    )
    return Finding(NAME, claim, holds)
