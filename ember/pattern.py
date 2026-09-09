"""A small regular expression engine, written out so its limits are visible.

Patterns are compiled to a tree and matched by backtracking. The tree is the honest
representation of what the syntax means: a sequence of terms, each possibly repeated, with
alternation between whole branches, and the matcher walks it trying possibilities and
undoing them. Delegating to the host's regular expression library would have been shorter
and would have imported a dialect nobody chose, with lookahead, backreferences, named
groups and a dozen flags, none of which this language's error messages could explain.
Writing the engine means the supported syntax is exactly what is documented.

What is supported: literal characters, the dot for any character, character classes with
ranges and negation, the anchors for start and end, the three quantifiers for none or
more, one or more, and optional, bounded repetition, grouping, alternation, and the usual
escapes for a digit, a word character, whitespace and their negations. Quantifiers are
greedy, and a question mark after one makes it lazy.

What is not supported, and why. There are no backreferences, because matching a group
against text it matched earlier makes the language no longer regular and turns the matcher
into something whose cost is much harder to reason about. There is no lookahead or
lookbehind, for the same reason plus the awkwardness of explaining them in a refusal
message. Both are absent rather than half implemented, and a pattern using either syntax
is refused with a message saying so rather than being read as something else.

The cost that matters is backtracking. A pattern with nested quantifiers over a long
subject can take time exponential in the subject's length, which is the well known failure
that takes a service down when a pattern meets input nobody tried. This engine does not
solve that: converting to an automaton would, and would cost the group captures that make
the engine useful. Instead there is a step limit, and a match that exceeds it is refused
with a message naming the limit rather than running until something else gives up. A
refusal a program can catch is a great deal better than a hang it cannot.

The step limit turned out not to be the binding one, which only measuring showed. The
matcher passes a continuation to each term and so recursed once per character consumed,
and one or more word characters over five hundred of them exhausted the host's stack while
the step count was still in the hundreds. Two things came out of that. A repetition of a
single character term now counts the run and tries lengths, which costs one level of
recursion however long the run, so the ordinary cases stop touching the stack at all. And
where recursion is genuinely needed, for a repeated group or an alternation, running out of
stack is caught and reported in this language's voice rather than escaping as the host's
error, because a program cannot catch what it has no name for.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ember.errors import Arithmetic

_STEP_LIMIT = 200000
_DIGITS = "0123456789"
_WORD = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_"
_SPACE = " " + chr(9) + chr(10) + chr(13) + chr(11) + chr(12)


@dataclass(frozen=True)
class Literal:
    character: str


@dataclass(frozen=True)
class AnyCharacter:
    pass


@dataclass(frozen=True)
class Class:
    """A character class: the members, whether ranges, and whether it is negated."""

    members: frozenset[str]
    ranges: tuple[tuple[str, str], ...] = ()
    negated: bool = False

    def holds(self, character: str) -> bool:
        inside = character in self.members or any(
            low <= character <= high for low, high in self.ranges
        )
        return not inside if self.negated else inside


@dataclass(frozen=True)
class Start:
    pass


@dataclass(frozen=True)
class End:
    pass


@dataclass
class Group:
    """A parenthesised branch, which captures unless it is marked otherwise."""

    branch: Alternation
    number: int


@dataclass
class Repeat:
    """A term repeated between a lowest and a highest count, greedily or lazily."""

    term: object
    lowest: int
    highest: int | None
    lazy: bool = False


@dataclass
class Sequence:
    terms: list[object] = field(default_factory=list)


@dataclass
class Alternation:
    branches: list[Sequence] = field(default_factory=list)


class _Parser:
    """Recursive descent over the pattern text."""

    def __init__(self, text: str) -> None:
        self._text = text
        self._at = 0
        self._groups = 0

    def _peek(self) -> str:
        return self._text[self._at] if self._at < len(self._text) else ""

    def _take(self) -> str:
        character = self._peek()
        self._at += 1
        return character

    def parse(self) -> Alternation:
        found = self._alternation()
        if self._at < len(self._text):
            raise Arithmetic(
                f"the pattern has an unmatched {self._peek()!r} at position {self._at}"
            )
        return found

    @property
    def group_count(self) -> int:
        return self._groups

    def _alternation(self) -> Alternation:
        branches = [self._sequence()]
        while self._peek() == "|":
            self._take()
            branches.append(self._sequence())
        return Alternation(branches=branches)

    def _sequence(self) -> Sequence:
        terms: list[object] = []
        while self._peek() and self._peek() not in "|)":
            terms.append(self._quantified())
        return Sequence(terms=terms)

    def _quantified(self) -> object:
        term = self._term()
        while True:
            marker = self._peek()
            if marker == "*":
                self._take()
                term = Repeat(term=term, lowest=0, highest=None, lazy=self._maybe_lazy())
            elif marker == "+":
                self._take()
                term = Repeat(term=term, lowest=1, highest=None, lazy=self._maybe_lazy())
            elif marker == "?":
                self._take()
                term = Repeat(term=term, lowest=0, highest=1, lazy=self._maybe_lazy())
            elif marker == "{":
                term = self._bounded(term)
            else:
                return term

    def _maybe_lazy(self) -> bool:
        if self._peek() == "?":
            self._take()
            return True
        return False

    def _bounded(self, term: object) -> object:
        opened = self._at
        self._take()
        digits = ""
        while self._peek().isdigit():
            digits += self._take()
        if not digits:
            raise Arithmetic(f"a repetition count is missing at position {opened}")
        lowest = int(digits)
        highest: int | None = lowest
        if self._peek() == ",":
            self._take()
            more = ""
            while self._peek().isdigit():
                more += self._take()
            highest = int(more) if more else None
        if self._peek() != "}":
            raise Arithmetic(f"the repetition opened at position {opened} is not closed")
        self._take()
        if highest is not None and highest < lowest:
            raise Arithmetic(
                f"a repetition counts up, so {lowest} to {highest} is empty"
            )
        return Repeat(term=term, lowest=lowest, highest=highest, lazy=self._maybe_lazy())

    def _term(self) -> object:
        character = self._take()
        if character == "":
            raise Arithmetic("the pattern ended where a term was needed")
        if character == "(":
            if self._peek() == "?":
                # lookahead and non capturing groups share this prefix, and neither is
                # supported, so it is refused rather than read as something else
                raise Arithmetic(
                    "this engine has no lookahead, lookbehind or group flags, so a "
                    "group beginning with a question mark is refused"
                )
            self._groups += 1
            number = self._groups
            inner = self._alternation()
            if self._peek() != ")":
                raise Arithmetic("a group was opened and never closed")
            self._take()
            return Group(branch=inner, number=number)
        if character == "[":
            return self._class()
        if character == ".":
            return AnyCharacter()
        if character == "^":
            return Start()
        if character == "$":
            return End()
        if character == chr(92):
            return self._escape()
        if character in "*+?":
            raise Arithmetic(f"the quantifier {character!r} has nothing before it")
        return Literal(character=character)

    def _escape(self) -> object:
        marker = self._take()
        if marker == "":
            raise Arithmetic("the pattern ends with an incomplete escape")
        if marker == "d":
            return Class(members=frozenset(_DIGITS))
        if marker == "D":
            return Class(members=frozenset(_DIGITS), negated=True)
        if marker == "w":
            return Class(members=frozenset(_WORD))
        if marker == "W":
            return Class(members=frozenset(_WORD), negated=True)
        if marker == "s":
            return Class(members=frozenset(_SPACE))
        if marker == "S":
            return Class(members=frozenset(_SPACE), negated=True)
        if marker == "n":
            return Literal(character=chr(10))
        if marker == "t":
            return Literal(character=chr(9))
        if marker == "r":
            return Literal(character=chr(13))
        if marker.isdigit():
            raise Arithmetic(
                "this engine has no backreferences, because matching a group against "
                "what it matched before is not a regular language"
            )
        return Literal(character=marker)

    def _class(self) -> Class:
        negated = False
        if self._peek() == "^":
            self._take()
            negated = True
        members: set[str] = set()
        ranges: list[tuple[str, str]] = []
        first = True
        while True:
            character = self._peek()
            if character == "":
                raise Arithmetic("a character class was opened and never closed")
            if character == "]" and not first:
                self._take()
                break
            first = False
            self._take()
            if character == chr(92):
                escaped = self._escape()
                if isinstance(escaped, Class):
                    members |= escaped.members
                    if escaped.negated:
                        raise Arithmetic(
                            "a negated escape inside a character class would mean two "
                            "things at once, so it is refused"
                        )
                    continue
                character = escaped.character  # type: ignore[attr-defined]
            looks_like_range = (
                self._peek() == "-"
                and self._at + 1 < len(self._text)
                and self._text[self._at + 1] != "]"
            )
            if looks_like_range:
                self._take()
                upper = self._take()
                if upper < character:
                    raise Arithmetic(
                        f"a range counts up, so {character!r} to {upper!r} is empty"
                    )
                ranges.append((character, upper))
                continue
            members.add(character)
        return Class(members=frozenset(members), ranges=tuple(ranges), negated=negated)


@dataclass
class Pattern:
    """A compiled pattern: its tree, how many groups it has, and its source."""

    source: str
    tree: Alternation
    groups: int


def compile_pattern(text: str) -> Pattern:
    parser = _Parser(text)
    tree = parser.parse()
    return Pattern(source=text, tree=tree, groups=parser.group_count)


class _Matcher:
    """Backtracking over the tree, counting steps so a runaway pattern refuses."""

    def __init__(self, pattern: Pattern, subject: str) -> None:
        self._pattern = pattern
        self._subject = subject
        self._steps = 0
        self.captures: dict[int, tuple[int, int]] = {}

    def _spend(self) -> None:
        self._steps += 1
        if self._steps > _STEP_LIMIT:
            raise Arithmetic(
                f"matching gave up after {_STEP_LIMIT} steps, which means this pattern "
                "backtracks too much on this subject; a refusal is better than a hang"
            )

    def match_at(self, start: int) -> int | None:
        self.captures = {}
        return self._alternation(self._pattern.tree, start, lambda at: at)

    def _alternation(self, node: Alternation, at: int, then) -> int | None:
        for branch in node.branches:
            kept = dict(self.captures)
            found = self._sequence(branch, 0, at, then)
            if found is not None:
                return found
            self.captures = kept
        return None

    def _sequence(self, node: Sequence, index: int, at: int, then) -> int | None:
        self._spend()
        if index >= len(node.terms):
            return then(at)
        return self._term(
            node.terms[index],
            at,
            lambda next_at: self._sequence(node, index + 1, next_at, then),
        )

    def _term(self, node: object, at: int, then) -> int | None:
        self._spend()
        if isinstance(node, Literal):
            if at < len(self._subject) and self._subject[at] == node.character:
                return then(at + 1)
            return None
        if isinstance(node, AnyCharacter):
            return then(at + 1) if at < len(self._subject) else None
        if isinstance(node, Class):
            if at < len(self._subject) and node.holds(self._subject[at]):
                return then(at + 1)
            return None
        if isinstance(node, Start):
            return then(at) if at == 0 else None
        if isinstance(node, End):
            return then(at) if at == len(self._subject) else None
        if isinstance(node, Group):
            def close(end: int, opened: int = at, number: int = node.number):
                self.captures[number] = (opened, end)
                return then(end)

            return self._alternation(node.branch, at, close)
        if isinstance(node, Repeat):
            return self._repeat(node, at, 0, then)
        return None

    def _single_width(self, node: object, at: int) -> bool:
        """Whether a one character term matches here, without any continuation."""
        if at >= len(self._subject):
            return False
        character = self._subject[at]
        if isinstance(node, Literal):
            return character == node.character
        if isinstance(node, AnyCharacter):
            return True
        return node.holds(character)  # type: ignore[attr-defined]

    def _repeat_simple(self, node: Repeat, at: int, then) -> int | None:
        """Repeat a one character term by counting, not by recursing per character.

        The general path calls itself once per repetition, which meant a pattern as
        ordinary as one or more word characters over a few hundred characters ran the
        host out of stack long before the step limit was anywhere in sight. Counting
        the run first and then trying lengths costs one level of recursion however
        long the run is, which is what makes the common case work at all.
        """
        longest = 0
        while self._single_width(node.term, at + longest):
            self._spend()
            longest += 1
            if node.highest is not None and longest >= node.highest:
                break
        if longest < node.lowest:
            return None
        counts = (
            range(node.lowest, longest + 1)
            if node.lazy
            else range(longest, node.lowest - 1, -1)
        )
        for count in counts:
            self._spend()
            found = then(at + count)
            if found is not None:
                return found
        return None

    def _repeat(self, node: Repeat, at: int, done: int, then) -> int | None:
        self._spend()
        if done == 0 and isinstance(node.term, (Literal, AnyCharacter, Class)):
            return self._repeat_simple(node, at, then)
        can_stop = done >= node.lowest
        can_go = node.highest is None or done < node.highest

        def onwards(next_at: int) -> int | None:
            if next_at == at:
                # a term that matched nothing would repeat for ever, so one empty
                # match is enough and the repetition moves on
                return None
            return self._repeat(node, next_at, done + 1, then)

        if node.lazy and can_stop:
            found = then(at)
            if found is not None:
                return found
        if can_go:
            found = self._term(node.term, at, onwards)
            if found is not None:
                return found
        if not node.lazy and can_stop:
            return then(at)
        return None


@dataclass(frozen=True)
class Match:
    """Where a pattern matched, and what each group captured."""

    start: int
    end: int
    text: str
    groups: tuple[str | None, ...] = ()

    @property
    def length(self) -> int:
        return self.end - self.start

    def group(self, number: int) -> str | None:
        if number == 0:
            return self.text
        if 1 <= number <= len(self.groups):
            return self.groups[number - 1]
        return None


def search(pattern: Pattern, subject: str, begin: int = 0) -> Match | None:
    """The leftmost match at or after begin, which is what search means."""
    for start in range(begin, len(subject) + 1):
        matcher = _Matcher(pattern, subject)
        try:
            end = matcher.match_at(start)
        except RecursionError as deep:
            # the host stack is a second limit below the step limit, and a pattern that
            # reaches it must still refuse in this language's own voice rather than
            # letting the host's error escape
            raise Arithmetic(
                "matching ran out of stack, which means this pattern nests its "
                "repetitions too deeply for the subject; simplify the pattern or "
                "match a shorter subject"
            ) from deep
        if end is not None:
            groups: list[str | None] = []
            for number in range(1, pattern.groups + 1):
                span = matcher.captures.get(number)
                groups.append(subject[span[0] : span[1]] if span else None)
            return Match(
                start=start,
                end=end,
                text=subject[start:end],
                groups=tuple(groups),
            )
    return None


def matches_whole(pattern: Pattern, subject: str) -> bool:
    found = search(pattern, subject)
    return found is not None and found.start == 0 and found.end == len(subject)


def find_all(pattern: Pattern, subject: str) -> list[Match]:
    """Every non overlapping match, left to right."""
    found: list[Match] = []
    at = 0
    while at <= len(subject):
        one = search(pattern, subject, at)
        if one is None:
            return found
        found.append(one)
        # an empty match would leave the position unchanged, so it advances by one
        at = one.end + 1 if one.end == one.start else one.end
    return found


def replace_all(pattern: Pattern, subject: str, replacement: str) -> str:
    pieces: list[str] = []
    at = 0
    for one in find_all(pattern, subject):
        pieces.append(subject[at : one.start])
        pieces.append(replacement)
        at = one.end
    pieces.append(subject[at:])
    return "".join(pieces)


def split_on(pattern: Pattern, subject: str) -> list[str]:
    pieces: list[str] = []
    at = 0
    for one in find_all(pattern, subject):
        if one.end == one.start:
            continue
        pieces.append(subject[at : one.start])
        at = one.end
    pieces.append(subject[at:])
    return pieces
