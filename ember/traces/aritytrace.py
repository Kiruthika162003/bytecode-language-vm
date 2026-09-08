"""Arity measured: a wrong call is stopped before a single instruction of the body runs.

There are two places a runtime could catch a call that passes the wrong
number of arguments: on entry, before the callee begins, or inside, when a
parameter turns out to be missing. The difference matters because the second
lets the body run partway and leave half-finished effects behind. This trace
gives the callee a print as its very first statement and then calls it with
no arguments, so the output is the witness: if anything was printed, the body
had started. Nothing is printed, and the four instructions dispatched are
the caller's own, loading the function and attempting the call. The trace
checks the instruction count as well as the silence, because a body that ran
and printed nothing would be indistinguishable from one that never started
if only the output were examined.
"""

from __future__ import annotations

from ember.builtins import install_builtins
from ember.errors import Arity
from ember.interpreter import build
from ember.traces.finding import Finding
from ember.vm import VM

NAME = "arity"
SOURCE = 'fn f(x) { print "body ran"; return x; } f();'


def run() -> Finding:
    machine = VM()
    install_builtins(machine)
    refused = False
    try:
        machine.interpret(build(SOURCE))
    except Arity:
        refused = True
    holds = refused and machine.output == [] and machine.instruction_count == 4
    claim = (
        f"a call with the wrong argument count is refused on entry: the callee's "
        f"first statement never printed, leaving {len(machine.output)} lines of "
        f"output, and only {machine.instruction_count} instructions ran, all of "
        "them the caller's"
    )
    return Finding(NAME, claim, holds)
