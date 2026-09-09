"""Documentation from a program: signatures from the tree, prose from the text.

A documentation generator needs two things about each declaration, its shape and what
its author said about it, and in this language they have to be gathered from two
different places. The shape comes from the syntax tree, which knows every parameter,
which of them have defaults, which function gathers the rest, and which class inherits
from which. The prose cannot come from there at all, because the scanner discards
comments: they never become tokens, so no comment survives into the tree. So the prose
is read from the source text directly, by taking a declaration's line from its name
token and walking upwards through the comment lines immediately above it.

That split is the design, and its cost is precision about placement. Reading upwards
from a line means a comment separated from its declaration by a blank line is not
attached, which is right, and a comment attached to the wrong thing when someone leaves
a stray remark just above a function is possible, which is wrong but harmless. The
alternative, teaching the scanner to keep comments as tokens, would put a documentation
concern into the front end that every other consumer of the token stream would then
have to skip past, and the parser would need to decide where a comment belongs, which
is a decision about presentation living in the wrong module.

What comes out is deliberately a reference rather than a manual. Every function, its
parameters with their defaults, whether it takes a rest parameter, and its own comment.
Every class, what it inherits, and each method the same way. What is missing is any
description of what a function returns, because the language has no type annotations
and inferring a return type from the body would be guessing, and any example of use,
because nothing in the source says which calls are exemplary. Both absences are better
than a generator inventing text that reads authoritative and is not.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ember import stmtnodes as s
from ember.parser import parse
from ember.scanner import scan
from ember.valueops import stringify

_NEWLINE = chr(10)
_LINE_COMMENT = "//"


def _comment_above(lines: list[str], line: int) -> str:
    """The run of comment lines immediately above a declaration, joined into prose."""
    gathered: list[str] = []
    at = line - 2
    while at >= 0:
        text = lines[at].strip()
        if not text.startswith(_LINE_COMMENT):
            # a blank line or code ends the run, so a detached remark is not attached
            break
        gathered.append(text[len(_LINE_COMMENT) :].strip())
        at -= 1
    return " ".join(reversed(gathered))


@dataclass
class Parameter:
    name: str
    default: str | None = None
    is_rest: bool = False

    def render(self) -> str:
        if self.is_rest:
            return "..." + self.name
        if self.default is not None:
            return f"{self.name} = {self.default}"
        return self.name


@dataclass
class FunctionDoc:
    name: str
    parameters: list[Parameter] = field(default_factory=list)
    comment: str = ""
    line: int = 0

    @property
    def required(self) -> int:
        return sum(
            1
            for parameter in self.parameters
            if parameter.default is None and not parameter.is_rest
        )

    @property
    def is_variadic(self) -> bool:
        return any(parameter.is_rest for parameter in self.parameters)

    def signature(self) -> str:
        listed = ", ".join(parameter.render() for parameter in self.parameters)
        return f"{self.name}({listed})"

    def render(self, indent: str = "") -> list[str]:
        lines = [f"{indent}{self.signature()}"]
        if self.comment:
            lines.append(f"{indent}  {self.comment}")
        return lines


@dataclass
class ClassDoc:
    name: str
    superclass: str | None = None
    methods: list[FunctionDoc] = field(default_factory=list)
    comment: str = ""
    line: int = 0

    def signature(self) -> str:
        if self.superclass is not None:
            return f"class {self.name} < {self.superclass}"
        return f"class {self.name}"

    def method_named(self, name: str) -> FunctionDoc | None:
        for method in self.methods:
            if method.name == name:
                return method
        return None

    def render(self) -> list[str]:
        lines = [self.signature()]
        if self.comment:
            lines.append(f"  {self.comment}")
        for method in self.methods:
            lines.extend(method.render(indent="  "))
        return lines


@dataclass
class ValueDoc:
    name: str
    is_const: bool = False
    comment: str = ""
    line: int = 0

    def render(self) -> list[str]:
        word = "const" if self.is_const else "let"
        lines = [f"{word} {self.name}"]
        if self.comment:
            lines.append(f"  {self.comment}")
        return lines


@dataclass
class Reference:
    """Everything a program declares at its top level, with whatever was said about it."""

    functions: list[FunctionDoc] = field(default_factory=list)
    classes: list[ClassDoc] = field(default_factory=list)
    values: list[ValueDoc] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.functions) + len(self.classes) + len(self.values)

    @property
    def documented(self) -> int:
        entries = [*self.functions, *self.classes, *self.values]
        return sum(1 for entry in entries if entry.comment)

    def function_named(self, name: str) -> FunctionDoc | None:
        for entry in self.functions:
            if entry.name == name:
                return entry
        return None

    def class_named(self, name: str) -> ClassDoc | None:
        for entry in self.classes:
            if entry.name == name:
                return entry
        return None

    def undocumented(self) -> list[str]:
        entries = [*self.functions, *self.classes, *self.values]
        return [entry.name for entry in entries if not entry.comment]

    def render(self) -> list[str]:
        lines: list[str] = []
        if self.values:
            lines.append("values")
            for value in self.values:
                lines.extend("  " + line for line in value.render())
        if self.functions:
            if lines:
                lines.append("")
            lines.append("functions")
            for entry in self.functions:
                lines.extend("  " + line for line in entry.render())
        if self.classes:
            if lines:
                lines.append("")
            lines.append("classes")
            for entry in self.classes:
                lines.extend("  " + line for line in entry.render())
        return lines


def _default_text(value: object) -> str:
    """A default as it would be written, which means a string keeps its quotes."""
    if isinstance(value, str):
        return chr(34) + value + chr(34)
    return stringify(value)


def _parameters_of(node: s.FunctionStmt) -> list[Parameter]:
    found: list[Parameter] = []
    total = len(node.parameters)
    # the defaults cover the last of the named parameters rather than the first, so
    # they are counted back from the end; reading them forwards attached the default
    # to the wrong parameter, which the printed signature made obvious
    named = total - 1 if node.is_variadic else total
    required = named - len(node.defaults)
    for index, token in enumerate(node.parameters):
        is_rest = node.is_variadic and index == total - 1
        default = None
        if not is_rest and index >= required:
            default = _default_text(node.defaults[index - required])
        found.append(Parameter(name=token.lexeme, default=default, is_rest=is_rest))
    return found


def _function_doc(node: s.FunctionStmt, lines: list[str]) -> FunctionDoc:
    line = node.name.span.start.line
    return FunctionDoc(
        name=node.name.lexeme,
        parameters=_parameters_of(node),
        comment=_comment_above(lines, line),
        line=line,
    )


def describe(source: str) -> Reference:
    """Read a program and gather every top level declaration it makes."""
    lines = source.split(_NEWLINE)
    reference = Reference()
    for statement in parse(scan(source)):
        if isinstance(statement, s.FunctionStmt):
            reference.functions.append(_function_doc(statement, lines))
        elif isinstance(statement, s.ClassStmt):
            line = statement.name.span.start.line
            reference.classes.append(
                ClassDoc(
                    name=statement.name.lexeme,
                    superclass=(
                        statement.superclass.lexeme
                        if statement.superclass is not None
                        else None
                    ),
                    methods=[_function_doc(method, lines) for method in statement.methods],
                    comment=_comment_above(lines, line),
                    line=line,
                )
            )
        elif isinstance(statement, s.LetStmt):
            line = statement.name.span.start.line
            reference.values.append(
                ValueDoc(
                    name=statement.name.lexeme,
                    is_const=statement.is_const,
                    comment=_comment_above(lines, line),
                    line=line,
                )
            )
    return reference


def render(source: str) -> str:
    return _NEWLINE.join(describe(source).render())


def coverage_of(source: str) -> int:
    """The share of declarations carrying a comment, as a percentage."""
    reference = describe(source)
    if reference.count == 0:
        return 100
    return round(100 * reference.documented / reference.count)
