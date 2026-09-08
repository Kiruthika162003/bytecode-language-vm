"""Recovering from failure, and the one failure the language will not let you catch.

A language that can only fail is not much use, so this example works through what
try and catch reach. A thrown value of any type arrives at the catch intact, and
a throw from three calls deep unwinds the frames in between without the functions
along the way needing to know. Then the more useful half: a runtime fault is
catchable too, so dividing by zero, reading an undefined name, indexing past the
end, and calling with the wrong number of arguments can all be recovered from,
each arriving as its message. That makes a catch a genuine safety net rather than
a facility only for errors a program raised on itself. The example then shows the
bookkeeping that is easy to get wrong: leaving a try block by returning, breaking,
or continuing has to remove its handler, and if it did not, a later throw would be
caught by a block that had already finished. Each of those is checked by throwing
afterwards and confirming the throw is caught where it should be. The ending is a
refusal. Runaway recursion raises a stack fault, and a catch does not swallow it,
because that fault reports a limit of the machine rather than a mistake in the
program's logic, and letting a program catch and ignore it would turn a clear
diagnosis into a silent hang.
"""

from __future__ import annotations

from ember.errors import StackFault, Thrown
from ember.interpreter import run, run_output


def main() -> None:
    print("a thrown value arrives at the catch, whatever its type")
    for source, label in (
        ('try { throw "a message"; } catch (e) { print e; }', "a string"),
        ("try { throw 42; } catch (e) { print e + 1; }", "a number, still arithmetic"),
        ("try { throw [1, 2, 3]; } catch (e) { print len(e); }", "a list, still a list"),
    ):
        print(f"  {label}: {run_output(source)}")

    print()
    print("a throw unwinds however many frames stand between it and the catch")
    deep = run_output(
        'fn three() { throw "from the bottom"; }'
        " fn two() { three(); } fn one() { two(); }"
        " try { one(); } catch (e) { print e; }"
    )
    print(f"  three frames deep: {deep}")
    print("  none of the functions in between needed to know a throw was possible")

    print()
    print("a runtime fault is catchable too, which is what makes this a safety net")
    faults = (
        ("division by zero", "print 1 / 0;"),
        ("an undefined name", "print missingName;"),
        ("an index past the end", "let a = [1]; print a[9];"),
        ("the wrong argument count", "fn f(x) { return x; } f();"),
        ("adding mismatched types", 'print 1 + "a";'),
    )
    for label, body in faults:
        source = "try { " + body + " } catch (e) { print e; }"
        caught = run_output(source)[0]
        print(f"  {label}:")
        print(f"    {caught}")

    print()
    print("leaving a try early must not leave its handler behind")
    checks = (
        (
            "by returning",
            'fn f() { try { return "returned"; } catch (e) { return "no"; } }'
            ' print f(); try { throw "later"; } catch (e) { print e; }',
        ),
        (
            "by breaking",
            "for (i in [1, 2]) { try { if (i == 2) break; print i; } catch (e) { } }"
            ' try { throw "later"; } catch (e) { print e; }',
        ),
        (
            "by continuing",
            "for (i in [1, 2]) { try { if (i == 1) continue; print i; } catch (e) { } }"
            ' try { throw "later"; } catch (e) { print e; }',
        ),
    )
    for label, source in checks:
        printed = run_output(source)
        print(f"  {label}: {printed}")
    print("  the later throw reaching its own catch is the evidence; a stale handler")
    print("  would have swallowed it inside a block that had already finished")

    print()
    print("an uncaught throw carries its value out to the host")
    try:
        run('throw "nobody is listening";')
    except Thrown as error:
        print(f"  the error message is: {error}")
        print(f"  and the value itself is still available: {error.value!r}")

    print()
    print("the refusal this example ends on:")
    try:
        run('fn f() { return f(); } try { f(); } catch (e) { print "caught it"; }')
        print("  the catch swallowed it, which would be a bug")
    except StackFault as error:
        print(f"  {error}")
    print("  a catch does not swallow that one. it reports a limit of the machine")
    print("  rather than a mistake in the program's logic, and letting a program")
    print("  ignore it would turn a clear diagnosis into a silent hang")


if __name__ == "__main__":
    main()
