"""The compiler: walk the syntax tree once and emit the bytecode that computes it.

The compiler is the bridge between the tree the parser built and the flat
code the machine runs. It walks the tree in a single pass, and for each
node it emits the instructions that leave that node's effect on the value
stack: a literal emits a load, a binary operator emits its two operands
then the operator, an if statement emits the condition then a conditional
jump around the branch it should skip. Two responsibilities make this
more than a transcription. The first is variable binding. A name declared
inside a block is a local, and the compiler assigns it a stack slot and
compiles every use into a direct slot access, while a name at the top
level is a global, resolved by name at run time; the compiler decides
which by the scope depth and emits accordingly. The second is control
flow. The machine only has jumps, so the compiler turns structured
constructs into jumps whose distances it does not know until it has
compiled what they skip, so it emits each jump with a placeholder
distance and patches the real distance once the target is known. The
honest limitation of this version is scope of capture: each function is
compiled with its own independent set of locals, so a nested function can
read globals and its own parameters and locals but cannot close over a
variable of an enclosing function; true closures need captured upvalues,
which this compiler does not emit, and a nested reference to an enclosing
local is therefore treated as a global and will fault at run time if no
such global exists. That boundary is drawn deliberately to keep this pass
and the machine simple, and it is the natural place a later stage extends.
"""

from __future__ import annotations

from ember import exprnodes as e
from ember import stmtnodes as s
from ember.chunk import Chunk
from ember.errors import Compile, Immutable
from ember.function import Function
from ember.localscope import Local, LocalScope
from ember.opcode import OpCode
from ember.token import Token
from ember.tokenkind import TokenKind

_MAX_JUMP = 0xFFFF
_MAX_UPVALUES = 256

_BINARY_OPS = {
    TokenKind.PLUS: OpCode.ADD,
    TokenKind.MINUS: OpCode.SUBTRACT,
    TokenKind.STAR: OpCode.MULTIPLY,
    TokenKind.SLASH: OpCode.DIVIDE,
    TokenKind.PERCENT: OpCode.MODULO,
    TokenKind.EQUAL_EQUAL: OpCode.EQUAL,
    TokenKind.BANG_EQUAL: OpCode.NOT_EQUAL,
    TokenKind.LESS: OpCode.LESS,
    TokenKind.LESS_EQUAL: OpCode.LESS_EQUAL,
    TokenKind.GREATER: OpCode.GREATER,
    TokenKind.GREATER_EQUAL: OpCode.GREATER_EQUAL,
}


class _Upvalue:
    """Where a closure's captured variable comes from in the enclosing unit."""

    __slots__ = ("index", "is_local")

    def __init__(self, index: int, is_local: bool) -> None:
        self.index = index
        self.is_local = is_local


class _FunctionUnit:
    def __init__(self, name: str, arity: int, enclosing: _FunctionUnit | None = None) -> None:
        self.function = Function(name, arity, Chunk())
        self.scope = LocalScope()
        self.enclosing = enclosing
        self.upvalues: list[_Upvalue] = []


class Compiler:
    def __init__(self) -> None:
        self._units: list[_FunctionUnit] = []
        self._const_globals: set[str] = set()

    def compile(self, statements: list[s.Stmt]) -> Function:
        unit = _FunctionUnit("", 0)
        # slot 0 of every frame, the script's included, holds the callee, so
        # reserve it before any local can claim it; the depth stays 0 so
        # top-level declarations are still globals
        unit.scope.declare_reserved()
        self._units.append(unit)
        for statement in statements:
            self._statement(statement)
        self._emit(OpCode.NIL, 1)
        self._emit(OpCode.RETURN, 1)
        self._units.pop()
        return unit.function

    @property
    def _unit(self) -> _FunctionUnit:
        return self._units[-1]

    @property
    def _chunk(self) -> Chunk:
        return self._unit.function.chunk

    @property
    def _scope(self) -> LocalScope:
        return self._unit.scope

    def _emit(self, opcode: OpCode, line: int) -> int:
        return self._chunk.write_op(opcode, line)

    def _emit_byte(self, byte: int, line: int) -> int:
        return self._chunk.write(byte, line)

    def _emit_constant(self, value: object, line: int) -> None:
        index = self._chunk.add_constant(value)
        self._emit(OpCode.CONSTANT, line)
        self._emit_byte(index, line)

    def _emit_jump(self, opcode: OpCode, line: int) -> int:
        self._emit(opcode, line)
        self._emit_byte(0xFF, line)
        self._emit_byte(0xFF, line)
        return len(self._chunk) - 2

    def _patch_jump(self, offset: int) -> None:
        distance = len(self._chunk) - offset - 2
        if distance > _MAX_JUMP:
            raise Compile(
                f"a jump of {distance} bytes is too far; the body of a branch "
                "or loop is larger than a two-byte offset can span"
            )
        self._chunk.patch(offset, (distance >> 8) & 0xFF)
        self._chunk.patch(offset + 1, distance & 0xFF)

    def _emit_loop(self, loop_start: int, line: int) -> None:
        self._emit(OpCode.LOOP, line)
        distance = len(self._chunk) - loop_start + 2
        if distance > _MAX_JUMP:
            raise Compile(
                f"a loop of {distance} bytes is too far to jump back over"
            )
        self._emit_byte((distance >> 8) & 0xFF, line)
        self._emit_byte(distance & 0xFF, line)

    # statements

    def _statement(self, node: s.Stmt) -> None:
        if isinstance(node, s.ExpressionStmt):
            self._expression(node.expression)
            self._emit(OpCode.POP, self._line_of(node.expression))
        elif isinstance(node, s.PrintStmt):
            self._expression(node.expression)
            self._emit(OpCode.PRINT, node.keyword.line)
        elif isinstance(node, s.LetStmt):
            self._let(node)
        elif isinstance(node, s.Block):
            self._block(node)
        elif isinstance(node, s.IfStmt):
            self._if(node)
        elif isinstance(node, s.WhileStmt):
            self._while(node)
        elif isinstance(node, s.ForStmt):
            self._for(node)
        elif isinstance(node, s.FunctionStmt):
            self._function(node)
        elif isinstance(node, s.ReturnStmt):
            self._return(node)
        else:
            raise Compile(f"the compiler does not handle the statement {type(node).__name__}")

    def _let(self, node: s.LetStmt) -> None:
        line = node.name.line
        if node.initializer is not None:
            self._expression(node.initializer)
        else:
            self._emit(OpCode.NIL, line)
        if self._scope.depth > 0:
            self._scope.declare(node.name.lexeme, node.is_const)
            return
        index = self._chunk.add_constant(node.name.lexeme)
        if node.is_const:
            self._const_globals.add(node.name.lexeme)
            self._emit(OpCode.DEFINE_GLOBAL_CONST, line)
        else:
            self._emit(OpCode.DEFINE_GLOBAL, line)
        self._emit_byte(index, line)

    def _block(self, node: s.Block) -> None:
        self._scope.begin_scope()
        for statement in node.statements:
            self._statement(statement)
        self._discard_scope(self._scope.end_scope())

    def _discard_scope(self, removed: list[Local]) -> None:
        # a captured local must be closed rather than merely popped, so the
        # closure holding it keeps the value once the slot is gone
        for local in removed:
            if local.is_captured:
                self._emit(OpCode.CLOSE_UPVALUE, 1)
            else:
                self._emit(OpCode.POP, 1)

    def _if(self, node: s.IfStmt) -> None:
        line = self._line_of(node.condition)
        self._expression(node.condition)
        then_jump = self._emit_jump(OpCode.JUMP_IF_FALSE, line)
        self._emit(OpCode.POP, line)
        self._statement(node.then_branch)
        else_jump = self._emit_jump(OpCode.JUMP, line)
        self._patch_jump(then_jump)
        self._emit(OpCode.POP, line)
        if node.else_branch is not None:
            self._statement(node.else_branch)
        self._patch_jump(else_jump)

    def _while(self, node: s.WhileStmt) -> None:
        line = self._line_of(node.condition)
        loop_start = len(self._chunk)
        self._expression(node.condition)
        exit_jump = self._emit_jump(OpCode.JUMP_IF_FALSE, line)
        self._emit(OpCode.POP, line)
        self._statement(node.body)
        self._emit_loop(loop_start, line)
        self._patch_jump(exit_jump)
        self._emit(OpCode.POP, line)

    def _for(self, node: s.ForStmt) -> None:
        self._scope.begin_scope()
        if node.initializer is not None:
            self._statement(node.initializer)
        loop_start = len(self._chunk)
        exit_jump = -1
        if node.condition is not None:
            line = self._line_of(node.condition)
            self._expression(node.condition)
            exit_jump = self._emit_jump(OpCode.JUMP_IF_FALSE, line)
            self._emit(OpCode.POP, line)
        if node.increment is not None:
            line = self._line_of(node.increment)
            body_jump = self._emit_jump(OpCode.JUMP, line)
            increment_start = len(self._chunk)
            self._expression(node.increment)
            self._emit(OpCode.POP, line)
            self._emit_loop(loop_start, line)
            loop_start = increment_start
            self._patch_jump(body_jump)
        self._statement(node.body)
        self._emit_loop(loop_start, 1)
        if exit_jump != -1:
            self._patch_jump(exit_jump)
            self._emit(OpCode.POP, 1)
        self._discard_scope(self._scope.end_scope())

    def _function(self, node: s.FunctionStmt) -> None:
        line = node.name.line
        unit = _FunctionUnit(node.name.lexeme, len(node.parameters), enclosing=self._unit)
        unit.scope.begin_scope()
        unit.scope.declare_reserved()
        for parameter in node.parameters:
            unit.scope.declare(parameter.lexeme)
        self._units.append(unit)
        for statement in node.body:
            self._statement(statement)
        self._emit(OpCode.NIL, line)
        self._emit(OpCode.RETURN, line)
        self._units.pop()
        unit.function.upvalue_count = len(unit.upvalues)
        index = self._chunk.add_constant(unit.function)
        self._emit(OpCode.CLOSURE, line)
        self._emit_byte(index, line)
        # each captured variable is described inline: whether it comes from the
        # enclosing frame's locals or from that frame's own upvalues, and where
        for upvalue in unit.upvalues:
            self._emit_byte(1 if upvalue.is_local else 0, line)
            self._emit_byte(upvalue.index, line)
        self._define_name(node.name, is_const=False)

    def _add_upvalue(self, unit: _FunctionUnit, index: int, is_local: bool) -> int:
        for existing, upvalue in enumerate(unit.upvalues):
            if upvalue.index == index and upvalue.is_local == is_local:
                return existing
        if len(unit.upvalues) >= _MAX_UPVALUES:
            raise Compile(
                f"a function cannot capture more than {_MAX_UPVALUES} variables "
                "from enclosing scopes"
            )
        unit.upvalues.append(_Upvalue(index, is_local))
        return len(unit.upvalues) - 1

    def _resolve_upvalue(self, unit: _FunctionUnit, name: str) -> int | None:
        enclosing = unit.enclosing
        if enclosing is None:
            return None
        local = enclosing.scope.resolve(name)
        if local is not None:
            enclosing.scope.mark_captured(local)
            return self._add_upvalue(unit, local, is_local=True)
        inherited = self._resolve_upvalue(enclosing, name)
        if inherited is not None:
            return self._add_upvalue(unit, inherited, is_local=False)
        return None

    def _return(self, node: s.ReturnStmt) -> None:
        line = node.keyword.line
        if node.value is not None:
            self._expression(node.value)
        else:
            self._emit(OpCode.NIL, line)
        self._emit(OpCode.RETURN, line)

    def _define_name(self, name: Token, is_const: bool) -> None:
        line = name.line
        if self._scope.depth > 0:
            self._scope.declare(name.lexeme, is_const)
            return
        index = self._chunk.add_constant(name.lexeme)
        self._emit(OpCode.DEFINE_GLOBAL, line)
        self._emit_byte(index, line)

    # expressions

    def _expression(self, node: e.Expr) -> None:
        if isinstance(node, e.Literal):
            self._literal(node)
        elif isinstance(node, e.Variable):
            self._variable(node)
        elif isinstance(node, e.Assign):
            self._assign(node)
        elif isinstance(node, e.Unary):
            self._unary(node)
        elif isinstance(node, e.Binary):
            self._binary(node)
        elif isinstance(node, e.Logical):
            self._logical(node)
        elif isinstance(node, e.Grouping):
            self._expression(node.inner)
        elif isinstance(node, e.Call):
            self._call(node)
        elif isinstance(node, e.Index):
            self._index(node)
        elif isinstance(node, e.SetIndex):
            self._set_index(node)
        elif isinstance(node, e.ListLiteral):
            self._list(node)
        elif isinstance(node, e.MapLiteral):
            self._map(node)
        else:
            raise Compile(f"the compiler does not handle the expression {type(node).__name__}")

    def _literal(self, node: e.Literal) -> None:
        line = node.token.line
        if node.value is None:
            self._emit(OpCode.NIL, line)
        elif node.value is True:
            self._emit(OpCode.TRUE, line)
        elif node.value is False:
            self._emit(OpCode.FALSE, line)
        else:
            self._emit_constant(node.value, line)

    def _variable(self, node: e.Variable) -> None:
        line = node.name.line
        slot = self._scope.resolve(node.name.lexeme)
        if slot is not None:
            self._emit(OpCode.GET_LOCAL, line)
            self._emit_byte(slot, line)
            return
        upvalue = self._resolve_upvalue(self._unit, node.name.lexeme)
        if upvalue is not None:
            self._emit(OpCode.GET_UPVALUE, line)
            self._emit_byte(upvalue, line)
            return
        index = self._chunk.add_constant(node.name.lexeme)
        self._emit(OpCode.GET_GLOBAL, line)
        self._emit_byte(index, line)

    def _assign(self, node: e.Assign) -> None:
        self._expression(node.value)
        line = node.name.line
        slot = self._scope.resolve(node.name.lexeme)
        if slot is not None:
            if self._scope.is_const(slot):
                raise Immutable(
                    f"the constant {node.name.lexeme!r} cannot be assigned to "
                    "after its declaration"
                )
            self._emit(OpCode.SET_LOCAL, line)
            self._emit_byte(slot, line)
            return
        upvalue = self._resolve_upvalue(self._unit, node.name.lexeme)
        if upvalue is not None:
            self._emit(OpCode.SET_UPVALUE, line)
            self._emit_byte(upvalue, line)
            return
        if node.name.lexeme in self._const_globals:
            raise Immutable(
                f"the constant {node.name.lexeme!r} cannot be assigned to "
                "after its declaration"
            )
        index = self._chunk.add_constant(node.name.lexeme)
        self._emit(OpCode.SET_GLOBAL, line)
        self._emit_byte(index, line)

    def _unary(self, node: e.Unary) -> None:
        self._expression(node.operand)
        line = node.operator.line
        if node.operator.kind == TokenKind.MINUS:
            self._emit(OpCode.NEGATE, line)
        else:
            self._emit(OpCode.NOT, line)

    def _binary(self, node: e.Binary) -> None:
        self._expression(node.left)
        self._expression(node.right)
        opcode = _BINARY_OPS[node.operator.kind]
        self._emit(opcode, node.operator.line)

    def _logical(self, node: e.Logical) -> None:
        line = node.operator.line
        self._expression(node.left)
        if node.operator.kind == TokenKind.AND:
            end_jump = self._emit_jump(OpCode.JUMP_IF_FALSE, line)
            self._emit(OpCode.POP, line)
            self._expression(node.right)
            self._patch_jump(end_jump)
        else:
            end_jump = self._emit_jump(OpCode.JUMP_IF_TRUE, line)
            self._emit(OpCode.POP, line)
            self._expression(node.right)
            self._patch_jump(end_jump)

    def _call(self, node: e.Call) -> None:
        self._expression(node.callee)
        for argument in node.arguments:
            self._expression(argument)
        self._emit(OpCode.CALL, node.paren.line)
        self._emit_byte(len(node.arguments), node.paren.line)

    def _index(self, node: e.Index) -> None:
        self._expression(node.collection)
        self._expression(node.key)
        self._emit(OpCode.INDEX_GET, node.bracket.line)

    def _set_index(self, node: e.SetIndex) -> None:
        self._expression(node.collection)
        self._expression(node.key)
        self._expression(node.value)
        self._emit(OpCode.INDEX_SET, node.bracket.line)

    def _list(self, node: e.ListLiteral) -> None:
        for element in node.elements:
            self._expression(element)
        self._emit(OpCode.BUILD_LIST, node.bracket.line)
        self._emit_byte(len(node.elements), node.bracket.line)

    def _map(self, node: e.MapLiteral) -> None:
        for key, value in node.pairs:
            self._expression(key)
            self._expression(value)
        self._emit(OpCode.BUILD_MAP, node.brace.line)
        self._emit_byte(len(node.pairs), node.brace.line)

    def _line_of(self, node: e.Expr) -> int:
        if isinstance(node, e.Literal):
            return node.token.line
        if isinstance(node, e.Variable):
            return node.name.line
        if isinstance(node, e.Assign):
            return node.name.line
        if isinstance(node, e.Unary):
            return node.operator.line
        if isinstance(node, (e.Binary, e.Logical)):
            return node.operator.line
        if isinstance(node, e.Grouping):
            return self._line_of(node.inner)
        if isinstance(node, e.Call):
            return node.paren.line
        if isinstance(node, (e.Index, e.SetIndex)):
            return node.bracket.line
        if isinstance(node, e.ListLiteral):
            return node.bracket.line
        if isinstance(node, e.MapLiteral):
            return node.brace.line
        return 1


def compile_program(statements: list[s.Stmt]) -> Function:
    return Compiler().compile(statements)
