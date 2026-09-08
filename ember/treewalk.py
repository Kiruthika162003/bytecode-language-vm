"""The tree-walking interpreter: run a program by evaluating its syntax tree directly.

This is the runtime's second backend, and it exists to be the simple one.
Instead of compiling the tree to bytecode and running a separate machine,
it walks the tree and computes each node's meaning on the spot: a literal
evaluates to its value, a binary node evaluates its two sides and
combines them, an if statement evaluates its condition and then walks one
branch. Statements that bind names write into an environment chain, and a
function closes over the environment it was defined in, so closures cost
this backend nothing at all: the captured chain is simply kept alive by
the reference. That was once a capability the bytecode backend lacked, and
it is worth recording that the comparison has since changed, because the
other backend now captures the same variables through upvalues and an
explicit closing step, several hundred lines of machinery to reach the
behaviour this one gets from a pointer. A return is implemented by raising
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
from ember.classes import INITIALIZER
from ember.environment import Environment
from ember.errors import (
    Arithmetic,
    Arity,
    EmberError,
    IndexRange,
    Resolve,
    StackFault,
    Thrown,
    TypeMismatch,
    Unbound,
)
from ember.function import NativeFunction
from ember.interpolation import TEXT as _TEXT
from ember.tokenkind import TokenKind
from ember.valueops import (
    is_truthy,
    iteration_source,
    stringify,
    type_name,
    values_equal,
)


class _Return(Exception):
    def __init__(self, value: Any) -> None:
        super().__init__()
        self.value = value


class _Thrown(Exception):
    """Carries a thrown value up to the nearest enclosing try."""

    def __init__(self, value: Any) -> None:
        super().__init__()
        self.value = value


class _Break(Exception):
    """Raised to unwind out of a loop body, caught by the loop that owns it."""


class _Continue(Exception):
    """Raised to abandon one iteration, caught by the loop that owns it."""


class TreeFunction:
    def __init__(self, declaration: s.FunctionStmt, closure: Environment) -> None:
        self.declaration = declaration
        self.closure = closure

    @property
    def arity(self) -> int:
        return len(self.declaration.parameters)

    @property
    def defaults(self) -> tuple[object, ...]:
        return self.declaration.defaults

    @property
    def is_variadic(self) -> bool:
        return self.declaration.is_variadic

    @property
    def named(self) -> int:
        return self.arity - (1 if self.is_variadic else 0)

    @property
    def required(self) -> int:
        return self.named - len(self.defaults)

    def accepts(self, count: int) -> bool:
        if count < self.required:
            return False
        return self.is_variadic or count <= self.named

    def describe_arity(self) -> str:
        if self.is_variadic:
            return f"at least {self.required}"
        if self.defaults:
            return f"between {self.required} and {self.named}"
        return str(self.required)

    @property
    def name(self) -> str:
        return self.declaration.name.lexeme

    @property
    def is_initializer(self) -> bool:
        return self.name == INITIALIZER

    def bind(self, receiver: TreeInstance) -> TreeFunction:
        # binding a method is just closing it over an environment in which
        # `this` names the receiver, so no separate bound-method type is needed
        bound = Environment(self.closure)
        bound.define("this", receiver)
        return TreeFunction(self.declaration, bound)

    def __repr__(self) -> str:
        return f"<fn {self.name}>"


class TreeClass:
    def __init__(self, name: str) -> None:
        self.name = name
        self.methods: dict[str, TreeFunction] = {}

    def find_method(self, name: str) -> TreeFunction | None:
        return self.methods.get(name)

    @property
    def initializer(self) -> TreeFunction | None:
        return self.methods.get(INITIALIZER)

    @property
    def arity(self) -> int:
        initializer = self.initializer
        return initializer.arity if initializer is not None else 0

    def accepts(self, count: int) -> bool:
        initializer = self.initializer
        if initializer is None:
            return count == 0
        return initializer.accepts(count)

    def describe_arity(self) -> str:
        initializer = self.initializer
        return initializer.describe_arity() if initializer is not None else "0"

    def __repr__(self) -> str:
        return f"<class {self.name}>"


class TreeInstance:
    def __init__(self, klass: TreeClass) -> None:
        self.klass = klass
        self.fields: dict[str, Any] = {}

    def __repr__(self) -> str:
        return f"<{self.klass.name} instance>"


_SUPER = "super"

_BITWISE = (
    TokenKind.AMPERSAND,
    TokenKind.PIPE,
    TokenKind.CARET,
    TokenKind.LESS_LESS,
    TokenKind.GREATER_GREATER,
)

_COMPARISONS = (
    TokenKind.LESS,
    TokenKind.LESS_EQUAL,
    TokenKind.GREATER,
    TokenKind.GREATER_EQUAL,
)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _whole(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeMismatch(
            f"bitwise operations need integers, not a {type_name(value)}"
        )
    return value


class TreeWalker:
    def __init__(self) -> None:
        self.globals = Environment()
        self.output: list[str] = []
        self.steps = 0

    def define_native(
        self, name: str, arity: int, handler: Any, needs_machine: bool = False
    ) -> None:
        self.globals.define(name, NativeFunction(name, arity, handler, needs_machine))

    def call_value(self, callee: Any, arguments: list[Any]) -> Any:
        """Call an Ember function from host code, the counterpart of the machine's.

        The tree-walker needs no re-entrancy machinery for this: evaluating a
        call is already an ordinary recursive descent through Python's own
        stack, so invoking a function from a native is the same operation the
        interpreter performs everywhere else.
        """
        if isinstance(callee, TreeFunction):
            return self._invoke(callee, arguments)
        if isinstance(callee, TreeClass):
            instance = TreeInstance(callee)
            initializer = callee.initializer
            if initializer is None:
                if arguments:
                    raise Arity(
                        f"the class {callee.name!r} has no initializer, so it "
                        f"takes no arguments but received {len(arguments)}"
                    )
                return instance
            self._invoke(initializer.bind(instance), arguments)
            return instance
        if isinstance(callee, NativeFunction):
            if len(arguments) != callee.arity:
                raise Arity(
                    f"the native function {callee.name!r} expects {callee.arity} "
                    f"arguments but received {len(arguments)}"
                )
            if callee.needs_machine:
                return callee.handler(self, arguments)
            return callee.handler(arguments)
        raise TypeMismatch(f"a {type_name(callee)} is not callable")

    def run(self, statements: list[s.Stmt]) -> None:
        try:
            for statement in statements:
                self._execute(statement, self.globals)
        except _Thrown as signal:
            raise Thrown(signal.value, stringify(signal.value)) from None

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
                try:
                    self._execute(node.body, env)
                except _Break:
                    break
                except _Continue:
                    continue
        elif isinstance(node, s.ForStmt):
            self._for(node, env)
        elif isinstance(node, s.ForEachStmt):
            self._for_each(node, env)
        elif isinstance(node, s.FunctionStmt):
            env.define(node.name.lexeme, TreeFunction(node, env))
        elif isinstance(node, s.ClassStmt):
            self._class(node, env)
        elif isinstance(node, s.ReturnStmt):
            value = self._evaluate(node.value, env) if node.value else None
            raise _Return(value)
        elif isinstance(node, s.MatchStmt):
            self._match(node, env)
        elif isinstance(node, s.TryStmt):
            self._try(node, env)
        elif isinstance(node, s.ThrowStmt):
            raise _Thrown(self._evaluate(node.value, env))
        elif isinstance(node, s.BreakStmt):
            raise _Break
        elif isinstance(node, s.ContinueStmt):
            raise _Continue
        else:
            raise TypeMismatch(f"the tree-walker cannot execute {type(node).__name__}")

    def _match(self, node: s.MatchStmt, env: Environment) -> None:
        subject = self._evaluate(node.subject, env)
        for arm in node.cases:
            for value in arm.values:
                if values_equal(subject, self._evaluate(value, env)):
                    self._execute(arm.body, Environment(env))
                    return
        if node.default is not None:
            self._execute(node.default, Environment(env))

    def _try(self, node: s.TryStmt, env: Environment) -> None:
        try:
            self._execute(node.body, env)
        except _Thrown as signal:
            caught = signal.value
        except (StackFault, Thrown):
            raise
        except EmberError as error:
            # a runtime fault becomes its message, matching the compiled backend
            caught = str(error)
        else:
            return
        handler_env = Environment(env)
        handler_env.define(node.catch_name.lexeme, caught)
        self._execute(node.handler, handler_env)

    def _class(self, node: s.ClassStmt, env: Environment) -> None:
        klass = TreeClass(node.name.lexeme)
        method_env = env
        if node.superclass is not None:
            superclass = env.get(node.superclass.lexeme)
            if not isinstance(superclass, TreeClass):
                raise TypeMismatch(
                    f"a class can only inherit from a class, and this is a "
                    f"{type_name(superclass)}"
                )
            # inherited methods are copied in first so an override below simply
            # replaces the entry, matching how the bytecode backend flattens
            klass.methods.update(superclass.methods)
            # methods see the superclass through an environment binding, which is
            # what lets super keep working after the declaration has finished
            method_env = Environment(env)
            method_env.define(_SUPER, superclass)
        seen: set[str] = set()
        for method in node.methods:
            if method.name.lexeme in seen:
                raise Resolve(
                    f"the class {node.name.lexeme!r} declares the method "
                    f"{method.name.lexeme!r} twice; remove one of them"
                )
            seen.add(method.name.lexeme)
            klass.methods[method.name.lexeme] = TreeFunction(method, method_env)
        env.define(node.name.lexeme, klass)

    def _execute_block(self, statements: tuple[s.Stmt, ...], env: Environment) -> None:
        for statement in statements:
            self._execute(statement, env)

    def _for(self, node: s.ForStmt, env: Environment) -> None:
        loop_env = Environment(env)
        if node.initializer is not None:
            self._execute(node.initializer, loop_env)
        while node.condition is None or is_truthy(self._evaluate(node.condition, loop_env)):
            try:
                self._execute(node.body, loop_env)
            except _Break:
                break
            except _Continue:
                # the increment still runs, matching the compiled form where
                # continue targets the step rather than the condition
                pass
            if node.increment is not None:
                self._evaluate(node.increment, loop_env)

    def _for_each(self, node: s.ForEachStmt, env: Environment) -> None:
        source = iteration_source(self._evaluate(node.iterable, env))
        for item in source:
            # a fresh scope per iteration, so a closure made inside the body
            # captures that iteration's value rather than the last one
            iteration_env = Environment(env)
            iteration_env.define(node.variable.lexeme, item)
            try:
                self._execute(node.body, iteration_env)
            except _Break:
                break
            except _Continue:
                continue

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
        if isinstance(node, e.Interpolation):
            pieces: list[str] = []
            for kind, value in node.parts:
                if kind == _TEXT:
                    pieces.append(value)
                else:
                    pieces.append(stringify(self._evaluate(value, env)))
            return "".join(pieces)
        if isinstance(node, e.Conditional):
            if is_truthy(self._evaluate(node.condition, env)):
                return self._evaluate(node.when_true, env)
            return self._evaluate(node.when_false, env)
        if isinstance(node, e.Call):
            return self._call(node, env)
        if isinstance(node, e.Index):
            return self._index(node, env)
        if isinstance(node, e.SetIndex):
            return self._set_index(node, env)
        if isinstance(node, e.Get):
            return self._get_property(node, env)
        if isinstance(node, e.Set):
            return self._set_property(node, env)
        if isinstance(node, e.This):
            return env.get("this")
        if isinstance(node, e.Super):
            return self._super(node, env)
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
        if node.operator.kind == TokenKind.TILDE:
            return ~_whole(value)
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
        if kind in _BITWISE:
            return self._bitwise(kind, left, right)
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

    def _bitwise(self, kind: TokenKind, left: Any, right: Any) -> int:
        a = _whole(left)
        b = _whole(right)
        if kind == TokenKind.AMPERSAND:
            return a & b
        if kind == TokenKind.PIPE:
            return a | b
        if kind == TokenKind.CARET:
            return a ^ b
        if b < 0:
            raise Arithmetic(
                f"cannot shift by the negative amount {b}; shift the other way"
            )
        if kind == TokenKind.LESS_LESS:
            return a << b
        return a >> b

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
        if isinstance(callee, TreeClass):
            instance = TreeInstance(callee)
            initializer = callee.initializer
            if initializer is None:
                if arguments:
                    raise Arity(
                        f"the class {callee.name!r} has no initializer, so it "
                        f"takes no arguments but received {len(arguments)}"
                    )
                return instance
            self._invoke(initializer.bind(instance), arguments)
            return instance
        if isinstance(callee, TreeFunction):
            return self._invoke(callee, arguments)
        if isinstance(callee, NativeFunction):
            if len(arguments) != callee.arity:
                raise Arity(
                    f"the native function {callee.name!r} expects {callee.arity} "
                    f"arguments but received {len(arguments)}"
                )
            if callee.needs_machine:
                return callee.handler(self, arguments)
            return callee.handler(arguments)
        raise TypeMismatch(f"a {type_name(callee)} is not callable")

    def _invoke(self, callee: TreeFunction, arguments: list[Any]) -> Any:
        if not callee.accepts(len(arguments)):
            raise Arity(
                f"the function {callee.name!r} expects "
                f"{callee.describe_arity()} arguments but received {len(arguments)}"
            )
        settled = self._settle(callee, arguments)
        call_env = Environment(callee.closure)
        pairs = zip(callee.declaration.parameters, settled, strict=True)
        for parameter, argument in pairs:
            call_env.define(parameter.lexeme, argument)
        try:
            self._execute_block(callee.declaration.body, call_env)
        except _Return as signal:
            if callee.is_initializer:
                return call_env.get("this")
            return signal.value
        if callee.is_initializer:
            return call_env.get("this")
        return None

    def _super(self, node: e.Super, env: Environment) -> Any:
        superclass = env.get(_SUPER)
        receiver = env.get("this")
        method = superclass.find_method(node.method.lexeme)
        if method is None:
            raise Unbound(
                f"the superclass {superclass.name} has no method "
                f"{node.method.lexeme!r} for 'super' to reach"
            )
        return method.bind(receiver)

    def _get_property(self, node: e.Get, env: Environment) -> Any:
        target = self._evaluate(node.target, env)
        if not isinstance(target, TreeInstance):
            raise TypeMismatch(
                f"only an instance has properties, and this is a {type_name(target)}"
            )
        name = node.name.lexeme
        if name in target.fields:
            return target.fields[name]
        method = target.klass.find_method(name)
        if method is None:
            raise Unbound(
                f"the {target.klass.name} instance has no property {name!r}; it "
                "was never assigned as a field nor declared as a method"
            )
        return method.bind(target)

    def _set_property(self, node: e.Set, env: Environment) -> Any:
        target = self._evaluate(node.target, env)
        if not isinstance(target, TreeInstance):
            raise TypeMismatch(
                f"only an instance can take a property, and this is a "
                f"{type_name(target)}"
            )
        value = self._evaluate(node.value, env)
        target.fields[node.name.lexeme] = value
        return value

    def _settle(self, callee: TreeFunction, arguments: list[Any]) -> list[Any]:
        """Fill any missing defaults and gather a rest argument, as the machine does."""
        supplied = list(arguments)
        if callee.is_variadic:
            extra = len(supplied) - callee.named
            if extra > 0:
                gathered = supplied[callee.named :]
                supplied = supplied[: callee.named]
                supplied.append(gathered)
            else:
                missing = callee.named - len(supplied)
                if missing:
                    supplied.extend(callee.defaults[len(callee.defaults) - missing :])
                supplied.append([])
            return supplied
        missing = callee.named - len(supplied)
        if missing:
            supplied.extend(callee.defaults[len(callee.defaults) - missing :])
        return supplied

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
