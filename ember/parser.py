"""The parser: fold a flat token stream into the nested tree the compiler walks.

The parser turns the scanner's flat list into a tree whose shape records
grouping and precedence. It uses two techniques suited to two problems.
Statements are parsed by recursive descent, one method per statement
form, because statements are recognized by their leading keyword and
that maps naturally onto a method that switches on the first token.
Expressions are parsed by precedence climbing, a compact form of Pratt
parsing, because an expression's structure is governed by how tightly
its operators bind, and precedence climbing reads the precedence ladder
directly: parse an operand, then keep absorbing operators that bind at
least as tightly as the current level, recursing one level higher for
the right operand so that left-associative operators group to the left.
Postfix forms, a call, an index, a field access, are handled in their own
tight loop after a primary is parsed, since they bind tighter than any
binary operator and chain naturally. Assignment is parsed as a special
low-precedence right-associative form whose left side must be a valid
target; an earlier version accepted only a bare variable there and that
restriction is worth recording, because lifting it turned out to be a
matter of recognising which node the target parsed into, a variable, an
index, or a property, and rewriting it into the matching assignment node
rather than of changing how assignment is parsed at all. The parser also
carries the language's context rules that have nothing to do with
grammar: whether it sits inside a method, an initializer, a subclass, or a
loop, which is what lets this, super, break, and continue be refused where
they would be meaningless. Putting those checks here rather than in either
backend is deliberate, since both then reject the same programs at the
same stage. On the first error the parser raises rather than attempting
recovery; a parser built for an editor would synchronize to the next
statement boundary and collect many errors, and that machinery is
deliberately omitted in favour of control flow that is easy to follow.
"""

from __future__ import annotations

from ember import exprnodes as e
from ember import stmtnodes as s
from ember.errors import Syntax
from ember.precedence import Precedence, infix_precedence
from ember.token import Token
from ember.tokenkind import TokenKind

_MAX_ARGUMENTS = 255
_INITIALIZER = "init"

_COMPOUND_OPS = {
    TokenKind.PLUS_EQUAL: TokenKind.PLUS,
    TokenKind.MINUS_EQUAL: TokenKind.MINUS,
    TokenKind.STAR_EQUAL: TokenKind.STAR,
    TokenKind.SLASH_EQUAL: TokenKind.SLASH,
    TokenKind.PERCENT_EQUAL: TokenKind.PERCENT,
}


class Parser:
    def __init__(self, tokens: list[Token]) -> None:
        self._tokens = tokens
        self._current = 0
        self._in_initializer = False
        self._in_method = False
        self._in_subclass = False
        self._loop_depth = 0

    def parse(self) -> list[s.Stmt]:
        statements: list[s.Stmt] = []
        while not self._at_end():
            statements.append(self._declaration())
        return statements

    def _peek(self) -> Token:
        return self._tokens[self._current]

    def _previous(self) -> Token:
        return self._tokens[self._current - 1]

    def _peek_next(self) -> Token:
        following = self._current + 1
        if following >= len(self._tokens):
            return self._tokens[-1]
        return self._tokens[following]

    def _at_end(self) -> bool:
        return self._peek().kind == TokenKind.EOF

    def _check(self, kind: TokenKind) -> bool:
        return not self._at_end() and self._peek().kind == kind

    def _advance(self) -> Token:
        if not self._at_end():
            self._current += 1
        return self._previous()

    def _match(self, *kinds: TokenKind) -> bool:
        for kind in kinds:
            if self._check(kind):
                self._advance()
                return True
        return False

    def _consume(self, kind: TokenKind, message: str) -> Token:
        if self._check(kind):
            return self._advance()
        found = self._peek()
        at_end = found.kind == TokenKind.EOF
        where = "at end of input" if at_end else f"at {found.lexeme!r}"
        raise Syntax(
            f"{message}, but found {found.kind.name} {where} on line {found.line}",
            at_end=at_end,
        )

    def _declaration(self) -> s.Stmt:
        if self._match(TokenKind.LET):
            return self._let_declaration(is_const=False)
        if self._match(TokenKind.CONST):
            return self._let_declaration(is_const=True)
        if self._match(TokenKind.FN):
            return self._function_declaration()
        if self._match(TokenKind.CLASS):
            return self._class_declaration()
        return self._statement()

    def _class_declaration(self) -> s.Stmt:
        name = self._consume(TokenKind.IDENTIFIER, "a class needs a name")
        superclass: Token | None = None
        if self._match(TokenKind.LESS):
            superclass = self._consume(
                TokenKind.IDENTIFIER, "a superclass must be named after '<'"
            )
            if superclass.lexeme == name.lexeme:
                raise Syntax(
                    f"the class {name.lexeme!r} on line {name.line} cannot inherit "
                    "from itself"
                )
        self._consume(TokenKind.LEFT_BRACE, "a class body must start with '{'")
        methods: list[s.FunctionStmt] = []
        was_in_subclass = self._in_subclass
        self._in_subclass = superclass is not None
        try:
            while not self._check(TokenKind.RIGHT_BRACE) and not self._at_end():
                methods.append(self._method())
        finally:
            self._in_subclass = was_in_subclass
        self._consume(TokenKind.RIGHT_BRACE, "a class body must be closed with '}'")
        return s.ClassStmt(name, superclass, tuple(methods))

    def _method(self) -> s.FunctionStmt:
        # a method is written without the fn keyword, since inside a class body
        # there is nothing else a name followed by a parameter list could be
        name = self._consume(TokenKind.IDENTIFIER, "a method needs a name")
        self._consume(TokenKind.LEFT_PAREN, "a method name must be followed by '('")
        parameters: list[Token] = []
        if not self._check(TokenKind.RIGHT_PAREN):
            while True:
                if len(parameters) >= _MAX_ARGUMENTS:
                    raise Syntax(
                        f"a method cannot declare more than {_MAX_ARGUMENTS} parameters"
                    )
                parameters.append(
                    self._consume(TokenKind.IDENTIFIER, "a parameter must be a name")
                )
                if not self._match(TokenKind.COMMA):
                    break
        self._consume(TokenKind.RIGHT_PAREN, "a parameter list must end with ')'")
        self._consume(TokenKind.LEFT_BRACE, "a method body must start with '{'")
        # the initializer rule is enforced here, before either backend runs, so
        # both refuse the same programs rather than one catching it later
        was_initializer = self._in_initializer
        was_in_method = self._in_method
        self._in_initializer = name.lexeme == _INITIALIZER
        # a nested fn inside a method is still lexically inside it, so this flag
        # is deliberately not cleared by an inner function declaration
        self._in_method = True
        try:
            body = self._block()
        finally:
            self._in_initializer = was_initializer
            self._in_method = was_in_method
        return s.FunctionStmt(name, tuple(parameters), tuple(body))

    def _let_declaration(self, is_const: bool) -> s.Stmt:
        keyword = "const" if is_const else "let"
        name = self._consume(TokenKind.IDENTIFIER, f"a {keyword} needs a name")
        initializer: e.Expr | None = None
        if self._match(TokenKind.EQUAL):
            initializer = self._expression()
        elif is_const:
            raise Syntax(
                f"the constant {name.lexeme!r} must be given a value where it "
                "is declared, since a constant cannot be assigned later"
            )
        self._consume(TokenKind.SEMICOLON, "a declaration must end with ';'")
        return s.LetStmt(name, initializer, is_const)

    def _function_declaration(self) -> s.Stmt:
        name = self._consume(TokenKind.IDENTIFIER, "a function needs a name")
        self._consume(TokenKind.LEFT_PAREN, "a function name must be followed by '('")
        parameters: list[Token] = []
        if not self._check(TokenKind.RIGHT_PAREN):
            while True:
                if len(parameters) >= _MAX_ARGUMENTS:
                    raise Syntax(
                        f"a function cannot declare more than {_MAX_ARGUMENTS} "
                        "parameters"
                    )
                parameters.append(
                    self._consume(TokenKind.IDENTIFIER, "a parameter must be a name")
                )
                if not self._match(TokenKind.COMMA):
                    break
        self._consume(TokenKind.RIGHT_PAREN, "a parameter list must end with ')'")
        self._consume(TokenKind.LEFT_BRACE, "a function body must start with '{'")
        outer_loops = self._loop_depth
        self._loop_depth = 0
        try:
            body = self._block()
        finally:
            self._loop_depth = outer_loops
        return s.FunctionStmt(name, tuple(parameters), tuple(body))

    def _statement(self) -> s.Stmt:
        if self._match(TokenKind.PRINT):
            return self._print_statement()
        if self._match(TokenKind.LEFT_BRACE):
            return s.Block(tuple(self._block()))
        if self._match(TokenKind.IF):
            return self._if_statement()
        if self._match(TokenKind.WHILE):
            return self._while_statement()
        if self._match(TokenKind.FOR):
            return self._for_statement()
        if self._match(TokenKind.RETURN):
            return self._return_statement()
        if self._match(TokenKind.TRY):
            return self._try_statement()
        if self._match(TokenKind.THROW):
            return self._throw_statement()
        if self._match(TokenKind.BREAK):
            return self._loop_jump(s.BreakStmt, "break")
        if self._match(TokenKind.CONTINUE):
            return self._loop_jump(s.ContinueStmt, "continue")
        return self._expression_statement()

    def _try_statement(self) -> s.Stmt:
        keyword = self._previous()
        self._consume(TokenKind.LEFT_BRACE, "a try needs a block")
        body = s.Block(tuple(self._block()))
        self._consume(TokenKind.CATCH, "a try must be followed by catch")
        self._consume(TokenKind.LEFT_PAREN, "a catch names its value in parentheses")
        name = self._consume(TokenKind.IDENTIFIER, "a catch needs a name for the value")
        self._consume(TokenKind.RIGHT_PAREN, "a catch name must be closed with ')'")
        self._consume(TokenKind.LEFT_BRACE, "a catch needs a block")
        handler = s.Block(tuple(self._block()))
        return s.TryStmt(keyword, body, name, handler)

    def _throw_statement(self) -> s.Stmt:
        keyword = self._previous()
        value = self._expression()
        self._consume(TokenKind.SEMICOLON, "a throw must end with ';'")
        return s.ThrowStmt(keyword, value)

    def _loop_jump(self, node_type, word: str) -> s.Stmt:
        keyword = self._previous()
        if self._loop_depth == 0:
            raise Syntax(
                f"'{word}' on line {keyword.line} is outside any loop, so there "
                "is no loop for it to act on"
            )
        self._consume(TokenKind.SEMICOLON, f"a {word} must end with ';'")
        return node_type(keyword)

    def _loop_body(self) -> s.Stmt:
        # a function declared inside a loop is a new frame, so break there would
        # be meaningless; the depth is saved and cleared around a function body
        self._loop_depth += 1
        try:
            return self._statement()
        finally:
            self._loop_depth -= 1

    def _print_statement(self) -> s.Stmt:
        keyword = self._previous()
        value = self._expression()
        self._consume(TokenKind.SEMICOLON, "a print must end with ';'")
        return s.PrintStmt(keyword, value)

    def _block(self) -> list[s.Stmt]:
        statements: list[s.Stmt] = []
        while not self._check(TokenKind.RIGHT_BRACE) and not self._at_end():
            statements.append(self._declaration())
        self._consume(TokenKind.RIGHT_BRACE, "a block must be closed with '}'")
        return statements

    def _if_statement(self) -> s.Stmt:
        self._consume(TokenKind.LEFT_PAREN, "an if condition must start with '('")
        condition = self._expression()
        self._consume(TokenKind.RIGHT_PAREN, "an if condition must end with ')'")
        then_branch = self._statement()
        else_branch = self._statement() if self._match(TokenKind.ELSE) else None
        return s.IfStmt(condition, then_branch, else_branch)

    def _while_statement(self) -> s.Stmt:
        self._consume(TokenKind.LEFT_PAREN, "a while condition must start with '('")
        condition = self._expression()
        self._consume(TokenKind.RIGHT_PAREN, "a while condition must end with ')'")
        body = self._loop_body()
        return s.WhileStmt(condition, body)

    def _for_statement(self) -> s.Stmt:
        self._consume(TokenKind.LEFT_PAREN, "a for clause must start with '('")
        # one token of lookahead separates the two loop forms: a name followed
        # by `in` is iteration, anything else is the three-clause counting loop
        if self._check(TokenKind.IDENTIFIER) and self._peek_next().kind == TokenKind.IN:
            return self._for_each_statement()
        if self._match(TokenKind.SEMICOLON):
            initializer: s.Stmt | None = None
        elif self._match(TokenKind.LET):
            initializer = self._let_declaration(is_const=False)
        else:
            initializer = self._expression_statement()
        condition = None if self._check(TokenKind.SEMICOLON) else self._expression()
        self._consume(TokenKind.SEMICOLON, "a for condition must be followed by ';'")
        increment = None if self._check(TokenKind.RIGHT_PAREN) else self._expression()
        self._consume(TokenKind.RIGHT_PAREN, "a for clause must end with ')'")
        body = self._loop_body()
        return s.ForStmt(initializer, condition, increment, body)

    def _for_each_statement(self) -> s.Stmt:
        variable = self._consume(TokenKind.IDENTIFIER, "an iteration needs a name")
        self._consume(TokenKind.IN, "an iteration name must be followed by 'in'")
        iterable = self._expression()
        self._consume(TokenKind.RIGHT_PAREN, "a for clause must end with ')'")
        body = self._loop_body()
        return s.ForEachStmt(variable, iterable, body)

    def _return_statement(self) -> s.Stmt:
        keyword = self._previous()
        value = None if self._check(TokenKind.SEMICOLON) else self._expression()
        if value is not None and self._in_initializer:
            raise Syntax(
                f"the initializer on line {keyword.line} cannot return a value, "
                "since calling a class must yield the new instance"
            )
        self._consume(TokenKind.SEMICOLON, "a return must end with ';'")
        return s.ReturnStmt(keyword, value)

    def _expression_statement(self) -> s.Stmt:
        value = self._expression()
        self._consume(TokenKind.SEMICOLON, "an expression statement must end with ';'")
        return s.ExpressionStmt(value)

    def _expression(self) -> e.Expr:
        target = self._conditional()
        if self._match(TokenKind.EQUAL):
            return self._finish_assignment(target, self._previous())
        if self._peek().kind in _COMPOUND_OPS:
            operator = self._advance()
            return self._finish_compound(target, operator)
        return target

    def _conditional(self) -> e.Expr:
        condition = self._binary(Precedence.OR)
        if not self._match(TokenKind.QUESTION):
            return condition
        question = self._previous()
        when_true = self._expression()
        self._consume(TokenKind.COLON, "a conditional needs ':' between its arms")
        # the false arm recurses into the conditional level, so a chain of them
        # groups to the right, which is what makes an else-if chain read correctly
        when_false = self._conditional()
        return e.Conditional(condition, question, when_true, when_false)

    def _finish_assignment(self, target: e.Expr, equals: Token) -> e.Expr:
        value = self._expression()
        if isinstance(target, e.Variable):
            return e.Assign(target.name, value)
        if isinstance(target, e.Index):
            return e.SetIndex(target.collection, target.bracket, target.key, value)
        if isinstance(target, e.Get):
            return e.Set(target.target, target.name, value)
        raise Syntax(
            "the left side of '=' is not something that can be assigned to; only a "
            f"variable, an index, or a property is a valid target on line {equals.line}"
        )

    def _finish_compound(self, target: e.Expr, operator: Token) -> e.Expr:
        # x += e becomes x = x + e; note this re-evaluates the target, so a
        # target with side effects like a[f()] += 1 calls f twice, which a
        # dup-based compiler would avoid at the cost of more machinery
        right = self._expression()
        binary_kind = _COMPOUND_OPS[operator.kind]
        binary_token = Token(binary_kind, operator.lexeme[:-1], operator.span)
        if isinstance(target, e.Variable):
            combined = e.Binary(e.Variable(target.name), binary_token, right)
            return e.Assign(target.name, combined)
        if isinstance(target, e.Index):
            getter = e.Index(target.collection, target.bracket, target.key)
            combined = e.Binary(getter, binary_token, right)
            return e.SetIndex(target.collection, target.bracket, target.key, combined)
        if isinstance(target, e.Get):
            combined = e.Binary(e.Get(target.target, target.name), binary_token, right)
            return e.Set(target.target, target.name, combined)
        raise Syntax(
            "the left side of a compound assignment is not assignable; only a "
            f"variable or an index qualifies, on line {operator.line}"
        )

    def _binary(self, min_precedence: Precedence) -> e.Expr:
        left = self._unary()
        while True:
            kind = self._peek().kind
            precedence = infix_precedence(kind)
            if precedence < min_precedence or precedence > Precedence.FACTOR:
                break
            operator = self._advance()
            right = self._binary(Precedence(precedence + 1))
            if kind in (TokenKind.AND, TokenKind.OR):
                left = e.Logical(left, operator, right)
            else:
                left = e.Binary(left, operator, right)
        return left

    def _unary(self) -> e.Expr:
        if self._match(TokenKind.BANG, TokenKind.MINUS, TokenKind.NOT, TokenKind.TILDE):
            operator = self._previous()
            operand = self._unary()
            return e.Unary(operator, operand)
        return self._call()

    def _call(self) -> e.Expr:
        expr = self._primary()
        while True:
            if self._match(TokenKind.LEFT_PAREN):
                expr = self._finish_call(expr)
            elif self._match(TokenKind.LEFT_BRACKET):
                bracket = self._previous()
                key = self._expression()
                self._consume(TokenKind.RIGHT_BRACKET, "an index must end with ']'")
                expr = e.Index(expr, bracket, key)
            elif self._match(TokenKind.DOT):
                name = self._consume(
                    TokenKind.IDENTIFIER, "a '.' must be followed by a property name"
                )
                expr = e.Get(expr, name)
            else:
                break
        return expr

    def _finish_call(self, callee: e.Expr) -> e.Expr:
        paren = self._previous()
        arguments: list[e.Expr] = []
        if not self._check(TokenKind.RIGHT_PAREN):
            while True:
                if len(arguments) >= _MAX_ARGUMENTS:
                    raise Syntax(
                        f"a call cannot pass more than {_MAX_ARGUMENTS} arguments"
                    )
                arguments.append(self._expression())
                if not self._match(TokenKind.COMMA):
                    break
        self._consume(TokenKind.RIGHT_PAREN, "a call's arguments must end with ')'")
        return e.Call(callee, paren, tuple(arguments))

    def _primary(self) -> e.Expr:
        if self._match(TokenKind.NUMBER, TokenKind.STRING):
            token = self._previous()
            return e.Literal(token.literal, token)
        if self._match(TokenKind.TRUE):
            return e.Literal(True, self._previous())
        if self._match(TokenKind.FALSE):
            return e.Literal(False, self._previous())
        if self._match(TokenKind.NIL):
            return e.Literal(None, self._previous())
        if self._match(TokenKind.SUPER):
            keyword = self._previous()
            if not self._in_method:
                raise Syntax(
                    f"'super' on line {keyword.line} is outside any method"
                )
            if not self._in_subclass:
                raise Syntax(
                    f"'super' on line {keyword.line} is inside a class with no "
                    "superclass, so there is nothing above it to reach"
                )
            self._consume(TokenKind.DOT, "'super' must be followed by '.'")
            method = self._consume(
                TokenKind.IDENTIFIER, "'super.' must name a method"
            )
            return e.Super(keyword, method)
        if self._match(TokenKind.THIS):
            keyword = self._previous()
            if not self._in_method:
                raise Syntax(
                    f"'this' on line {keyword.line} is outside any method, so "
                    "there is no instance for it to name"
                )
            return e.This(keyword)
        if self._match(TokenKind.IDENTIFIER):
            return e.Variable(self._previous())
        if self._match(TokenKind.LEFT_PAREN):
            inner = self._expression()
            self._consume(TokenKind.RIGHT_PAREN, "a group must be closed with ')'")
            return e.Grouping(inner)
        if self._match(TokenKind.LEFT_BRACKET):
            return self._list_literal()
        if self._match(TokenKind.LEFT_BRACE):
            return self._map_literal()
        found = self._peek()
        at_end = found.kind == TokenKind.EOF
        where = "at end of input" if at_end else f"{found.lexeme!r}"
        raise Syntax(
            f"expected an expression but found {found.kind.name} {where} "
            f"on line {found.line}",
            at_end=at_end,
        )

    def _list_literal(self) -> e.Expr:
        bracket = self._previous()
        elements: list[e.Expr] = []
        if not self._check(TokenKind.RIGHT_BRACKET):
            while True:
                elements.append(self._expression())
                if not self._match(TokenKind.COMMA):
                    break
        self._consume(TokenKind.RIGHT_BRACKET, "a list must be closed with ']'")
        return e.ListLiteral(bracket, tuple(elements))

    def _map_literal(self) -> e.Expr:
        brace = self._previous()
        pairs: list[tuple[e.Expr, e.Expr]] = []
        if not self._check(TokenKind.RIGHT_BRACE):
            while True:
                key = self._expression()
                self._consume(TokenKind.COLON, "a map entry needs ':' between key and value")
                value = self._expression()
                pairs.append((key, value))
                if not self._match(TokenKind.COMMA):
                    break
        self._consume(TokenKind.RIGHT_BRACE, "a map must be closed with '}'")
        return e.MapLiteral(brace, tuple(pairs))


def parse(tokens: list[Token]) -> list[s.Stmt]:
    return Parser(tokens).parse()
