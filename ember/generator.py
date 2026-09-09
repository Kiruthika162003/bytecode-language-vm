"""Generating random programs: build only what is certain to be valid.

Random testing is worth far more here than anywhere else in this project, because
there are two independent implementations of the same language and disagreement
between them is a bug in one of them with no interpretation required. That makes the
oracle free, which is the hard part of random testing usually. What is left is the
generation, and the decision that shapes this module is to generate only programs
that are guaranteed to compile and to terminate, rather than generating freely and
discarding what fails.

The reasoning is about where the interesting failures live. A generator that emits
arbitrary token soup spends almost all its output on syntax errors, and a syntax
error tests the parser's refusal path, which is already covered by tests naming
specific mistakes. The disagreements worth finding are in programs that both
backends accept and evaluate differently, so every expression here is built from a
grammar that cannot fail: names come from a scope the generator tracks, so nothing
is ever unbound; division and modulo always get a non-zero literal divisor, because
otherwise most arithmetic programs would end in the same runtime fault instead of
producing a value; string and number operands are never mixed under an operator that
would refuse them; and loops count over a fixed range rather than a computed
condition, so nothing can spin forever. Every one of those restrictions is a class
of program this generator will never explore, which is the honest cost of the
choice, and each is covered by hand written tests instead. The seed is the whole of
the state, so a disagreement found on a machine reproduces exactly on another from
the seed alone, which matters more than variety: a failure nobody can reproduce is
barely a failure report.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

_ARITHMETIC = ("+", "-", "*")
_COMPARISONS = ("<", "<=", ">", ">=", "==", "!=")
_BITWISE = ("&", "|", "^")
_NUMBERS = (0, 1, 2, 3, 7, 12, 40, 100)
_WORDS = ("ada", "grace", "alan", "edsger", "barbara", "hi", "x")
_NAMES = ("a", "b", "c", "d", "e", "f", "g", "h")


@dataclass
class Scope:
    """The names the generator has already bound, so nothing is ever unbound."""

    numbers: list[str] = field(default_factory=list)
    strings: list[str] = field(default_factory=list)
    functions: list[str] = field(default_factory=list)

    @property
    def next_name(self) -> str:
        taken = set(self.numbers) | set(self.strings) | set(self.functions)
        for name in _NAMES:
            if name not in taken:
                return name
        return "v" + str(len(taken))

    def has_numbers(self) -> bool:
        return bool(self.numbers)


class Generator:
    """Builds a random program that is certain to compile and to terminate."""

    def __init__(self, seed: int, depth: int = 3) -> None:
        self._random = random.Random(seed)
        self._depth = depth
        self._scope = Scope()

    def _pick(self, choices):
        return self._random.choice(list(choices))

    def _number(self) -> str:
        return str(self._pick(_NUMBERS))

    def _word(self) -> str:
        return '"' + self._pick(_WORDS) + '"'

    def _nonzero(self) -> str:
        return str(self._pick([n for n in _NUMBERS if n != 0]))

    def number_expression(self, depth: int | None = None) -> str:
        """An expression that always evaluates to a number."""
        remaining = self._depth if depth is None else depth
        if remaining <= 0:
            if self._scope.has_numbers() and self._random.random() < 0.5:
                return self._pick(self._scope.numbers)
            return self._number()
        shape = self._random.randrange(7)
        if shape == 0:
            return self.number_expression(0)
        if shape == 1:
            left = self.number_expression(remaining - 1)
            right = self.number_expression(remaining - 1)
            return f"({left} {self._pick(_ARITHMETIC)} {right})"
        if shape == 2:
            # a literal divisor, so the program cannot end in a division fault
            return f"({self.number_expression(remaining - 1)} / {self._nonzero()})"
        if shape == 3:
            return f"({self.number_expression(remaining - 1)} % {self._nonzero()})"
        if shape == 4:
            return f"(-{self.number_expression(remaining - 1)})"
        if shape == 5:
            left = self._number()
            return f"({left} {self._pick(_BITWISE)} {self._number()})"
        condition = self.condition(remaining - 1)
        left = self.number_expression(remaining - 1)
        right = self.number_expression(remaining - 1)
        return f"({condition} ? {left} : {right})"

    def string_expression(self, depth: int | None = None) -> str:
        """An expression that always evaluates to a string."""
        remaining = self._depth if depth is None else depth
        if remaining <= 0:
            if self._scope.strings and self._random.random() < 0.5:
                return self._pick(self._scope.strings)
            return self._word()
        shape = self._random.randrange(3)
        if shape == 0:
            return self.string_expression(0)
        if shape == 1:
            left = self.string_expression(remaining - 1)
            right = self.string_expression(remaining - 1)
            return f"({left} + {right})"
        return f"str({self.number_expression(remaining - 1)})"

    def condition(self, depth: int | None = None) -> str:
        """A comparison, which is always between two numbers so it cannot refuse."""
        remaining = self._depth if depth is None else depth
        left = self.number_expression(max(remaining - 1, 0))
        right = self.number_expression(max(remaining - 1, 0))
        return f"({left} {self._pick(_COMPARISONS)} {right})"

    def _let_number(self) -> str:
        name = self._scope.next_name
        line = f"let {name} = {self.number_expression()};"
        self._scope.numbers.append(name)
        return line

    def _let_string(self) -> str:
        name = self._scope.next_name
        line = f"let {name} = {self.string_expression()};"
        self._scope.strings.append(name)
        return line

    def _print_number(self) -> str:
        return f"print {self.number_expression()};"

    def _print_string(self) -> str:
        return f"print {self.string_expression()};"

    def _if_statement(self) -> str:
        condition = self.condition()
        then = self._print_number()
        if self._random.random() < 0.5:
            return f"if {condition} {then}"
        return f"if {condition} {then} else {self._print_number()}"

    def _counted_loop(self) -> str:
        # a fixed count, so no generated program can fail to terminate
        name = self._scope.next_name
        limit = self._pick((1, 2, 3, 4))
        self._scope.numbers.append(name)
        body = self._print_number()
        self._scope.numbers.remove(name)
        return f"for (let {name} = 0; {name} < {limit}; {name} = {name} + 1) {body}"

    def _foreach_loop(self) -> str:
        name = self._scope.next_name
        items = ", ".join(self._number() for _ in range(self._random.randrange(1, 4)))
        self._scope.numbers.append(name)
        body = self._print_number()
        self._scope.numbers.remove(name)
        return f"for ({name} in [{items}]) {body}"

    def _function(self) -> str:
        name = "fn" + str(len(self._scope.functions))
        parameter = "p"
        outer = list(self._scope.numbers)
        self._scope.numbers.append(parameter)
        body = f"return {self.number_expression(2)};"
        self._scope.numbers = outer
        self._scope.functions.append(name)
        return f"fn {name}({parameter}) {{ {body} }}"

    def _call(self) -> str:
        if not self._scope.functions:
            return self._print_number()
        return f"print {self._pick(self._scope.functions)}({self.number_expression(1)});"

    def _block(self) -> str:
        outer_numbers = list(self._scope.numbers)
        outer_strings = list(self._scope.strings)
        inner = [self._let_number(), self._print_number()]
        self._scope.numbers = outer_numbers
        self._scope.strings = outer_strings
        return "{ " + " ".join(inner) + " }"

    def statement(self) -> str:
        shape = self._random.randrange(10)
        if shape == 0:
            return self._let_number()
        if shape == 1:
            return self._let_string()
        if shape == 2:
            return self._print_string()
        if shape == 3:
            return self._if_statement()
        if shape == 4:
            return self._counted_loop()
        if shape == 5:
            return self._foreach_loop()
        if shape == 6:
            return self._function()
        if shape == 7:
            return self._call()
        if shape == 8:
            return self._block()
        return self._print_number()

    def program(self, statements: int = 6) -> str:
        lines = [self.statement() for _ in range(statements)]
        if not any(line.startswith("print") for line in lines):
            # a program with no output proves nothing, so make sure of one
            lines.append(self._print_number())
        return "\n".join(lines) + "\n"


def program_for(seed: int, statements: int = 6, depth: int = 3) -> str:
    """One program, determined entirely by the seed so a failure reproduces."""
    return Generator(seed, depth=depth).program(statements)


def programs(count: int, first_seed: int = 0, statements: int = 6) -> list[str]:
    return [program_for(first_seed + offset, statements) for offset in range(count)]
