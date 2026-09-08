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

from ember.errors import Arithmetic, Arity, IndexRange, StackFault, TypeMismatch, Unbound
from ember.function import Function, NativeFunction
from ember.opcode import OpCode
from ember.valueops import is_truthy, stringify, type_name, values_equal

_MAX_FRAMES = 1024


class CallFrame:
    __slots__ = ("base", "function", "ip")

    def __init__(self, function: Function, base: int) -> None:
        self.function = function
        self.ip = 0
        self.base = base


class VM:
    def __init__(self) -> None:
        self.stack: list[Any] = []
        self.frames: list[CallFrame] = []
        self.globals: dict[str, Any] = {}
        self.const_globals: set[str] = set()
        self.output: list[str] = []
        self.instruction_count = 0
        self.max_stack = 0

    def define_native(
        self, name: str, arity: int, handler: Callable[[list[Any]], Any]
    ) -> None:
        self.globals[name] = NativeFunction(name, arity, handler)

    def interpret(self, function: Function) -> Any:
        self.stack.append(function)
        self.frames.append(CallFrame(function, base=0))
        return self._run()

    def _frame(self) -> CallFrame:
        return self.frames[-1]

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

    def _run(self) -> Any:  # noqa: PLR0915
        while True:
            self.instruction_count += 1
            self.max_stack = max(self.max_stack, len(self.stack))
            opcode = OpCode(self._read_byte())
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
            elif opcode == OpCode.RETURN:
                result = self._pop()
                frame = self.frames.pop()
                if not self.frames:
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
            else:
                raise StackFault(f"the machine has no handler for opcode {opcode.name}")

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

    def _call(self, argument_count: int) -> None:
        callee = self._peek(argument_count)
        if isinstance(callee, Function):
            if argument_count != callee.arity:
                raise Arity(
                    f"the function {callee.name!r} expects {callee.arity} "
                    f"arguments but received {argument_count}"
                )
            if len(self.frames) >= _MAX_FRAMES:
                raise StackFault(
                    f"call depth exceeded {_MAX_FRAMES} frames; this is usually "
                    "runaway recursion with no base case"
                )
            base = len(self.stack) - argument_count - 1
            self.frames.append(CallFrame(callee, base))
        elif isinstance(callee, NativeFunction):
            if argument_count != callee.arity:
                raise Arity(
                    f"the native function {callee.name!r} expects {callee.arity} "
                    f"arguments but received {argument_count}"
                )
            arguments = self.stack[len(self.stack) - argument_count :]
            result = callee.handler(arguments)
            del self.stack[len(self.stack) - argument_count - 1 :]
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
