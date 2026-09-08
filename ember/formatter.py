"""The formatter: print a syntax tree back out as source in one canonical shape.

A formatter is the parser's mirror, and writing one is a sharper test of a tree
than reading it: any information the parser dropped shows up here as something
that cannot be printed. This one walks the tree and emits source with one
consistent layout, two spaces of indentation per level, a space around every
binary operator, braces on the same line as the construct that opens them. The
interesting part is not the layout but the parentheses. The tree records
grouping structurally, so the printer must decide where parentheses are needed
to make the text parse back to the same tree, and adding them everywhere would
be correct and unreadable. So it compares precedence: a child is wrapped only
when its operator binds more loosely than its parent's, or binds equally and
sits on the side that associativity would regroup. That rule is what lets the
sum of two products print without parentheses while the product of two sums
keeps them. Two properties make the module checkable rather than merely
plausible, and both are asserted in the tests. Formatting is idempotent:
formatting already formatted text changes nothing, which catches a printer that
adds or drops a token each pass. And formatting preserves meaning: parsing the
output and running it produces exactly what the original produced, which catches
a printer that loses a parenthesis and quietly changes an expression's value.
The honest limitation is that comments are not preserved, because the scanner
discards them as trivia and the tree never sees them, so formatting a commented
program silently strips its commentary; keeping them would mean attaching trivia
to tokens, a real change to the front end rather than an addition here.
"""

from __future__ import annotations

from ember import exprnodes as e
from ember import stmtnodes as s
from ember.interpolation import TEXT as _TEXT
from ember.precedence import Precedence, infix_precedence
from ember.tokenkind import TokenKind
from ember.valueops import stringify

_INDENT = "  "

_UNARY_TEXT = {
    TokenKind.MINUS: "-",
    TokenKind.BANG: "!",
    TokenKind.NOT: "not ",
    TokenKind.TILDE: "~",
}


def _literal_text(value: object) -> str:
    if isinstance(value, str):
        escaped = value.replace(chr(92), chr(92) * 2).replace('"', chr(92) + '"')
        escaped = escaped.replace(chr(10), chr(92) + "n").replace(chr(9), chr(92) + "t")
        return '"' + escaped + '"'
    return stringify(value)


def _precedence_of(node: e.Expr) -> Precedence:
    if isinstance(node, e.Grouping):
        # a group prints as its contents, so it must report the contents'
        # precedence; reporting it as primary was a bug that dropped the
        # parentheses from a sum multiplied by something, silently changing
        # (1 + 2) * 3 into 1 + 2 * 3
        return _precedence_of(node.inner)
    if isinstance(node, (e.Binary, e.Logical)):
        return infix_precedence(node.operator.kind)
    if isinstance(node, e.Conditional):
        return Precedence.CONDITIONAL
    if isinstance(node, (e.Assign, e.Set, e.SetIndex)):
        return Precedence.ASSIGNMENT
    if isinstance(node, e.Unary):
        return Precedence.UNARY
    if isinstance(node, (e.Call, e.Index, e.Get, e.Super)):
        return Precedence.CALL
    return Precedence.PRIMARY


def expression(node: e.Expr) -> str:
    if isinstance(node, e.Literal):
        return _literal_text(node.value)
    if isinstance(node, e.Interpolation):
        pieces = []
        for kind, value in node.parts:
            if kind == _TEXT:
                inner = value.replace(chr(92), chr(92) * 2).replace('"', chr(92) + '"')
                inner = inner.replace("$", chr(92) + "$")
                pieces.append(inner.replace(chr(10), chr(92) + "n"))
            else:
                pieces.append("${" + expression(value) + "}")
        return '"' + "".join(pieces) + '"'
    if isinstance(node, e.Variable):
        return node.name.lexeme
    if isinstance(node, e.This):
        return "this"
    if isinstance(node, e.Super):
        return f"super.{node.method.lexeme}"
    if isinstance(node, e.Grouping):
        # the tree already records grouping, so an explicit group node is printed
        # by whatever its contents need rather than by always adding parentheses
        return expression(node.inner)
    if isinstance(node, e.Unary):
        return _UNARY_TEXT[node.operator.kind] + _wrap(node.operand, Precedence.UNARY)
    if isinstance(node, (e.Binary, e.Logical)):
        return _binary(node)
    if isinstance(node, e.Conditional):
        condition = _wrap(node.condition, Precedence.OR)
        when_true = expression(node.when_true)
        when_false = _wrap(node.when_false, Precedence.CONDITIONAL)
        return f"{condition} ? {when_true} : {when_false}"
    if isinstance(node, e.Assign):
        return f"{node.name.lexeme} = {expression(node.value)}"
    if isinstance(node, e.Call):
        arguments = ", ".join(expression(argument) for argument in node.arguments)
        return f"{_wrap(node.callee, Precedence.CALL)}({arguments})"
    if isinstance(node, e.Index):
        return f"{_wrap(node.collection, Precedence.CALL)}[{expression(node.key)}]"
    if isinstance(node, e.SetIndex):
        target = _wrap(node.collection, Precedence.CALL)
        return f"{target}[{expression(node.key)}] = {expression(node.value)}"
    if isinstance(node, e.Get):
        return f"{_wrap(node.target, Precedence.CALL)}.{node.name.lexeme}"
    if isinstance(node, e.Set):
        target = _wrap(node.target, Precedence.CALL)
        return f"{target}.{node.name.lexeme} = {expression(node.value)}"
    if isinstance(node, e.ListLiteral):
        return "[" + ", ".join(expression(item) for item in node.elements) + "]"
    if isinstance(node, e.MapLiteral):
        pairs = ", ".join(
            f"{expression(key)}: {expression(value)}" for key, value in node.pairs
        )
        return "{" + pairs + "}"
    raise TypeError(f"the formatter cannot print {type(node).__name__}")


def _binary(node: e.Binary | e.Logical) -> str:
    level = infix_precedence(node.operator.kind)
    # a left-associative operator regroups its right side, so the right child
    # needs parentheses at equal precedence while the left child does not
    left = _wrap(node.left, level)
    right = _wrap(node.right, Precedence(level + 1))
    return f"{left} {node.operator.lexeme} {right}"


def _wrap(node: e.Expr, minimum: Precedence) -> str:
    text = expression(node)
    if _precedence_of(node) < minimum:
        return f"({text})"
    return text


def statement(node: s.Stmt, depth: int = 0) -> str:
    pad = _INDENT * depth
    if isinstance(node, s.ExpressionStmt):
        return f"{pad}{expression(node.expression)};"
    if isinstance(node, s.PrintStmt):
        return f"{pad}print {expression(node.expression)};"
    if isinstance(node, s.LetStmt):
        keyword = "const" if node.is_const else "let"
        if node.initializer is None:
            return f"{pad}{keyword} {node.name.lexeme};"
        return f"{pad}{keyword} {node.name.lexeme} = {expression(node.initializer)};"
    if isinstance(node, s.Block):
        return _block(node.statements, depth)
    if isinstance(node, s.IfStmt):
        return _if(node, depth)
    if isinstance(node, s.WhileStmt):
        head = f"{pad}while ({expression(node.condition)})"
        return head + _attached(node.body, depth)
    if isinstance(node, s.ForStmt):
        return _for(node, depth)
    if isinstance(node, s.ForEachStmt):
        head = f"{pad}for ({node.variable.lexeme} in {expression(node.iterable)})"
        return head + _attached(node.body, depth)
    if isinstance(node, s.FunctionStmt):
        return _function(node, depth, keyword="fn ")
    if isinstance(node, s.ClassStmt):
        return _class(node, depth)
    if isinstance(node, s.ReturnStmt):
        if node.value is None:
            return f"{pad}return;"
        return f"{pad}return {expression(node.value)};"
    if isinstance(node, s.BreakStmt):
        return f"{pad}break;"
    if isinstance(node, s.ContinueStmt):
        return f"{pad}continue;"
    if isinstance(node, s.ThrowStmt):
        return f"{pad}throw {expression(node.value)};"
    if isinstance(node, s.MatchStmt):
        return _match(node, depth)
    if isinstance(node, s.TryStmt):
        return _try(node, depth)
    raise TypeError(f"the formatter cannot print {type(node).__name__}")


def _block(statements: tuple[s.Stmt, ...], depth: int) -> str:
    pad = _INDENT * depth
    if not statements:
        return pad + "{ }"
    lines = [pad + "{"]
    for inner in statements:
        lines.append(statement(inner, depth + 1))
    lines.append(pad + "}")
    return chr(10).join(lines)


def _attached(body: s.Stmt, depth: int) -> str:
    """Print a construct's body, on the same line when it is a block."""
    if isinstance(body, s.Block):
        return " " + _block(body.statements, depth).lstrip()
    return chr(10) + statement(body, depth + 1)


def _if(node: s.IfStmt, depth: int) -> str:
    pad = _INDENT * depth
    text = f"{pad}if ({expression(node.condition)})" + _attached(node.then_branch, depth)
    if node.else_branch is None:
        return text
    if isinstance(node.then_branch, s.Block):
        text += " else"
    else:
        text += chr(10) + pad + "else"
    return text + _attached(node.else_branch, depth)


def _for(node: s.ForStmt, depth: int) -> str:
    pad = _INDENT * depth
    initializer = statement(node.initializer, 0).strip() if node.initializer else ";"
    condition = expression(node.condition) if node.condition else ""
    increment = expression(node.increment) if node.increment else ""
    head = f"{pad}for ({initializer} {condition}; {increment})"
    return head + _attached(node.body, depth)


def _parameters(node: s.FunctionStmt) -> str:
    names = [parameter.lexeme for parameter in node.parameters]
    if node.is_variadic:
        names[-1] = "..." + names[-1]
    positional = len(names) - (1 if node.is_variadic else 0)
    first_defaulted = positional - len(node.defaults)
    rendered: list[str] = []
    for index, name in enumerate(names):
        if first_defaulted <= index < positional:
            value = node.defaults[index - first_defaulted]
            rendered.append(f"{name} = {_literal_text(value)}")
        else:
            rendered.append(name)
    return ", ".join(rendered)


def _function(node: s.FunctionStmt, depth: int, keyword: str) -> str:
    pad = _INDENT * depth
    parameters = _parameters(node)
    head = f"{pad}{keyword}{node.name.lexeme}({parameters})"
    return head + " " + _block(node.body, depth).lstrip()


def _class(node: s.ClassStmt, depth: int) -> str:
    pad = _INDENT * depth
    head = f"{pad}class {node.name.lexeme}"
    if node.superclass is not None:
        head += f" < {node.superclass.lexeme}"
    if not node.methods:
        return head + " { }"
    lines = [head + " {"]
    for method in node.methods:
        lines.append(_function(method, depth + 1, keyword=""))
    lines.append(pad + "}")
    return chr(10).join(lines)


def _match(node: s.MatchStmt, depth: int) -> str:
    pad = _INDENT * depth
    inner = _INDENT * (depth + 1)
    lines = [f"{pad}match ({expression(node.subject)}) {{"]
    for arm in node.cases:
        values = ", ".join(expression(value) for value in arm.values)
        lines.append(f"{inner}case {values}:")
        lines.extend(_arm_lines(arm.body, depth + 2))
    if node.default is not None:
        lines.append(f"{inner}default:")
        lines.extend(_arm_lines(node.default, depth + 2))
    lines.append(pad + "}")
    return chr(10).join(lines)


def _arm_lines(body: s.Stmt, depth: int) -> list[str]:
    statements = body.statements if isinstance(body, s.Block) else (body,)
    return [statement(inner, depth) for inner in statements]


def _try(node: s.TryStmt, depth: int) -> str:
    pad = _INDENT * depth
    body = node.body.statements if isinstance(node.body, s.Block) else (node.body,)
    handler = node.handler.statements if isinstance(node.handler, s.Block) else (node.handler,)
    text = f"{pad}try " + _block(body, depth).lstrip()
    text += f" catch ({node.catch_name.lexeme}) " + _block(handler, depth).lstrip()
    return text


def format_program(statements: list[s.Stmt]) -> str:
    return chr(10).join(statement(node) for node in statements) + chr(10)
