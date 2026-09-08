"""The tree-walking interpreter: run a program by evaluating its syntax tree directly.

This is the runtime's second backend, and it exists to be the simple one.
Instead of compiling the tree to bytecode and running a separate machine,
it walks the tree and computes each node's meaning on the spot: a literal
evaluates to its value, a binary node evaluates its two sides and
combines them, an if statement evaluates its condition and then walks one
branch. Statements that bind names write into an environment chain, and a
function closes over the environment it was defined in, which is why the
tree-walker supports true lexical closures with no extra machinery where
the current bytecode backend does not. A return is implemented by raising
a small internal signal that the function-call boundary catches, which is
the cleanest way to unwind out of the middle of a nested body. Keeping
this backend means the language has two independent implementations of
the same semantics, and running a program through both and checking they
agree is a strong test that neither has drifted, which is worth far more
than either alone could prove about correctness. The honest tradeoff is
performance: re-walking the tree and looking names up in a chain on every
access is markedly slower than executing flat bytecode with slotted
locals, and on a hot loop the difference is large. That is precisely the
tradeoff the two backends exist to make visible, so this one is written
for clarity and left unoptimized on purpose. It shares the value
semantics and the native builtins with the other backend, so only the
execution strategy differs, not the language.
"""

from __future__ import annotations

from typing import Any

from ember import exprnodes as e
from ember import stmtnodes as s
from ember.environment import Environment
from ember.errors import Arithmetic, Arity, IndexRange, TypeMismatch
from ember.function import NativeFunction
from ember.tokenkind import TokenKind
from ember.valueops import is_truthy, stringify, type_name, values_equal


class _Return(Exception):
    def __init__(self, value: Any) -> None:
        super().__init__()
        self.value = value


class TreeFunction:
    def __init__(self, declaration: s.FunctionStmt, closure: Environment) -> None:
        self.declaration = declaration
        self.closure = closure

    @property
    def arity(self) -> int:
        return len(self.declaration.parameters)

    @property
    def name(self) -> str:
        return self.declaration.name.lexeme

    def __repr__(self) -> str:
        return f"<fn {self.name}>"


_COMPARISONS = (
    TokenKind.LESS,
    TokenKind.LESS_EQUAL,
    TokenKind.GREATER,
    TokenKind.GREATER_EQUAL,
)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


class TreeWalker:
    def __init__(self) -> None:
        self.globals = Environment()
        self.output: list[str] = []
        self.steps = 0

    def define_native(self, name: str, arity: int, handler: Any) -> None:
        self.globals.define(name, NativeFunction(name, arity, handler))

    def run(self, statements: list[s.Stmt]) -> None:
        for statement in statements:
            self._execute(statement, self.globals)

    def _execute(self, node: s.Stmt, env: Environment) -> None:
        self.steps += 1
        if isinstance(node, s.ExpressionStmt):
            self._evaluate(node.expression, env)
        elif isinstance(node, s.PrintStmt):
            self.output.append(stringify(self._evaluate(node.expression, env)))
        elif isinstance(node, s.LetStmt):
            value = self._evaluate(node.initializer, env) if node.initializer else None
            env.define(node.name.lexeme, value, node.is_const)
        elif isinstance(node, s.Block):
            self._execute_block(node.statements, Environment(env))
        elif isinstance(node, s.IfStmt):
            if is_truthy(self._evaluate(node.condition, env)):
                self._execute(node.then_branch, env)
            elif node.else_branch is not None:
                self._execute(node.else_branch, env)
        elif isinstance(node, s.WhileStmt):
            while is_truthy(self._evaluate(node.condition, env)):
                self._execute(node.body, env)
        elif isinstance(node, s.ForStmt):
            self._for(node, env)
        elif isinstance(node, s.FunctionStmt):
            env.define(node.name.lexeme, TreeFunction(node, env))
        elif isinstance(node, s.ReturnStmt):
            value = self._evaluate(node.value, env) if node.value else None
            raise _Return(value)
        else:
            raise TypeMismatch(f"the tree-walker cannot execute {type(node).__name__}")

    def _execute_block(self, statements: tuple[s.Stmt, ...], env: Environment) -> None:
        for statement in statements:
            self._execute(statement, env)

    def _for(self, node: s.ForStmt, env: Environment) -> None:
        loop_env = Environment(env)
        if node.initializer is not None:
            self._execute(node.initializer, loop_env)
        while node.condition is None or is_truthy(self._evaluate(node.condition, loop_env)):
            self._execute(node.body, loop_env)
            if node.increment is not None:
                self._evaluate(node.increment, loop_env)

    def _evaluate(self, node: e.Expr, env: Environment) -> Any:
        self.steps += 1
        if isinstance(node, e.Literal):
            return node.value
        if isinstance(node, e.Variable):
            return env.get(node.name.lexeme)
        if isinstance(node, e.Grouping):
            return self._evaluate(node.inner, env)
        if isinstance(node, e.Assign):
            value = self._evaluate(node.value, env)
            env.assign(node.name.lexeme, value)
            return value
        if isinstance(node, e.Unary):
            return self._unary(node, env)
        if isinstance(node, e.Binary):
            return self._binary(node, env)
        if isinstance(node, e.Logical):
            return self._logical(node, env)
        if isinstance(node, e.Call):
            return self._call(node, env)
        if isinstance(node, e.Index):
            return self._index(node, env)
        if isinstance(node, e.SetIndex):
            return self._set_index(node, env)
        if isinstance(node, e.ListLiteral):
            return [self._evaluate(item, env) for item in node.elements]
        if isinstance(node, e.MapLiteral):
            return self._map(node, env)
        raise TypeMismatch(f"the tree-walker cannot evaluate {type(node).__name__}")

    def _unary(self, node: e.Unary, env: Environment) -> Any:
        value = self._evaluate(node.operand, env)
        if node.operator.kind == TokenKind.MINUS:
            if not _is_number(value):
                raise TypeMismatch(f"cannot negate a {type_name(value)}")
            return -value
        return not is_truthy(value)

    def _binary(self, node: e.Binary, env: Environment) -> Any:
        left = self._evaluate(node.left, env)
        right = self._evaluate(node.right, env)
        kind = node.operator.kind
        if kind == TokenKind.EQUAL_EQUAL:
            return values_equal(left, right)
        if kind == TokenKind.BANG_EQUAL:
            return not values_equal(left, right)
        if kind == TokenKind.PLUS:
            return self._add(left, right)
        if kind in _COMPARISONS:
            return self._compare(kind, left, right)
        return self._numeric(kind, left, right)

    def _add(self, left: Any, right: Any) -> Any:
        if _is_number(left) and _is_number(right):
            return left + right
        if isinstance(left, str) and isinstance(right, str):
            return left + right
        if isinstance(left, list) and isinstance(right, list):
            return left + right
        raise TypeMismatch(
            f"cannot add a {type_name(left)} and a {type_name(right)}"
        )

    def _numeric(self, kind: TokenKind, left: Any, right: Any) -> Any:
        if not (_is_number(left) and _is_number(right)):
            raise TypeMismatch(
                f"arithmetic needs two numbers, not a {type_name(left)} and a "
                f"{type_name(right)}"
            )
        if kind == TokenKind.MINUS:
            return left - right
        if kind == TokenKind.STAR:
            return left * right
        if kind == TokenKind.SLASH:
            if right == 0:
                raise Arithmetic("division by zero has no defined result")
            return left / right
        if right == 0:
            raise Arithmetic("remainder by zero has no defined result")
        return left % right

    def _compare(self, kind: TokenKind, left: Any, right: Any) -> bool:
        ok = (_is_number(left) and _is_number(right)) or (
            isinstance(left, str) and isinstance(right, str)
        )
        if not ok:
            raise TypeMismatch(
                f"cannot compare a {type_name(left)} with a {type_name(right)}"
            )
        if kind == TokenKind.LESS:
            return left < right
        if kind == TokenKind.LESS_EQUAL:
            return left <= right
        if kind == TokenKind.GREATER:
            return left > right
        return left >= right

    def _logical(self, node: e.Logical, env: Environment) -> Any:
        left = self._evaluate(node.left, env)
        if node.operator.kind == TokenKind.OR:
            return left if is_truthy(left) else self._evaluate(node.right, env)
        return self._evaluate(node.right, env) if is_truthy(left) else left

    def _call(self, node: e.Call, env: Environment) -> Any:
        callee = self._evaluate(node.callee, env)
        arguments = [self._evaluate(argument, env) for argument in node.arguments]
        if isinstance(callee, TreeFunction):
            if len(arguments) != callee.arity:
                raise Arity(
                    f"the function {callee.name!r} expects {callee.arity} "
                    f"arguments but received {len(arguments)}"
                )
            call_env = Environment(callee.closure)
            pairs = zip(callee.declaration.parameters, arguments, strict=True)
            for parameter, argument in pairs:
                call_env.define(parameter.lexeme, argument)
            try:
                self._execute_block(callee.declaration.body, call_env)
            except _Return as signal:
                return signal.value
            return None
        if isinstance(callee, NativeFunction):
            if len(arguments) != callee.arity:
                raise Arity(
                    f"the native function {callee.name!r} expects {callee.arity} "
                    f"arguments but received {len(arguments)}"
                )
            return callee.handler(arguments)
        raise TypeMismatch(f"a {type_name(callee)} is not callable")

    def _index(self, node: e.Index, env: Environment) -> Any:
        collection = self._evaluate(node.collection, env)
        key = self._evaluate(node.key, env)
        return _index_read(collection, key)

    def _set_index(self, node: e.SetIndex, env: Environment) -> Any:
        collection = self._evaluate(node.collection, env)
        key = self._evaluate(node.key, env)
        value = self._evaluate(node.value, env)
        _index_write(collection, key, value)
        return value

    def _map(self, node: e.MapLiteral, env: Environment) -> dict[Any, Any]:
        result: dict[Any, Any] = {}
        for key_node, value_node in node.pairs:
            key = self._evaluate(key_node, env)
            if isinstance(key, (list, dict)):
                raise TypeMismatch(f"a {type_name(key)} cannot be a map key")
            result[key] = self._evaluate(value_node, env)
        return result


def _index_read(collection: Any, key: Any) -> Any:
    if isinstance(collection, (list, str)):
        if isinstance(key, bool) or not isinstance(key, int):
            raise TypeMismatch(f"an index must be an integer, not a {type_name(key)}")
        if not -len(collection) <= key < len(collection):
            raise IndexRange(f"the index {key} is outside a length of {len(collection)}")
        return collection[key]
    if isinstance(collection, dict):
        if key not in collection:
            raise IndexRange(f"the key {key!r} is not present in the map")
        return collection[key]
    raise TypeMismatch(f"a {type_name(collection)} cannot be indexed")


def _index_write(collection: Any, key: Any, value: Any) -> None:
    if isinstance(collection, list):
        if isinstance(key, bool) or not isinstance(key, int):
            raise TypeMismatch(f"a list index must be an integer, not a {type_name(key)}")
        if not -len(collection) <= key < len(collection):
            raise IndexRange(f"the index {key} is outside a length of {len(collection)}")
        collection[key] = value
    elif isinstance(collection, dict):
        if isinstance(key, (list, dict)):
            raise TypeMismatch(f"a {type_name(key)} cannot be a map key")
        collection[key] = value
    else:
        raise TypeMismatch(
            f"a {type_name(collection)} cannot be assigned by index"
        )
