"""Closures measured: two counters from one factory, and the upvalue that outlived its frame.

A closure is only worth its machinery if each instantiation gets its own
captured state, so this trace calls one factory twice and advances the
counters different numbers of times. The first reaches three and the second
one, which is the whole claim: the compiled body is shared while the
captured variable is not. The second measurement is the one that shows why
upvalues exist at all. By the time either counter runs, the factory call
that declared the variable has returned and its slice of the value stack is
long gone, so the upvalue behind each counter must have been closed, its
value copied out of the vanished slot. The trace reads that flag directly
off the closure rather than inferring it from behaviour, because the
behaviour would look the same right up until the stack slot was reused by
another call, and the flag is what distinguishes working from lucky.
"""

from __future__ import annotations

from ember.interpreter import run as execute
from ember.traces.finding import Finding

NAME = "closure"
FACTORY = "fn make() { let c = 0; fn inc() { c = c + 1; return c; } return inc; }"
SOURCE = (
    FACTORY + " let a = make(); let b = make();"
    " print a(); print a(); print a(); print b();"
)


def run() -> Finding:
    machine = execute(SOURCE)
    first = machine.globals["a"]
    second = machine.globals["b"]
    closed = first.upvalues[0].is_closed and second.upvalues[0].is_closed
    shared_body = first.function is second.function
    distinct_state = first.upvalues[0] is not second.upvalues[0]
    holds = (
        machine.output == ["1", "2", "3", "1"]
        and closed
        and shared_body
        and distinct_state
    )
    claim = (
        "one factory yields independent counters reaching "
        f"{machine.output[2]} and {machine.output[3]} while sharing a single "
        "compiled body, and each upvalue is closed by then, its value copied "
        "out of a stack slot that no longer exists"
    )
    return Finding(NAME, claim, holds)
