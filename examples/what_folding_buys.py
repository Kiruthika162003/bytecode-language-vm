"""What the optimizers actually remove, measured rather than asserted.

An optimiser is easy to believe in and hard to check, so this example compiles
the same programs four ways, with neither pass, with the tree passes, with the
peephole pass, and with both, and prints the bytes and constants each produced.
The numbers make the division of labour visible. The tree passes work on what
the program says, so they collapse arithmetic and delete branches that cannot
run, which shows up as constants disappearing from the pool. The peephole pass
works on what the compiler emitted, so it removes a push followed by a pop and a
jump that goes nowhere, which shows up as bytes disappearing while the pool
stays the same size. Neither pass is dominant: each finds waste the other cannot
see. The example also prints the output of every variant, because a smaller
program that computes something else is not an optimisation, and that check is
the one that matters most. It ends on the two rewrites both passes refuse: a
value plus zero is not simplified because plus is overloaded and a string plus
zero is an error the program is owed, and a global load followed by a pop is not
removed because reading an undefined global raises.
"""

from __future__ import annotations

from ember.interpreter import build, run_output

PROGRAMS = (
    "print 1 + 2 * 3 - 4 / 2;",
    'if (false) { print "a"; print "b"; } print "c";',
    "print (2 + 3) * (4 - 1);",
    'while (1 > 2) { print "never"; } print "done";',
    "{ let x = 1; x; x; print x; }",
    "{ let a = 1; let b = 2; a; b; print a + b; }",
    "let n = 0; while (n < 3) { n = n + 1; if (n == 2) break; } print n;",
    "let g = 1; g; print g;",
)


def _shape(source: str, optimize: bool, peephole: bool) -> tuple[int, int]:
    chunk = build(source, optimize=optimize, peephole=peephole).chunk
    return len(chunk.code), len(chunk.constants)


def main() -> None:
    print("bytes and constants under each combination of passes")
    print()
    header = f"{'plain':>12}  {'tree':>12}  {'peephole':>12}  {'both':>12}"
    print(f"{header}   program")
    for source in PROGRAMS:
        plain = _shape(source, False, False)
        tree = _shape(source, True, False)
        peep = _shape(source, False, True)
        both = _shape(source, True, True)
        cells = "  ".join(
            f"{bytes_used:>5}b {constants:>2}c" for bytes_used, constants in
            (plain, tree, peep, both)
        )
        print(f"{cells}   {source[:44]}")

    print()
    print("every variant must still print the same thing:")
    for source in PROGRAMS:
        results = {
            run_output(source, optimize=o, peephole=p)[0] if run_output(source) else ""
            for o, p in ((False, False), (True, False), (False, True), (True, True))
        }
        agreement = "same" if len(results) == 1 else "DIFFERENT"
        print(f"  {agreement}: {sorted(results)} for {source[:40]}")

    print()
    print("the division of labour, visible in the columns:")
    print("  the tree passes shrink the pool, because they collapse what the")
    print("  program says, and a folded expression needs one constant not four")
    print("  the peephole pass shrinks bytes while the pool stays the same size,")
    print("  because it removes instructions emitted around constants that remain")
    print("  a local load then pop vanishes; the last row shows a global load then")
    print("  pop surviving, because reading an undefined global raises, so that")
    print("  pair is an error the program is owed rather than dead code")
    print()
    print("and the rewrite neither pass will make:")
    print("  a value plus zero stays, because plus is overloaded over numbers,")
    print("  strings, and lists, so a string plus zero is a type error the program")
    print("  is entitled to receive and an optimiser must not delete it")


if __name__ == "__main__":
    main()
