"""The virtual machine: a stack of values, a stack of frames, and a loop that reads bytecode.

The machine is where compiled code finally does something. It holds one
stack of values, on which every instruction operates by pushing and
popping, and one stack of call frames, each remembering which function is
running, where its instruction pointer sits, and where its slice of the
value stack begins. The core is a loop: read the next opcode, do what it
says, repeat. An arithmetic opcode pops two values and pushes a result, a
jump moves the instruction pointer, a call pushes a new frame, and a
return pops one and hands its result back to the caller. Representing
locals as a window into the shared value stack, addressed by an offset
from the frame's base, is the idea that makes calls cheap: entering a
function costs a frame and no copying, because the arguments the caller
pushed are already sitting where the callee's parameters expect them. The
machine also carries light instrumentation, a count of instructions
dispatched and the deepest the value stack ever grew, because those
numbers are exactly what a claim about a program's cost is made of, and
measuring them from inside is more honest than estimating from the
source. The deliberate limits are two. Call depth is capped so runaway
recursion raises a clear fault instead of exhausting the host's own
stack, and a value-stack underflow, which a correct compiler can never
cause, is treated as an internal fault pointing at the compiler rather
than the program. Native functions run host code directly, the escape
hatch that lets a program reach facilities the language does not provide.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from ember.classes import BoundMethod, EmberClass, Instance
from ember.closure import Closure, Upvalue
from ember.errors import (
    Arithmetic,
    Arity,
    EmberError,
    IndexRange,
    StackFault,
    Thrown,
    TypeMismatch,
    Unbound,
)
from ember.function import Function, NativeFunction
from ember.opcode import OpCode
from ember.profiler import Profile
from ember.valueops import (
    is_truthy,
    iteration_source,
    stringify,
    type_name,
    values_equal,
)

_MAX_FRAMES = 1024


def _whole(value: Any, operation: str) -> int:
    """Require an integer, since a bit pattern is only defined for whole numbers."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeMismatch(
            f"cannot {operation} a {type_name(value)}; bitwise operations need "
            "integers, and a float has no bit pattern in this language"
        )
    return value


class Handler:
    """Where to resume, and what to restore, when something is thrown.

    A handler has to remember three things, because a throw can happen an
    arbitrary distance below where the try began: how many frames were live
    when the try was entered, so deeper ones can be discarded; how tall the
    value stack was, so the operands of half-finished expressions are dropped
    rather than left as garbage; and where the catch clause starts.
    """

    __slots__ = ("frame_count", "resume_ip", "stack_depth")

    def __init__(self, frame_count: int, stack_depth: int, resume_ip: int) -> None:
        self.frame_count = frame_count
        self.stack_depth = stack_depth
        self.resume_ip = resume_ip


class CallFrame:
    __slots__ = ("base", "closure", "ip")

    def __init__(self, closure: Closure, base: int) -> None:
        self.closure = closure
        self.ip = 0
        self.base = base

    @property
    def function(self) -> Function:
        return self.closure.function


class VM:
    def __init__(self) -> None:
        self.stack: list[Any] = []
        self.frames: list[CallFrame] = []
        self.globals: dict[str, Any] = {}
        self.const_globals: set[str] = set()
        self.output: list[str] = []
        self.instruction_count = 0
        self.max_stack = 0
        self.open_upvalues: list[Upvalue] = []
        # profiling is off by default so the dispatch loop pays one branch, not a
        # line-table walk, on every instruction
        self.profile: Profile | None = None
        self.handlers: list[Handler] = []

    def reset_execution_state(self) -> None:
        """Discard the value and frame stacks while keeping globals and output.

        A run that faulted leaves its frames in place, and reusing the machine
        without clearing them would let the next program's return land back
        inside the abandoned one. An interactive session reuses one machine on
        purpose, so it resets here between inputs; globals survive, because the
        definitions a session has built up are the whole point of keeping it.
        """
        self.stack.clear()
        self.frames.clear()
        self.open_upvalues.clear()
        self.handlers.clear()

    def enable_profiling(self) -> Profile:
        self.profile = Profile()
        return self.profile

    def define_native(
        self,
        name: str,
        arity: int,
        handler: Callable[..., Any],
        needs_machine: bool = False,
    ) -> None:
        self.globals[name] = NativeFunction(name, arity, handler, needs_machine)

    def interpret(self, function: Function) -> Any:
        script = Closure(function)
        self.stack.append(script)
        self.frames.append(CallFrame(script, base=0))
        return self._run()

    def call_value(self, callee: Any, arguments: list[Any]) -> Any:
        """Call an Ember function from host code and run until it returns.

        This is what lets a native like map invoke the function it was handed.
        The callee and its arguments are pushed exactly as a compiled call
        would push them, and if the call opened a frame the dispatch loop is
        re-entered with a floor at the current depth, so it stops when that one
        frame returns rather than running to the end of the program.
        """
        depth = len(self.frames)
        self.stack.append(callee)
        self.stack.extend(arguments)
        self._call(len(arguments))
        if len(self.frames) == depth:
            # a native callee was handled inline and left its result on the stack
            return self._pop()
        return self._run(stop_depth=depth)

    def _capture_upvalue(self, location: int) -> Upvalue:
        # open upvalues are interned by slot so two closures capturing the same
        # variable share one indirection and therefore genuinely share the value
        for upvalue in self.open_upvalues:
            if not upvalue.is_closed and upvalue.location == location:
                return upvalue
        created = Upvalue(location)
        self.open_upvalues.append(created)
        return created

    def _close_upvalues(self, from_location: int) -> None:
        remaining: list[Upvalue] = []
        for upvalue in self.open_upvalues:
            if not upvalue.is_closed and upvalue.location >= from_location:
                upvalue.close(self.stack)
            else:
                remaining.append(upvalue)
        self.open_upvalues = remaining

    def _frame(self) -> CallFrame:
        return self.frames[-1]

    def current_line(self) -> int:
        # ip has already advanced past the byte being executed, so the line for
        # the instruction that is running is the one before it
        frame = self._frame()
        if not frame.function.chunk.code:
            return 1
        offset = min(max(frame.ip - 1, 0), len(frame.function.chunk.code) - 1)
        return frame.function.chunk.line_at(offset)

    def call_stack(self) -> list[tuple[str, int]]:
        stack: list[tuple[str, int]] = []
        for frame in reversed(self.frames):
            chunk = frame.function.chunk
            if chunk.code:
                offset = min(max(frame.ip - 1, 0), len(chunk.code) - 1)
                line = chunk.line_at(offset)
            else:
                line = 1
            stack.append((frame.function.name, line))
        return stack

    def _read_byte(self) -> int:
        frame = self._frame()
        byte = frame.function.chunk.code[frame.ip]
        frame.ip += 1
        return byte

    def _read_short(self) -> int:
        high = self._read_byte()
        low = self._read_byte()
        return (high << 8) | low

    def _read_constant(self) -> Any:
        return self._frame().function.chunk.constants[self._read_byte()]

    def _pop(self) -> Any:
        if not self.stack:
            raise StackFault(
                "the value stack underflowed; this indicates a compiler bug, "
                "not a fault in the program"
            )
        return self.stack.pop()

    def _peek(self, distance: int = 0) -> Any:
        return self.stack[-1 - distance]

    def _run(self, stop_depth: int = 0) -> Any:  # noqa: PLR0915
        while True:
            try:
                self.instruction_count += 1
                self.max_stack = max(self.max_stack, len(self.stack))
                opcode = OpCode(self._read_byte())
                if self.profile is not None:
                    self.profile.record(opcode, self.current_line())
                if opcode == OpCode.CONSTANT:
                    self.stack.append(self._read_constant())
                elif opcode == OpCode.NIL:
                    self.stack.append(None)
                elif opcode == OpCode.TRUE:
                    self.stack.append(True)
                elif opcode == OpCode.FALSE:
                    self.stack.append(False)
                elif opcode == OpCode.POP:
                    self._pop()
                elif opcode == OpCode.DEFINE_GLOBAL:
                    self.globals[self._read_constant()] = self._pop()
                elif opcode == OpCode.DEFINE_GLOBAL_CONST:
                    name = self._read_constant()
                    self.globals[name] = self._pop()
                    self.const_globals.add(name)
                elif opcode == OpCode.GET_GLOBAL:
                    name = self._read_constant()
                    if name not in self.globals:
                        raise Unbound(f"the name {name!r} is not defined")
                    self.stack.append(self.globals[name])
                elif opcode == OpCode.SET_GLOBAL:
                    name = self._read_constant()
                    if name not in self.globals:
                        raise Unbound(
                            f"cannot assign to {name!r} because it was never declared"
                        )
                    if name in self.const_globals:
                        raise Unbound(
                            f"the constant {name!r} cannot be reassigned"
                        )
                    self.globals[name] = self._peek()
                elif opcode == OpCode.GET_LOCAL:
                    slot = self._read_byte()
                    self.stack.append(self.stack[self._frame().base + slot])
                elif opcode == OpCode.SET_LOCAL:
                    slot = self._read_byte()
                    self.stack[self._frame().base + slot] = self._peek()
                elif opcode == OpCode.ADD:
                    self._add()
                elif opcode in (
                    OpCode.SUBTRACT,
                    OpCode.MULTIPLY,
                    OpCode.DIVIDE,
                    OpCode.MODULO,
                ):
                    self._arithmetic(opcode)
                elif opcode in (
                    OpCode.BIT_AND,
                    OpCode.BIT_OR,
                    OpCode.BIT_XOR,
                    OpCode.SHIFT_LEFT,
                    OpCode.SHIFT_RIGHT,
                ):
                    self._bitwise(opcode)
                elif opcode == OpCode.TO_STRING:
                    self.stack.append(stringify(self._pop()))
                elif opcode == OpCode.BIT_NOT:
                    value = self._pop()
                    self.stack.append(~_whole(value, "invert"))
                elif opcode == OpCode.NEGATE:
                    value = self._pop()
                    if isinstance(value, bool) or not isinstance(value, (int, float)):
                        raise TypeMismatch(
                            f"cannot negate a {type_name(value)}; negation needs a number"
                        )
                    self.stack.append(-value)
                elif opcode == OpCode.EQUAL:
                    right = self._pop()
                    left = self._pop()
                    self.stack.append(values_equal(left, right))
                elif opcode == OpCode.NOT_EQUAL:
                    right = self._pop()
                    left = self._pop()
                    self.stack.append(not values_equal(left, right))
                elif opcode in (
                    OpCode.LESS,
                    OpCode.LESS_EQUAL,
                    OpCode.GREATER,
                    OpCode.GREATER_EQUAL,
                ):
                    self._compare(opcode)
                elif opcode == OpCode.NOT:
                    self.stack.append(not is_truthy(self._pop()))
                elif opcode == OpCode.JUMP:
                    # read the offset into a name first: it advances ip, and folding
                    # it into an augmented assignment would read ip before that
                    offset = self._read_short()
                    self._frame().ip += offset
                elif opcode == OpCode.JUMP_IF_FALSE:
                    offset = self._read_short()
                    if not is_truthy(self._peek()):
                        self._frame().ip += offset
                elif opcode == OpCode.JUMP_IF_TRUE:
                    offset = self._read_short()
                    if is_truthy(self._peek()):
                        self._frame().ip += offset
                elif opcode == OpCode.LOOP:
                    offset = self._read_short()
                    self._frame().ip -= offset
                elif opcode == OpCode.CALL:
                    self._call(self._read_byte())
                elif opcode == OpCode.CLASS:
                    self.stack.append(EmberClass(self._read_constant()))
                elif opcode == OpCode.METHOD:
                    self._define_method(self._read_constant())
                elif opcode == OpCode.GET_PROPERTY:
                    self._get_property(self._read_constant())
                elif opcode == OpCode.SET_PROPERTY:
                    self._set_property(self._read_constant())
                elif opcode == OpCode.PUSH_HANDLER:
                    offset = self._read_short()
                    self.handlers.append(
                        Handler(
                            frame_count=len(self.frames),
                            stack_depth=len(self.stack),
                            resume_ip=self._frame().ip + offset,
                        )
                    )
                elif opcode == OpCode.POP_HANDLER:
                    if self.handlers:
                        self.handlers.pop()
                elif opcode == OpCode.THROW:
                    thrown = self._pop()
                    self._unwind(thrown)
                elif opcode == OpCode.ITER_PREPARE:
                    self.stack.append(iteration_source(self._pop()))
                elif opcode == OpCode.ITER_SIZE:
                    self.stack.append(len(self._pop()))
                elif opcode == OpCode.INHERIT:
                    self._inherit()
                elif opcode == OpCode.GET_SUPER:
                    self._get_super(self._read_constant())
                elif opcode == OpCode.CLOSURE:
                    self._make_closure()
                elif opcode == OpCode.GET_UPVALUE:
                    index = self._read_byte()
                    self.stack.append(self._frame().closure.upvalues[index].get(self.stack))
                elif opcode == OpCode.SET_UPVALUE:
                    index = self._read_byte()
                    self._frame().closure.upvalues[index].set(self.stack, self._peek())
                elif opcode == OpCode.CLOSE_UPVALUE:
                    self._close_upvalues(len(self.stack) - 1)
                    self._pop()
                elif opcode == OpCode.RETURN:
                    result = self._pop()
                    frame = self.frames.pop()
                    self._close_upvalues(frame.base)
                    # a return from inside a try skips its POP_HANDLER, so any
                    # handler belonging to the frame just left is discarded here
                    while self.handlers and self.handlers[-1].frame_count > len(self.frames):
                        self.handlers.pop()
                    if len(self.frames) <= stop_depth:
                        # either the script finished or a re-entrant call returned to
                        # the host code that started it
                        del self.stack[frame.base :]
                        return result
                    del self.stack[frame.base :]
                    self.stack.append(result)
                elif opcode == OpCode.PRINT:
                    self.output.append(stringify(self._pop()))
                elif opcode == OpCode.BUILD_LIST:
                    self._build_list(self._read_byte())
                elif opcode == OpCode.BUILD_MAP:
                    self._build_map(self._read_byte())
                elif opcode == OpCode.INDEX_GET:
                    self._index_get()
                elif opcode == OpCode.INDEX_SET:
                    self._index_set()
                else:
                    raise StackFault(f"the machine has no handler for opcode {opcode.name}")
            except (Thrown, StackFault):
                # a thrown value with nowhere to go, and an internal fault,
                # both leave the machine rather than becoming catchable
                raise
            except EmberError as error:
                if not self.handlers:
                    raise
                # a runtime fault inside a try is handed to the catch clause as
                # its message, so a program can recover from division by zero
                # the same way it recovers from something it threw itself
                self._unwind(str(error))

    def _add(self) -> None:
        right = self._pop()
        left = self._pop()
        left_num = isinstance(left, (int, float)) and not isinstance(left, bool)
        right_num = isinstance(right, (int, float)) and not isinstance(right, bool)
        both_numbers = left_num and right_num
        both_strings = isinstance(left, str) and isinstance(right, str)
        both_lists = isinstance(left, list) and isinstance(right, list)
        if both_numbers or both_strings or both_lists:
            self.stack.append(left + right)
            return
        raise TypeMismatch(
            f"cannot add a {type_name(left)} and a {type_name(right)}; add "
            "two numbers, two strings, or two lists"
        )

    def _bitwise(self, opcode: OpCode) -> None:
        right = self._pop()
        left = self._pop()
        a = _whole(left, opcode.name.lower())
        b = _whole(right, opcode.name.lower())
        if opcode == OpCode.BIT_AND:
            self.stack.append(a & b)
        elif opcode == OpCode.BIT_OR:
            self.stack.append(a | b)
        elif opcode == OpCode.BIT_XOR:
            self.stack.append(a ^ b)
        else:
            if b < 0:
                raise Arithmetic(
                    f"cannot shift by the negative amount {b}; shift the other way"
                )
            if opcode == OpCode.SHIFT_LEFT:
                self.stack.append(a << b)
            else:
                self.stack.append(a >> b)

    def _arithmetic(self, opcode: OpCode) -> None:
        right = self._pop()
        left = self._pop()
        for value in (left, right):
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeMismatch(
                    f"cannot use {opcode.name.lower()} on a {type_name(value)}; "
                    "it needs two numbers"
                )
        if opcode == OpCode.SUBTRACT:
            self.stack.append(left - right)
        elif opcode == OpCode.MULTIPLY:
            self.stack.append(left * right)
        elif opcode == OpCode.DIVIDE:
            if right == 0:
                raise Arithmetic("division by zero has no defined result")
            self.stack.append(left / right)
        else:
            if right == 0:
                raise Arithmetic("remainder by zero has no defined result")
            self.stack.append(left % right)

    def _compare(self, opcode: OpCode) -> None:
        right = self._pop()
        left = self._pop()
        comparable = (
            isinstance(left, (int, float))
            and isinstance(right, (int, float))
            and not isinstance(left, bool)
            and not isinstance(right, bool)
        ) or (isinstance(left, str) and isinstance(right, str))
        if not comparable:
            raise TypeMismatch(
                f"cannot compare a {type_name(left)} with a {type_name(right)}; "
                "order is defined for two numbers or two strings"
            )
        if opcode == OpCode.LESS:
            self.stack.append(left < right)
        elif opcode == OpCode.LESS_EQUAL:
            self.stack.append(left <= right)
        elif opcode == OpCode.GREATER:
            self.stack.append(left > right)
        else:
            self.stack.append(left >= right)

    def _settle_arguments(self, function: Function, argument_count: int) -> int:
        """Check the count, fill any missing defaults, and gather a rest argument.

        This runs before the frame is opened, so by the time the callee begins
        every parameter slot already holds a value and the body never has to ask
        whether it was passed one.
        """
        if not function.accepts(argument_count):
            raise Arity(
                f"the function {function.name!r} expects "
                f"{function.describe_arity()} arguments but received {argument_count}"
            )
        if function.is_variadic:
            extra = argument_count - (function.named)
            if extra > 0:
                gathered = self.stack[len(self.stack) - extra :]
                del self.stack[len(self.stack) - extra :]
                self.stack.append(list(gathered))
            else:
                # the named parameters may still be short of their defaults, and
                # the rest parameter then receives an empty list
                supplied = argument_count
                for value in function.defaults[supplied - function.required :]:
                    self.stack.append(value)
                self.stack.append([])
            return function.arity
        missing = function.named - argument_count
        if missing:
            for value in function.defaults[len(function.defaults) - missing :]:
                self.stack.append(value)
        return function.arity

    def _invoke_closure(self, closure: Closure, argument_count: int) -> None:
        argument_count = self._settle_arguments(closure.function, argument_count)
        if len(self.frames) >= _MAX_FRAMES:
            raise StackFault(
                f"call depth exceeded {_MAX_FRAMES} frames; this is usually "
                "runaway recursion with no base case"
            )
        base = len(self.stack) - argument_count - 1
        self.frames.append(CallFrame(closure, base))
        if self.profile is not None:
            self.profile.record_frame()

    def _inherit(self) -> None:
        subclass = self._pop()
        superclass = self._peek()
        if not isinstance(superclass, EmberClass):
            raise TypeMismatch(
                f"a class can only inherit from a class, and this is a "
                f"{type_name(superclass)}"
            )
        # the superclass's methods are copied in before the subclass declares
        # its own, so an override written below simply replaces the entry
        subclass.methods.update(superclass.methods)

    def _get_super(self, name: str) -> None:
        superclass = self._pop()
        receiver = self._pop()
        method = superclass.find_method(name)
        if method is None:
            raise Unbound(
                f"the superclass {superclass.name} has no method {name!r} for "
                "'super' to reach"
            )
        self.stack.append(BoundMethod(receiver, method))

    def _define_method(self, name: str) -> None:
        method = self._pop()
        klass = self._peek()
        klass.methods[name] = method

    def _get_property(self, name: str) -> None:
        target = self._pop()
        if not isinstance(target, Instance):
            raise TypeMismatch(
                f"only an instance has properties, and this is a {type_name(target)}"
            )
        if name in target.fields:
            self.stack.append(target.fields[name])
            return
        method = target.klass.find_method(name)
        if method is None:
            raise Unbound(
                f"the {target.klass.name} instance has no property {name!r}; it "
                "was never assigned as a field nor declared as a method"
            )
        self.stack.append(BoundMethod(target, method))

    def _set_property(self, name: str) -> None:
        value = self._pop()
        target = self._pop()
        if not isinstance(target, Instance):
            raise TypeMismatch(
                f"only an instance can take a property, and this is a "
                f"{type_name(target)}"
            )
        target.fields[name] = value
        self.stack.append(value)

    def _unwind(self, thrown: Any) -> None:
        """Hand a thrown value to the nearest handler, or give up and raise."""
        if not self.handlers:
            raise Thrown(thrown, stringify(thrown))
        handler = self.handlers.pop()
        del self.frames[handler.frame_count :]
        # locals above the handler's mark may have been captured, so they are
        # closed rather than merely dropped before the stack is truncated
        self._close_upvalues(handler.stack_depth)
        del self.stack[handler.stack_depth :]
        # the thrown value lands where the catch clause's name expects it
        self.stack.append(thrown)
        self._frame().ip = handler.resume_ip

    def _make_closure(self) -> None:
        function = self._read_constant()
        upvalues: list[Upvalue] = []
        enclosing = self._frame()
        for _ in range(function.upvalue_count):
            is_local = self._read_byte()
            index = self._read_byte()
            if is_local:
                upvalues.append(self._capture_upvalue(enclosing.base + index))
            else:
                upvalues.append(enclosing.closure.upvalues[index])
        self.stack.append(Closure(function, upvalues))

    def _call(self, argument_count: int) -> None:
        callee = self._peek(argument_count)
        if isinstance(callee, EmberClass):
            instance = Instance(callee)
            # the class sits where the frame's slot 0 will be, so replacing it
            # with the instance puts the receiver exactly where `this` expects
            self.stack[len(self.stack) - argument_count - 1] = instance
            initializer = callee.initializer
            if initializer is None:
                if argument_count != 0:
                    raise Arity(
                        f"the class {callee.name!r} has no initializer, so it "
                        f"takes no arguments but received {argument_count}"
                    )
                return
            self._invoke_closure(initializer, argument_count)
            return
        if isinstance(callee, BoundMethod):
            self.stack[len(self.stack) - argument_count - 1] = callee.receiver
            self._invoke_closure(callee.method, argument_count)
            return
        if isinstance(callee, Closure):
            argument_count = self._settle_arguments(callee.function, argument_count)
            if len(self.frames) >= _MAX_FRAMES:
                raise StackFault(
                    f"call depth exceeded {_MAX_FRAMES} frames; this is usually "
                    "runaway recursion with no base case"
                )
            base = len(self.stack) - argument_count - 1
            self.frames.append(CallFrame(callee, base))
            if self.profile is not None:
                self.profile.record_frame()
        elif isinstance(callee, NativeFunction):
            if argument_count != callee.arity:
                raise Arity(
                    f"the native function {callee.name!r} expects {callee.arity} "
                    f"arguments but received {argument_count}"
                )
            arguments = self.stack[len(self.stack) - argument_count :]
            del self.stack[len(self.stack) - argument_count - 1 :]
            if callee.needs_machine:
                result = callee.handler(self, arguments)
            else:
                result = callee.handler(arguments)
            self.stack.append(result)
        else:
            raise TypeMismatch(
                f"a {type_name(callee)} is not callable; only functions can be "
                "called"
            )

    def _build_list(self, count: int) -> None:
        items = self.stack[len(self.stack) - count :]
        del self.stack[len(self.stack) - count :]
        self.stack.append(list(items))

    def _build_map(self, count: int) -> None:
        result: dict[Any, Any] = {}
        start = len(self.stack) - count * 2
        for i in range(count):
            key = self.stack[start + i * 2]
            value = self.stack[start + i * 2 + 1]
            if isinstance(key, (list, dict)):
                raise TypeMismatch(
                    f"a {type_name(key)} cannot be a map key; keys must be "
                    "numbers, strings, or booleans"
                )
            result[key] = value
        del self.stack[start:]
        self.stack.append(result)

    def _index_get(self) -> None:
        key = self._pop()
        collection = self._pop()
        if isinstance(collection, list):
            if isinstance(key, bool) or not isinstance(key, int):
                raise TypeMismatch(
                    f"a list index must be an integer, not a {type_name(key)}"
                )
            if not -len(collection) <= key < len(collection):
                raise IndexRange(
                    f"the index {key} is outside a list of length "
                    f"{len(collection)}"
                )
            self.stack.append(collection[key])
        elif isinstance(collection, dict):
            if key not in collection:
                raise IndexRange(f"the key {key!r} is not present in the map")
            self.stack.append(collection[key])
        elif isinstance(collection, str):
            if isinstance(key, bool) or not isinstance(key, int):
                raise TypeMismatch(
                    f"a string index must be an integer, not a {type_name(key)}"
                )
            if not -len(collection) <= key < len(collection):
                raise IndexRange(
                    f"the index {key} is outside a string of length "
                    f"{len(collection)}"
                )
            self.stack.append(collection[key])
        else:
            raise TypeMismatch(
                f"a {type_name(collection)} cannot be indexed; index a list, "
                "map, or string"
            )

    def _index_set(self) -> None:
        value = self._pop()
        key = self._pop()
        collection = self._pop()
        if isinstance(collection, list):
            if isinstance(key, bool) or not isinstance(key, int):
                raise TypeMismatch(
                    f"a list index must be an integer, not a {type_name(key)}"
                )
            if not -len(collection) <= key < len(collection):
                raise IndexRange(
                    f"the index {key} is outside a list of length "
                    f"{len(collection)}"
                )
            collection[key] = value
        elif isinstance(collection, dict):
            if isinstance(key, (list, dict)):
                raise TypeMismatch(
                    f"a {type_name(key)} cannot be a map key; keys must be "
                    "numbers, strings, or booleans"
                )
            collection[key] = value
        else:
            raise TypeMismatch(
                f"a {type_name(collection)} cannot be assigned by index; only a "
                "list or a map can, and a string is immutable"
            )
        self.stack.append(value)
