"""Unwinding measured: a throw three frames deep, and the machine left clean behind it.

A throw that crosses call boundaries has to leave the machine in a state the
program can carry on from, and the interesting evidence is not that the catch ran
but that nothing was left behind. This trace throws from the bottom of a
three-deep call chain and then inspects the machine: no frames remain, no handler
remains registered, and the value stack is empty, which together mean the
unwinding discarded exactly what it should have and no more. The second half
checks the case that is easy to get wrong. Leaving a try block by returning,
breaking, or continuing skips the instruction that would have removed its
handler, so each of those is followed by another throw; that throw reaching its
own catch rather than a stale one is the proof the escaped handler was removed.
The trace also confirms a runtime fault is catchable while an internal stack
fault is not, which is the line between a mistake in the program and a limit of
the machine.
"""

from __future__ import annotations

from ember.errors import StackFault
from ember.interpreter import run as execute
from ember.interpreter import run_output
from ember.traces.finding import Finding

NAME = "unwind"
DEEP = (
    'fn a() { throw "from the bottom"; } fn b() { a(); } fn c() { b(); }'
    " try { c(); } catch (e) { print e; }"
)
ESCAPES = (
    'fn f() { try { return "returned"; } catch (e) { return "no"; } } print f();'
    ' try { throw "later"; } catch (e) { print e; }',
    "for (i in [1, 2]) { try { if (i == 2) break; print i; } catch (e) { } }"
    ' try { throw "later"; } catch (e) { print e; }',
    "for (i in [1, 2]) { try { if (i == 1) continue; print i; } catch (e) { } }"
    ' try { throw "later"; } catch (e) { print e; }',
)


def run() -> Finding:
    machine = execute(DEEP)
    clean = not machine.frames and not machine.handlers and not machine.stack
    escaped = all(run_output(source)[-1] == "later" for source in ESCAPES)
    caught = run_output('try { print 1 / 0; } catch (e) { print "caught"; }') == ["caught"]
    internal_escapes = False
    try:
        execute('fn f() { return f(); } try { f(); } catch (e) { print "no"; }')
    except StackFault:
        internal_escapes = True
    holds = (
        machine.output == ["from the bottom"]
        and clean
        and escaped
        and caught
        and internal_escapes
    )
    claim = (
        f"a throw three frames deep reaches its catch and leaves "
        f"{len(machine.frames)} frames, {len(machine.handlers)} handlers, and "
        f"{len(machine.stack)} stack slots behind; escaping a try by return, break, "
        f"or continue removes its handler in all {len(ESCAPES)} cases, and a runtime "
        "fault is catchable while an internal stack fault still escapes"
    )
    return Finding(NAME, claim, holds)
