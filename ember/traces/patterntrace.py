"""The pattern engine measured against the host's, and against a pattern built to hang.

Writing a regular expression engine is easy to do almost correctly, and almost correctly
is indistinguishable from correctly until a pattern nobody tried arrives. So this trace
does not assert that the engine works; it compares it, case by case, with the host's own
engine over the syntax both understand. The host is a genuinely independent implementation
written by other people from the same conventions, which makes agreement on a corpus
meaningful in the way agreement between two things sharing code would not be. Where the
two disagree, this engine is wrong, because the conventions are not this project's to
define.

The second half measures the defence rather than the behaviour. A pattern of nested
quantifiers over a subject that cannot match is the standard catastrophic case, and the
engine is supposed to refuse it rather than run until something else gives up. That has to
be measured because it is a claim about what does not happen, and because the limit that
actually binds turned out not to be the one that was written first: the recursion depth of
the matcher was reached long before the step count on a perfectly ordinary pattern, which
is why a repetition of a single character now counts its run instead of recursing through
it. So this trace also matches a long ordinary subject, which is the case that used to
fail, and holds only when both the agreement and the two refusals are all as expected.
"""

from __future__ import annotations

import re

from ember.errors import Arithmetic
from ember.pattern import compile_pattern, search
from ember.traces.finding import Finding

NAME = "pattern"
_BACKSLASH = chr(92)

CORPUS = (
    ("abc", "xabcy"),
    ("abc", "xyz"),
    ("a.c", "abc"),
    ("a*", "aaa"),
    ("a+", "bbb"),
    ("ab?c", "ac"),
    ("[abc]+", "xbcay"),
    ("[a-z]+", "AbcD"),
    ("[^a-z]+", "abcDEF"),
    ("^abc$", "abc"),
    ("^abc$", "xabc"),
    ("a|b", "b"),
    ("cat|dog", "hotdog"),
    ("(ab)+", "abab"),
    ("(a|b)+", "abba"),
    ("a{2}", "aaa"),
    ("a{2,}", "aaaa"),
    ("a{2,3}", "aaaa"),
    (_BACKSLASH + "d+", "abc123"),
    (_BACKSLASH + "w+", " ab_1 "),
    (_BACKSLASH + "s+", "a  b"),
    ("a*?b", "aaab"),
    ("a+?", "aaa"),
    ("(a)(b)", "ab"),
    (_BACKSLASH + "d{3}-" + _BACKSLASH + "d{4}", "call 555-1234 now"),
    ("colou?r", "colour"),
    ("[0-9]+[.][0-9]+", "pi is 3.14"),
    (".*", "anything"),
    ("x*y", "y"),
    ("(a*)*b", "b"),
)

_LONG = 5000


def _agreements() -> int:
    found = 0
    for pattern, subject in CORPUS:
        mine = search(compile_pattern(pattern), subject)
        theirs = re.search(pattern, subject)
        ours = (mine.start, mine.end, mine.text) if mine else None
        yours = (theirs.start(), theirs.end(), theirs.group(0)) if theirs else None
        if ours == yours:
            found += 1
    return found


def _refuses_a_hang() -> bool:
    try:
        search(compile_pattern("(a+)+b"), "a" * 24 + "!")
    except Arithmetic as refused:
        return "backtracks too much" in str(refused)
    return False


def _handles_a_long_subject() -> bool:
    # the case that used to run the host out of stack while the step count was tiny
    found = search(compile_pattern(_BACKSLASH + "w+"), "a" * _LONG)
    return found is not None and found.end == _LONG


def run() -> Finding:
    agreed = _agreements()
    refused = _refuses_a_hang()
    long_subject = _handles_a_long_subject()
    holds = agreed == len(CORPUS) and refused and long_subject
    claim = (
        f"the engine agrees with the host's on {agreed} of {len(CORPUS)} cases spanning "
        "literals, classes, anchors, alternation, groups, bounded repetition and lazy "
        f"quantifiers, matches an ordinary pattern across {_LONG} characters without "
        "running out of stack, and refuses a pattern built to backtrack for ever rather "
        "than hanging on it"
    )
    return Finding(NAME, claim, holds)
