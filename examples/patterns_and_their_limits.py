"""What the pattern engine matches, what it refuses, and where it gives up.

A regular expression engine is easy to demonstrate working and much more useful to
demonstrate failing, because every engine works on the patterns its author tried.
This example runs the same corpus past the host's own engine, which is an
independent implementation of the same conventions, and prints where the two agree.
Agreement across literals, classes, anchors, alternation, groups, bounded repetition
and lazy quantifiers is the whole of the claim this engine makes.

It then shows what the engine refuses, and each refusal is a design decision rather
than an omission. A backreference makes the language no longer regular. Lookahead
needs syntax that would have to be explained in an error message somebody reads at
three in the morning. A group beginning with a question mark could mean either, so it
is refused rather than guessed at, which also refuses the harmless non capturing
group. And a malformed class is refused where it is written rather than quietly read
as literal brackets, because the second reading is never what anybody meant.

The last part is the one worth the space. A pattern of nested quantifiers over a
subject that cannot match is the failure that takes services down, and the example
runs it at increasing lengths, printing where the engine stops trying. That the
refusal arrives in a fraction of a second at a length where a naive engine would run
for years is the whole reason the limit is there. The example also shows the limit
that was not designed and had to be found: an ordinary pattern over a long subject
used to exhaust the host stack while the step count was still tiny, which is why a
repetition of a single character now counts its run instead of recursing through it.
"""

from __future__ import annotations

import re
import time

from ember.errors import Arithmetic
from ember.pattern import compile_pattern, find_all, search

BACKSLASH = chr(92)
CORPUS = (
    ("abc", "xabcy"),
    ("a.c", "abc"),
    ("a*", "aaa"),
    ("a+", "bbb"),
    ("[a-z]+", "AbcD"),
    ("[^a-z]+", "abcDEF"),
    ("^abc$", "xabc"),
    ("cat|dog", "hotdog"),
    ("(ab)+", "abab"),
    ("a{2,3}", "aaaa"),
    (BACKSLASH + "d+", "abc123"),
    ("a*?b", "aaab"),
    ("colou?r", "colour"),
    ("(a*)*b", "b"),
)
REFUSED = (
    ("a backreference", "(a)" + BACKSLASH + "1"),
    ("a lookahead", "(?=a)"),
    ("a non capturing group", "(?:a)"),
    ("an unclosed class", "[a-z"),
    ("a backwards range", "[z-a]"),
)


def _span(pattern: str, subject: str):
    found = search(compile_pattern(pattern), subject)
    return (found.start, found.end) if found else None


def _agreement() -> None:
    print("agreement with the host engine, which is an independent implementation")
    print()
    agreed = 0
    for pattern, subject in CORPUS:
        theirs = re.search(pattern, subject)
        expected = theirs.span() if theirs else None
        mine = _span(pattern, subject)
        matched = "same" if mine == expected else "DIFFERS"
        if mine == expected:
            agreed += 1
        print(f"  {pattern:14s} on {subject!r:12s} {mine!s:12s} {matched}")
    print()
    print(f"{agreed} of {len(CORPUS)} agree")


def _refusals() -> None:
    print("what this engine refuses, and why each refusal is a decision:")
    for label, pattern in REFUSED:
        try:
            compile_pattern(pattern)
            print(f"  {label}: NOT REFUSED")
        except Arithmetic as refused:
            print(f"  {label}: {refused}")


def _the_runaway() -> None:
    print("the pattern that takes services down, at increasing lengths:")
    for length in (10, 16, 20, 26, 40):
        subject = "a" * length + "!"
        began = time.time()
        try:
            search(compile_pattern("(a+)+b"), subject)
            outcome = "completed"
        except Arithmetic:
            outcome = "refused"
        elapsed = time.time() - began
        print(f"  {length:3d} characters: {outcome} in {elapsed:.3f} seconds")
    print()
    print("a naive engine runs for years at the longer lengths; this one stops trying")


def _the_found_limit() -> None:
    print("and the limit that was found rather than designed:")
    for length in (100, 1000, 5000):
        began = time.time()
        found = search(compile_pattern(BACKSLASH + "w+"), "a" * length)
        elapsed = time.time() - began
        reached = found.end if found else 0
        print(f"  an ordinary pattern over {length:5d} characters reached {reached:5d}"
              f" in {elapsed:.3f} seconds")
    print("  this used to exhaust the host stack, because the matcher recursed once per")
    print("  character; a repetition of one character counts its run instead now")


def _every_match() -> None:
    print("finding every match, which is what a program usually wants:")
    digits = compile_pattern(BACKSLASH + "d+")
    subject = "order 66 shipped 1024 items on day 7"
    print(f"  {subject!r}")
    print(f"  numbers: {[one.text for one in find_all(digits, subject)]}")


def main() -> None:
    _agreement()
    print()
    _refusals()
    print()
    _the_runaway()
    print()
    _the_found_limit()
    print()
    _every_match()
    print()
    print("what none of this measures is the cost of the patterns that do match, and")
    print("the step limit does not distinguish a slow match from a runaway one: it")
    print("refuses both, so a legitimate pattern over a large subject can be refused")
    print("for looking like an attack, which is a price this engine chooses to pay")


if __name__ == "__main__":
    main()
