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
third responsibility, added after the first two were working, is capture:
a name that is neither a local here nor a global is looked for among the
enclosing function's locals and then among that function's own upvalues,
so a nested function closes over the variables it mentions and a
declaration emits CLOSURE carrying one descriptor per captured variable.
An earlier version of this compiler treated such a name as a global and
left a nested reference to fault at run time, and the note recording that
limitation is kept here rather than deleted, because the shape of the fix,
resolving through enclosing units and marking the captured local so its
scope closes it instead of popping it, is the interesting part. What
remains true is that this pass never optimises: it writes the
straightforward instruction sequence for each construct. Folding and dead
branch removal do happen, but in a separate pass over the tree that runs
before this one rather than here, which keeps this pass a translation and
nothing more. This docstring long said that nothing worked at the
instruction level, that a redundant load was never removed and a jump
landing on another jump never threaded, and that such a pass would need
its own jump-retargeting machinery because rewriting bytecode moves every
offset that points past the edit. That prediction was right about the
difficulty and is now out of date about the absence: a peephole pass does
both, and the retargeting it needed turned out to be a matter of decoding
jumps into references to instructions rather than distances in bytes,
after which deletion is safe. What this compiler still does, and should,
is emit the straightforward sequence and leave the tightening to a pass
whose only job is that.
"""

from __future__ import annotations

from ember import exprnodes as e
from ember import stmtnodes as s
from ember.chunk import Chunk
from ember.classes import INITIALIZER
from ember.errors import Compile, Immutable, Resolve
from ember.function import Function
from ember.interpolation import TEXT as _TEXT
from ember.localscope import Local, LocalScope
from ember.opcode import OpCode
from ember.token import Token
from ember.tokenkind import TokenKind

_MAX_JUMP = 0xFFFF
_MAX_UPVALUES = 256
_SUPER = "super"
# hidden locals for an iteration; the "@" cannot appear in a source identifier,
# so these can never collide with a name the program itself declares
_ITER = "@iterable"
_INDEX = "@index"
_LIMIT = "@limit"
_SUBJECT = "@subject"

_BINARY_OPS = {
    TokenKind.PLUS: OpCode.ADD,
    TokenKind.MINUS: OpCode.SUBTRACT,
    TokenKind.STAR: OpCode.MULTIPLY,
    TokenKind.SLASH: OpCode.DIVIDE,
    TokenKind.PERCENT: OpCode.MODULO,
    TokenKind.AMPERSAND: OpCode.BIT_AND,
    TokenKind.PIPE: OpCode.BIT_OR,
    TokenKind.CARET: OpCode.BIT_XOR,
    TokenKind.LESS_LESS: OpCode.SHIFT_LEFT,
    TokenKind.GREATER_GREATER: OpCode.SHIFT_RIGHT,
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


class _Loop:
    """Where a loop's break jumps must land and where continue must go back to.

    A break cannot be patched when it is emitted, because the end of the loop
    has not been compiled yet, so each one records its offset here and they
    are all patched together once the loop closes. A continue is the opposite
    case: its target already exists, so it is emitted as a backward jump
    immediately. The scope depth at entry is kept because both statements
    leave the loop body early and must discard whatever locals the body had
    declared, which the compiler can only know by comparing depths.
    """

    __slots__ = ("breaks", "continue_target", "depth", "handler_depth")

    def __init__(self, continue_target: int, depth: int, handler_depth: int = 0) -> None:
        self.continue_target = continue_target
        self.depth = depth
        self.handler_depth = handler_depth
        self.breaks: list[int] = []


class _FunctionUnit:
    def __init__(
        self,
        name: str,
        arity: int,
        enclosing: _FunctionUnit | None = None,
        defaults: tuple[object, ...] = (),
        is_variadic: bool = False,
    ) -> None:
        self.function = Function(
            name, arity, Chunk(), defaults=defaults, is_variadic=is_variadic
        )
        self.scope = LocalScope()
        self.enclosing = enclosing
        self.upvalues: list[_Upvalue] = []
        self.is_initializer = False
        self.loops: list[_Loop] = []
        self.handler_depth = 0


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
        elif isinstance(node, s.ForEachStmt):
            self._for_each(node)
        elif isinstance(node, s.FunctionStmt):
            self._function(node)
        elif isinstance(node, s.ClassStmt):
            self._class(node)
        elif isinstance(node, s.ReturnStmt):
            self._return(node)
        elif isinstance(node, s.MatchStmt):
            self._match(node)
        elif isinstance(node, s.TryStmt):
            self._try(node)
        elif isinstance(node, s.ThrowStmt):
            self._throw(node)
        elif isinstance(node, s.BreakStmt):
            self._break(node)
        elif isinstance(node, s.ContinueStmt):
            self._continue(node)
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
        loop = _Loop(
            continue_target=loop_start,
            depth=self._scope.depth,
            handler_depth=self._unit.handler_depth,
        )
        self._unit.loops.append(loop)
        self._statement(node.body)
        self._unit.loops.pop()
        self._emit_loop(loop_start, line)
        self._patch_jump(exit_jump)
        self._emit(OpCode.POP, line)
        # a break lands past the condition's pop, so it leaves no residue
        for offset in loop.breaks:
            self._patch_jump(offset)

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
        # continue targets the increment rather than the condition, so the step
        # still runs and a counting loop cannot be turned into an infinite one
        loop = _Loop(
            continue_target=loop_start,
            depth=self._scope.depth,
            handler_depth=self._unit.handler_depth,
        )
        self._unit.loops.append(loop)
        self._statement(node.body)
        self._unit.loops.pop()
        self._emit_loop(loop_start, 1)
        if exit_jump != -1:
            self._patch_jump(exit_jump)
            self._emit(OpCode.POP, 1)
        for offset in loop.breaks:
            self._patch_jump(offset)
        self._discard_scope(self._scope.end_scope())

    def _for_each(self, node: s.ForEachStmt) -> None:
        line = node.variable.line
        self._scope.begin_scope()
        # the collection is evaluated once into a hidden local, so a call in the
        # iterable position happens a single time rather than every iteration
        self._expression(node.iterable)
        self._emit(OpCode.ITER_PREPARE, line)
        self._scope.declare(_ITER)
        self._emit_constant(0, line)
        self._scope.declare(_INDEX)
        iter_slot = self._scope.resolve(_ITER)
        index_slot = self._scope.resolve(_INDEX)
        self._emit(OpCode.GET_LOCAL, line)
        self._emit_byte(iter_slot, line)
        self._emit(OpCode.ITER_SIZE, line)
        self._scope.declare(_LIMIT)
        limit_slot = self._scope.resolve(_LIMIT)

        loop_start = len(self._chunk)
        self._emit(OpCode.GET_LOCAL, line)
        self._emit_byte(index_slot, line)
        self._emit(OpCode.GET_LOCAL, line)
        self._emit_byte(limit_slot, line)
        self._emit(OpCode.LESS, line)
        exit_jump = self._emit_jump(OpCode.JUMP_IF_FALSE, line)
        self._emit(OpCode.POP, line)
        # the step is emitted before the body and jumped over on first entry, so
        # a continue can reach it with a single backward jump
        body_jump = self._emit_jump(OpCode.JUMP, line)
        step_start = len(self._chunk)
        self._emit(OpCode.GET_LOCAL, line)
        self._emit_byte(index_slot, line)
        self._emit_constant(1, line)
        self._emit(OpCode.ADD, line)
        self._emit(OpCode.SET_LOCAL, line)
        self._emit_byte(index_slot, line)
        self._emit(OpCode.POP, line)
        self._emit_loop(loop_start, line)
        self._patch_jump(body_jump)

        loop = _Loop(
            continue_target=step_start,
            depth=self._scope.depth,
            handler_depth=self._unit.handler_depth,
        )
        self._unit.loops.append(loop)
        self._scope.begin_scope()
        self._emit(OpCode.GET_LOCAL, line)
        self._emit_byte(iter_slot, line)
        self._emit(OpCode.GET_LOCAL, line)
        self._emit_byte(index_slot, line)
        self._emit(OpCode.INDEX_GET, line)
        self._scope.declare(node.variable.lexeme)
        self._statement(node.body)
        self._discard_scope(self._scope.end_scope())
        self._unit.loops.pop()
        self._emit_loop(step_start, line)

        self._patch_jump(exit_jump)
        self._emit(OpCode.POP, line)
        for offset in loop.breaks:
            self._patch_jump(offset)
        self._discard_scope(self._scope.end_scope())

    def _function(self, node: s.FunctionStmt) -> None:
        line = node.name.line
        unit = _FunctionUnit(
            node.name.lexeme,
            len(node.parameters),
            enclosing=self._unit,
            defaults=node.defaults,
            is_variadic=node.is_variadic,
        )
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

    def _class(self, node: s.ClassStmt) -> None:
        line = node.name.line
        name_index = self._chunk.add_constant(node.name.lexeme)
        self._emit(OpCode.CLASS, line)
        self._emit_byte(name_index, line)
        self._define_name(node.name, is_const=False)
        if node.superclass is not None:
            # the superclass is held in a hidden local for the class body, which
            # methods capture as an upvalue; that is how super reaches it after
            # the declaration has finished and the stack window is gone
            self._scope.begin_scope()
            self._load_name(node.superclass)
            self._scope.declare(_SUPER)
            self._load_name(node.name)
            self._emit(OpCode.INHERIT, line)
        self._load_name(node.name)
        seen: set[str] = set()
        for method in node.methods:
            if method.name.lexeme in seen:
                raise Resolve(
                    f"the class {node.name.lexeme!r} declares the method "
                    f"{method.name.lexeme!r} twice; remove one of them"
                )
            seen.add(method.name.lexeme)
            self._method(method)
        self._emit(OpCode.POP, line)
        if node.superclass is not None:
            self._discard_scope(self._scope.end_scope())

    def _method(self, node: s.FunctionStmt) -> None:
        line = node.name.line
        is_initializer = node.name.lexeme == INITIALIZER
        unit = _FunctionUnit(
            node.name.lexeme,
            len(node.parameters),
            enclosing=self._unit,
            defaults=node.defaults,
            is_variadic=node.is_variadic,
        )
        unit.is_initializer = is_initializer
        unit.scope.begin_scope()
        unit.scope.declare_receiver()
        for parameter in node.parameters:
            unit.scope.declare(parameter.lexeme)
        self._units.append(unit)
        for statement in node.body:
            self._statement(statement)
        if is_initializer:
            # an initializer always yields the instance, never nil, so the
            # caller of a class gets the object back rather than nothing
            self._emit(OpCode.GET_LOCAL, line)
            self._emit_byte(0, line)
        else:
            self._emit(OpCode.NIL, line)
        self._emit(OpCode.RETURN, line)
        self._units.pop()
        unit.function.upvalue_count = len(unit.upvalues)
        index = self._chunk.add_constant(unit.function)
        self._emit(OpCode.CLOSURE, line)
        self._emit_byte(index, line)
        for upvalue in unit.upvalues:
            self._emit_byte(1 if upvalue.is_local else 0, line)
            self._emit_byte(upvalue.index, line)
        name_index = self._chunk.add_constant(node.name.lexeme)
        self._emit(OpCode.METHOD, line)
        self._emit_byte(name_index, line)

    def _load_name(self, name: Token) -> None:
        line = name.line
        slot = self._scope.resolve(name.lexeme)
        if slot is not None:
            self._emit(OpCode.GET_LOCAL, line)
            self._emit_byte(slot, line)
            return
        index = self._chunk.add_constant(name.lexeme)
        self._emit(OpCode.GET_GLOBAL, line)
        self._emit_byte(index, line)

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
            if self._unit.is_initializer:
                raise Resolve(
                    f"the initializer on line {line} cannot return a value, "
                    "since calling a class must yield the new instance"
                )
            self._expression(node.value)
        elif self._unit.is_initializer:
            self._emit(OpCode.GET_LOCAL, line)
            self._emit_byte(0, line)
        else:
            self._emit(OpCode.NIL, line)
        self._emit(OpCode.RETURN, line)

    def _match(self, node: s.MatchStmt) -> None:
        """Compile a match into one subject evaluation and a chain of comparisons.

        The subject is computed once into a hidden local, so a call in that
        position happens a single time however many arms are tested against it.
        Each arm compares the subject to its values in turn and jumps to the body
        on the first that is equal, and because this language has no fallthrough
        every body ends by jumping past the rest, so exactly one arm can run.
        """
        line = node.keyword.line
        self._scope.begin_scope()
        self._expression(node.subject)
        self._scope.declare(_SUBJECT)
        subject_slot = self._scope.resolve(_SUBJECT)
        finished: list[int] = []
        for arm in node.cases:
            matched: list[int] = []
            for value in arm.values:
                self._emit(OpCode.GET_LOCAL, line)
                self._emit_byte(subject_slot, line)
                self._expression(value)
                self._emit(OpCode.EQUAL, line)
                matched.append(self._emit_jump(OpCode.JUMP_IF_TRUE, line))
                # the comparison left a falsehood behind, so it is dropped before
                # the next value is tried
                self._emit(OpCode.POP, line)
            skip = self._emit_jump(OpCode.JUMP, line)
            for offset in matched:
                self._patch_jump(offset)
            # whichever comparison jumped here left its truth on the stack
            self._emit(OpCode.POP, line)
            self._statement(arm.body)
            finished.append(self._emit_jump(OpCode.JUMP, line))
            self._patch_jump(skip)
        if node.default is not None:
            self._statement(node.default)
        for offset in finished:
            self._patch_jump(offset)
        self._discard_scope(self._scope.end_scope())

    def _try(self, node: s.TryStmt) -> None:
        line = node.keyword.line
        handler_jump = self._emit_jump(OpCode.PUSH_HANDLER, line)
        self._unit.handler_depth += 1
        self._statement(node.body)
        self._unit.handler_depth -= 1
        self._emit(OpCode.POP_HANDLER, line)
        done_jump = self._emit_jump(OpCode.JUMP, line)
        self._patch_jump(handler_jump)
        # the machine pushes the thrown value where the catch name's slot lands,
        # so the name is simply declared over it rather than stored explicitly
        self._scope.begin_scope()
        self._scope.declare(node.catch_name.lexeme)
        self._statement(node.handler)
        self._discard_scope(self._scope.end_scope())
        self._patch_jump(done_jump)

    def _throw(self, node: s.ThrowStmt) -> None:
        self._expression(node.value)
        self._emit(OpCode.THROW, node.keyword.line)

    def _break(self, node: s.BreakStmt) -> None:
        loop = self._innermost_loop(node.keyword.line, "break")
        self._leave_handlers(loop.handler_depth, node.keyword.line)
        self._unwind_to(loop.depth, node.keyword.line)
        loop.breaks.append(self._emit_jump(OpCode.JUMP, node.keyword.line))

    def _continue(self, node: s.ContinueStmt) -> None:
        loop = self._innermost_loop(node.keyword.line, "continue")
        self._leave_handlers(loop.handler_depth, node.keyword.line)
        self._unwind_to(loop.depth, node.keyword.line)
        self._emit_loop(loop.continue_target, node.keyword.line)

    def _leave_handlers(self, depth: int, line: int) -> None:
        # jumping out of a try block skips its POP_HANDLER, so one is emitted per
        # handler being escaped or the machine would keep a handler for a block
        # that is no longer running
        for _ in range(self._unit.handler_depth - depth):
            self._emit(OpCode.POP_HANDLER, line)

    def _innermost_loop(self, line: int, word: str) -> _Loop:
        if not self._unit.loops:
            raise Resolve(f"'{word}' on line {line} is outside any loop")
        return self._unit.loops[-1]

    def _unwind_to(self, depth: int, line: int) -> None:
        # leaving a loop body early still has to discard the locals the body
        # declared, closing any an inner closure captured rather than popping it
        for slot in range(self._scope.count - 1, -1, -1):
            if self._scope.depth_of(slot) <= depth:
                break
            if self._scope.is_captured(slot):
                self._emit(OpCode.CLOSE_UPVALUE, line)
            else:
                self._emit(OpCode.POP, line)

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
        elif isinstance(node, e.Interpolation):
            self._interpolation(node)
        elif isinstance(node, e.Conditional):
            self._conditional(node)
        elif isinstance(node, e.Get):
            self._get_property(node)
        elif isinstance(node, e.Set):
            self._set_property(node)
        elif isinstance(node, e.This):
            self._this(node)
        elif isinstance(node, e.Super):
            self._super(node)
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
        elif node.operator.kind == TokenKind.TILDE:
            self._emit(OpCode.BIT_NOT, line)
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

    def _interpolation(self, node: e.Interpolation) -> None:
        # each piece is pushed as a string and the pieces are added together, so
        # the result is built by the same concatenation a program could write by
        # hand; the only thing the machine adds is turning a value into its text
        line = node.token.line
        if not node.parts:
            self._emit_constant("", line)
            return
        first = True
        for kind, value in node.parts:
            if kind == _TEXT:
                self._emit_constant(value, line)
            else:
                self._expression(value)
                self._emit(OpCode.TO_STRING, line)
            if not first:
                self._emit(OpCode.ADD, line)
            first = False

    def _conditional(self, node: e.Conditional) -> None:
        # the same shape as an if statement, except each arm leaves a value, so
        # the whole expression yields whichever arm ran
        line = node.question.line
        self._expression(node.condition)
        else_jump = self._emit_jump(OpCode.JUMP_IF_FALSE, line)
        self._emit(OpCode.POP, line)
        self._expression(node.when_true)
        end_jump = self._emit_jump(OpCode.JUMP, line)
        self._patch_jump(else_jump)
        self._emit(OpCode.POP, line)
        self._expression(node.when_false)
        self._patch_jump(end_jump)

    def _get_property(self, node: e.Get) -> None:
        self._expression(node.target)
        index = self._chunk.add_constant(node.name.lexeme)
        self._emit(OpCode.GET_PROPERTY, node.name.line)
        self._emit_byte(index, node.name.line)

    def _set_property(self, node: e.Set) -> None:
        self._expression(node.target)
        self._expression(node.value)
        index = self._chunk.add_constant(node.name.lexeme)
        self._emit(OpCode.SET_PROPERTY, node.name.line)
        self._emit_byte(index, node.name.line)

    def _this(self, node: e.This) -> None:
        line = node.keyword.line
        slot = self._scope.resolve("this")
        if slot is not None:
            self._emit(OpCode.GET_LOCAL, line)
            self._emit_byte(slot, line)
            return
        upvalue = self._resolve_upvalue(self._unit, "this")
        if upvalue is not None:
            self._emit(OpCode.GET_UPVALUE, line)
            self._emit_byte(upvalue, line)
            return
        raise Resolve(
            f"'this' on line {line} is outside any method, so there is no "
            "instance for it to name"
        )

    def _super(self, node: e.Super) -> None:
        line = node.keyword.line
        self._emit_named_load("this", line, "'this'")
        self._emit_named_load(_SUPER, line, "'super'")
        index = self._chunk.add_constant(node.method.lexeme)
        self._emit(OpCode.GET_SUPER, line)
        self._emit_byte(index, line)

    def _emit_named_load(self, name: str, line: int, label: str) -> None:
        slot = self._scope.resolve(name)
        if slot is not None:
            self._emit(OpCode.GET_LOCAL, line)
            self._emit_byte(slot, line)
            return
        upvalue = self._resolve_upvalue(self._unit, name)
        if upvalue is not None:
            self._emit(OpCode.GET_UPVALUE, line)
            self._emit_byte(upvalue, line)
            return
        raise Resolve(f"{label} on line {line} has nothing to refer to here")

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
        if isinstance(node, (e.Get, e.Set)):
            return node.name.line
        if isinstance(node, (e.This, e.Super)):
            return node.keyword.line
        if isinstance(node, e.Interpolation):
            return node.token.line
        if isinstance(node, e.Conditional):
            return node.question.line
        if isinstance(node, e.ListLiteral):
            return node.bracket.line
        if isinstance(node, e.MapLiteral):
            return node.brace.line
        return 1


def compile_program(statements: list[s.Stmt]) -> Function:
    return Compiler().compile(statements)
