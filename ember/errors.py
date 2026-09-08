"""The exception family: one base to catch everything, many kinds to catch just one.

A language runtime fails in categories that a user cares about keeping
apart. A misspelled keyword is a different problem from dividing by
zero, and a program that calls a function with too few arguments wants
a different message from one that indexes past the end of a list. This
module defines a single base exception so that an embedder can wrap the
whole runtime in one handler, and a spread of specific subclasses so
that a caller who wants to react to just one failure can. Every kind
carries the same contract as the rest of the package: its message is a
sentence that names what went wrong and, where there is one, the
remedy, because an error that only says that something failed forces
the reader to guess. The subclasses deliberately avoid shadowing
Python's own built-in exception names, so that a runtime type error in
the Ember language is never confused with a Python TypeError raised by
a bug in the interpreter itself.
"""

from __future__ import annotations


class EmberError(Exception):
    """The root of every error the runtime raises on purpose.

    Catching this catches every deliberate failure of the scanner,
    parser, compiler, and virtual machine, while letting a genuine
    interpreter bug, which surfaces as an ordinary Python exception,
    pass through uncaught so it is not silently mistaken for a language
    error.
    """


class Syntax(EmberError):
    """The source text could not be scanned or parsed.

    This covers an unterminated string, a stray character, a missing
    closing bracket, and every other shape that is not valid Ember
    before any meaning is assigned to it.
    """


class Resolve(EmberError):
    """A name could not be bound at compile time.

    Using a variable that was never declared, or declaring the same
    local twice in one scope, is caught here while compiling, before the
    program ever runs, rather than left to fail unpredictably later.
    """


class Compile(EmberError):
    """The program is valid but exceeds a limit of the bytecode format.

    A chunk can hold only so many constants and a jump can reach only so
    far; a program that overruns one of these limits is reported here
    rather than producing bytecode that cannot be executed.
    """


class TypeMismatch(EmberError):
    """An operation was given a value of the wrong type.

    Adding a number to a function, or calling something that is not
    callable, raises this at run time with the offending types named.
    """


class Arity(EmberError):
    """A function was called with the wrong number of arguments.

    The message names how many the function expects and how many it
    received, since an off-by-one call is otherwise tedious to locate.
    """


class Unbound(EmberError):
    """A variable was read or assigned that has no binding at run time.

    This is the run-time counterpart of a resolution failure, reserved
    for the cases that only the running program can reveal, such as a
    global referenced before it is ever defined.
    """


class Arithmetic(EmberError):
    """An arithmetic operation has no defined result.

    Division or remainder by zero is the common case; the message names
    the operation rather than leaving a bare failure.
    """


class IndexRange(EmberError):
    """An index or key fell outside what the container holds.

    Reading past the end of a list, or fetching a map key that is
    absent, raises this with the offending index or key named.
    """


class StackFault(EmberError):
    """An internal stack invariant was violated.

    A value-stack underflow or a call depth beyond the machine's limit
    lands here; in a correct compiler the first should never occur, so
    seeing it points at a compiler bug rather than a program bug.
    """


class Immutable(EmberError):
    """An attempt was made to change a binding that cannot change.

    Assigning to a name declared as a constant raises this rather than
    quietly overwriting a value the program promised not to touch.
    """
