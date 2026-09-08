"""The read-eval-print session: keep one machine alive across many separate inputs.

Running a file is a single act, but a session is a sequence of them that must
share state: a function defined on one line has to still exist on the next.
This module supplies that by keeping one machine and compiling each input as
its own small script against it. That works because globals in this language
are resolved by name at run time, so a later snippet's reference to an earlier
snippet's function is an ordinary global lookup and needs no linking; what does
not carry over is locals, since each input is its own script and a block's
locals live and die inside it. Three behaviours separate a usable session from
a bare loop. A single expression is printed rather than discarded, because
someone who types an arithmetic expression wants to see the answer and would
otherwise get silence; the honest consequence is that calling a function which
returns nothing shows nil, which is the truthful answer rather than a special
case. An input that is obviously unfinished, an open brace or an unterminated
string, is reported as incomplete so a caller can ask for another line instead
of showing a syntax error for text the person is still writing. And a failing
input leaves the session alive and its earlier definitions intact, because
losing an hour of work to one typo is the difference between a tool and a toy.
Detecting incompleteness asks the failure itself whether the text simply ran
out, a flag the scanner and parser set when they reach the end needing more,
rather than matching on the wording of a message, so the rule cannot break when
a message is reworded. Unclosed brackets are counted first, since an input can
be unfinished without having failed yet.
"""

from __future__ import annotations

from ember import stmtnodes as s
from ember.builtins import install_builtins
from ember.compiler import compile_program
from ember.errors import EmberError, Syntax
from ember.parser import parse
from ember.scanner import scan
from ember.tokenkind import TokenKind
from ember.vm import VM

_OPENERS = (TokenKind.LEFT_BRACE, TokenKind.LEFT_PAREN, TokenKind.LEFT_BRACKET)
_CLOSERS = (TokenKind.RIGHT_BRACE, TokenKind.RIGHT_PAREN, TokenKind.RIGHT_BRACKET)


def is_incomplete(source: str) -> bool:
    """Say whether an input looks unfinished rather than wrong."""
    if not source.strip():
        return False
    try:
        tokens = scan(source)
    except Syntax as error:
        return error.at_end
    depth = 0
    for token in tokens:
        if token.kind in _OPENERS:
            depth += 1
        elif token.kind in _CLOSERS:
            depth -= 1
    if depth > 0:
        return True
    try:
        parse(tokens)
    except Syntax as error:
        return error.at_end
    return False


def _auto_print(statements: list[s.Stmt]) -> list[s.Stmt]:
    """Turn a lone expression into a print, so a typed expression shows its value."""
    if len(statements) != 1:
        return statements
    only = statements[0]
    if not isinstance(only, s.ExpressionStmt):
        return statements
    keyword = _first_token(only.expression)
    if keyword is None:
        return statements
    return [s.PrintStmt(keyword, only.expression)]


def _first_token(node: object) -> object | None:
    for attribute in ("token", "name", "operator", "paren", "bracket", "brace", "keyword"):
        candidate = getattr(node, attribute, None)
        if candidate is not None and hasattr(candidate, "line"):
            return candidate
    for attribute in ("left", "inner", "target", "collection", "callee", "operand", "value"):
        child = getattr(node, attribute, None)
        if child is not None:
            found = _first_token(child)
            if found is not None:
                return found
    return None


class Session:
    def __init__(self, with_builtins: bool = True) -> None:
        self.machine = VM()
        if with_builtins:
            install_builtins(self.machine)
        self.inputs = 0
        self.failures = 0

    @property
    def globals(self) -> dict[str, object]:
        return self.machine.globals

    def evaluate(self, source: str) -> list[str]:
        """Run one input and return only the lines it printed."""
        self.inputs += 1
        # a previous input that faulted left frames behind, and running on top
        # of them would let this input's return land inside the abandoned one
        self.machine.reset_execution_state()
        before = len(self.machine.output)
        statements = _auto_print(parse(scan(source)))
        function = compile_program(statements)
        self.machine.interpret(function)
        return self.machine.output[before:]

    def evaluate_safely(self, source: str) -> tuple[list[str], str | None]:
        """Run one input, reporting a fault instead of raising, so the session survives."""
        before = len(self.machine.output)
        try:
            return self.evaluate(source), None
        except EmberError as error:
            self.failures += 1
            # anything the input managed to print before failing is still real
            return self.machine.output[before:], str(error)
