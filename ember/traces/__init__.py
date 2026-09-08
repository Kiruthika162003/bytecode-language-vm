"""Traces: small programs run through the real runtime, each asserting one measured claim.

A trace is not a unit test, though it is checked like one. A test asks
whether a function returns what it should; a trace asks what running a
program through this runtime actually costs and then states the answer in
a sentence with the numbers in it. Seventeen bytes of bytecode became five.
Two counters from one factory reached three and one. A wrong-arity call
executed four instructions and none of them were the callee's. Those are
the claims a reader wants when deciding whether a design choice earned its
complexity, and they are worth keeping separate from the tests because
their value is the number, not the pass. Each trace measures from inside
the machine, using the instruction counter and stack high-water mark the
virtual machine already keeps, so nothing here is estimated from the
source or timed with a clock that would make the result depend on the
host. The set is swept by the command line, which reports every claim and
whether it still holds, so a change that quietly makes the runtime worse
shows up as a number that moved rather than as silence.
"""

from __future__ import annotations
