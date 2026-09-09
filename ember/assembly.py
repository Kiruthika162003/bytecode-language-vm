"""An assembly text for the bytecode: writable by hand, and exactly reversible.

The disassembler prints bytecode for a person to read, and what it prints cannot be read
back: it shows byte offsets, and it resolves each jump into a comment saying where it lands,
both of which are useful to a reader and useless to a parser. This module defines a second
text that is designed to be read back, and provides both directions, so a chunk can be
written out, edited, and assembled again into the same bytecode.

Labels are what make that possible. A jump in bytecode holds a byte distance, which changes
whenever anything between the jump and its target changes, so an assembly text holding
distances could not be edited at all. A label names a position and the assembler computes
the distance, which means an instruction can be inserted anywhere and every jump still lands
where its label is. The writer therefore invents a label for each instruction some jump
targets, and only for those, so a listing carries no more names than it needs.

Nested functions are sections rather than references to something external. Each function in
a program becomes its own block of assembly, and a constant that holds a function names the
block. Resolving those names happens after every section is parsed, because a function can
refer to one defined later and a single pass would have to guess.

A section is labelled rather than named, and that was a correction. The first version used
the function's own name as the label, which read better and could not represent a real
program: two classes each with a method called m produce two functions with one name, the
assembler could not tell which a constant meant, and it refused rather than guessing. Twenty
one of the twenty two corpus programs round tripped and that one did not, which is exactly
the case a language with classes will meet constantly. So a section now carries a generated
label, unique by construction, and records the function's real name as a setting beside it.
The listing is slightly less pretty and can represent every program the compiler produces.

The round trip is a property worth testing rather than trusting, and the tests do: every
program in the corpus and a hundred generated ones are written out, read back, and compared
instruction by instruction against the original, which is the only way to know that a format
claiming to be reversible is.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ember.chunk import Chunk
from ember.errors import Compile
from ember.function import Function
from ember.instructions import Instruction, Program, decode, encode
from ember.opcode import OpCode, operand_bytes

_NEWLINE = chr(10)
_QUOTE = chr(34)
_INDENT = "  "


def _quoted(text: str) -> str:
    escaped = text.replace(chr(92), chr(92) + chr(92)).replace(_QUOTE, chr(92) + _QUOTE)
    escaped = escaped.replace(_NEWLINE, chr(92) + "n").replace(chr(9), chr(92) + "t")
    return _QUOTE + escaped + _QUOTE


def _unquoted(text: str) -> str:
    if len(text) < 2 or not text.startswith(_QUOTE) or not text.endswith(_QUOTE):
        raise Compile(f"a string constant must be quoted, and {text!r} is not")
    inner = text[1:-1]
    pieces: list[str] = []
    at = 0
    while at < len(inner):
        character = inner[at]
        if character == chr(92) and at + 1 < len(inner):
            marker = inner[at + 1]
            pieces.append(
                {"n": _NEWLINE, "t": chr(9), _QUOTE: _QUOTE, chr(92): chr(92)}.get(
                    marker, marker
                )
            )
            at += 2
            continue
        pieces.append(character)
        at += 1
    return "".join(pieces)


def _constant_text(value: object, labels: dict[int, str]) -> str:
    if value is None:
        return "nil"
    if value is True:
        return "true"
    if value is False:
        return "false"
    if isinstance(value, Function):
        # the generated label, not the function's name: two methods can share a name
        return "fn " + labels[id(value)]
    if isinstance(value, str):
        return "string " + _quoted(value)
    if isinstance(value, int):
        return "int " + str(value)
    if isinstance(value, float):
        return "float " + repr(value)
    raise Compile(f"a constant of this kind cannot be written as assembly: {value!r}")


def _label_tree(function: Function, labels: dict[int, str], order: list[Function]) -> None:
    """Give every function in the tree a label unique by construction."""
    labels[id(function)] = f"f{len(order)}"
    order.append(function)
    for constant in function.chunk.constants:
        if isinstance(constant, Function):
            _label_tree(constant, labels, order)


def _labels_for(program: Program) -> dict[int, str]:
    """A name for each instruction some jump lands on, and for no others."""
    targets = sorted(
        {
            instruction.target
            for instruction in program.instructions
            if instruction.target is not None
        }
    )
    return {target: f"L{number}" for number, target in enumerate(targets)}


def _write_function(function: Function, sections: dict[int, str]) -> list[str]:
    program = decode(function.chunk)
    labels = _labels_for(program)
    lines = [
        f".function {sections[id(function)]} name={_quoted(function.name or '')} "
        f"arity={function.arity} upvalues={function.upvalue_count}"
    ]
    if function.is_variadic:
        lines.append(f"{_INDENT}.variadic")
    for default in function.defaults:
        lines.append(f"{_INDENT}.default {_constant_text(default, sections)}")
    for index, value in enumerate(program.constants):
        lines.append(f"{_INDENT}.const {index} {_constant_text(value, sections)}")
    for index, instruction in enumerate(program.instructions):
        if index in labels:
            lines.append(f"{labels[index]}:")
        written = _instruction_text(instruction, labels, len(program.instructions))
        lines.append(_INDENT + written)
    end = len(program.instructions)
    if end in labels:
        # a jump can land just past the last instruction, which needs a label too
        lines.append(f"{labels[end]}:")
    lines.append(".end")
    return lines


def _instruction_text(
    instruction: Instruction, labels: dict[int, str], count: int
) -> str:
    if instruction.target is not None:
        label = labels.get(instruction.target, f"L_unknown_{instruction.target}")
        return f"{instruction.opcode.name} {label}"
    del count
    if instruction.operands:
        listed = " ".join(str(operand) for operand in instruction.operands)
        return f"{instruction.opcode.name} {listed}"
    return instruction.opcode.name


def to_assembly(function: Function) -> str:
    """Write a function and every function nested in it as assembly text."""
    sections: dict[int, str] = {}
    order: list[Function] = []
    _label_tree(function, sections, order)
    lines: list[str] = []
    for one in order:
        if lines:
            lines.append("")
        lines.extend(_write_function(one, sections))
    return _NEWLINE.join(lines)


@dataclass
class _Section:
    label: str
    name: str = ""
    arity: int = 0
    upvalues: int = 0
    is_variadic: bool = False
    defaults: list[object] = field(default_factory=list)
    constants: dict[int, object] = field(default_factory=dict)
    pending: dict[int, str] = field(default_factory=dict)
    lines: list[tuple[str, list[str]]] = field(default_factory=list)
    labels: dict[str, int] = field(default_factory=dict)


def _parse_constant(words: list[str], section: _Section, index: int) -> None:
    if not words:
        raise Compile(f"the constant {index} in {section.name} has no value")
    kind = words[0]
    rest = " ".join(words[1:])
    if kind == "nil":
        section.constants[index] = None
    elif kind == "true":
        section.constants[index] = True
    elif kind == "false":
        section.constants[index] = False
    elif kind == "int":
        section.constants[index] = int(rest)
    elif kind == "float":
        section.constants[index] = float(rest)
    elif kind == "string":
        section.constants[index] = _unquoted(rest)
    elif kind == "fn":
        # resolved once every section is known, because a function may name one
        # that is defined further down
        section.pending[index] = rest
    else:
        raise Compile(f"{kind!r} is not a kind of constant this assembler knows")


def _parse_default(words: list[str], section: _Section) -> None:
    holder = _Section(label=section.label)
    _parse_constant(words, holder, 0)
    if 0 not in holder.constants:
        raise Compile("a default value cannot be a function")
    section.defaults.append(holder.constants[0])


def _sections_of(text: str) -> list[_Section]:
    sections: list[_Section] = []
    current: _Section | None = None
    for number, raw in enumerate(text.split(_NEWLINE), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith(".function"):
            if current is not None:
                raise Compile(f"line {number} opens a function inside another")
            current = _header(line, number)
            continue
        if current is None:
            raise Compile(f"line {number} is outside any function section")
        if line == ".end":
            sections.append(current)
            current = None
            continue
        if line == ".variadic":
            current.is_variadic = True
            continue
        if line.startswith(".default"):
            _parse_default(line.split()[1:], current)
            continue
        if line.startswith(".const"):
            words = line.split()
            if len(words) < 3:
                raise Compile(f"line {number} is not a complete constant")
            _parse_constant(words[2:], current, int(words[1]))
            continue
        if line.endswith(":"):
            current.labels[line[:-1]] = len(current.lines)
            continue
        words = line.split()
        current.lines.append((words[0], words[1:]))
    if current is not None:
        raise Compile(f"the section {current.label} was opened and never ended")
    return sections


def _header(line: str, number: int) -> _Section:
    words = line.split(" ")
    words = [word for word in words if word]
    if len(words) < 2:
        raise Compile(f"line {number} opens a function with no label")
    section = _Section(label=words[1])
    rest = line.split(" ", 2)[2] if len(words) > 2 else ""
    for setting in _settings_of(rest, number):
        key, _, value = setting.partition("=")
        if key == "arity":
            section.arity = int(value)
        elif key == "upvalues":
            section.upvalues = int(value)
        elif key == "name":
            section.name = _unquoted(value) if value.startswith(_QUOTE) else value
        else:
            raise Compile(f"line {number} carries the unknown setting {key!r}")
    return section


def _settings_of(text: str, number: int) -> list[str]:
    """Split a header's settings, keeping a quoted name in one piece."""
    found: list[str] = []
    current = ""
    inside = False
    for character in text:
        if character == _QUOTE:
            inside = not inside
        if character == " " and not inside:
            if current:
                found.append(current)
            current = ""
            continue
        current += character
    if inside:
        raise Compile(f"line {number} has a name that is opened and never closed")
    if current:
        found.append(current)
    return found


def _built(section: _Section, functions: dict[str, Function]) -> Function:
    program = Program()
    highest = max(section.constants) if section.constants else -1
    highest = max(highest, max(section.pending) if section.pending else -1)
    pool: list[object] = [None] * (highest + 1)
    for index, value in section.constants.items():
        pool[index] = value
    for index, name in section.pending.items():
        if name not in functions:
            raise Compile(
                f"the constant {index} names the section {name!r}, which is absent"
            )
        pool[index] = functions[name]
    program.constants = pool
    for opcode_name, words in section.lines:
        try:
            opcode = OpCode[opcode_name]
        except KeyError as unknown:
            raise Compile(f"{opcode_name!r} is not an instruction") from unknown
        if words and words[0] in section.labels:
            program.instructions.append(
                Instruction(opcode, 1, target=section.labels[words[0]])
            )
            continue
        if words and not words[0].lstrip("-").isdigit():
            raise Compile(
                f"{words[0]!r} is neither a number nor a label in section {section.label}"
            )
        operands = tuple(int(word) for word in words)
        expected = operand_bytes(opcode)
        if opcode != OpCode.CLOSURE and len(operands) != expected:
            raise Compile(
                f"{opcode_name} takes {expected} operands and was given {len(operands)}"
            )
        program.instructions.append(Instruction(opcode, 1, operands=operands))
    chunk = encode(program)
    return Function(
        name=section.name,
        arity=section.arity,
        chunk=chunk,
        upvalue_count=section.upvalues,
        defaults=tuple(section.defaults),
        is_variadic=section.is_variadic,
    )


def from_assembly(text: str) -> Function:
    """Read assembly text back into a function, resolving the sections together."""
    sections = _sections_of(text)
    if not sections:
        raise Compile("this assembly text holds no function sections")
    labels = [section.label for section in sections]
    if len(set(labels)) != len(labels):
        repeated = sorted({label for label in labels if labels.count(label) > 1})
        raise Compile(
            f"two sections both carry the label {repeated[0]!r}, and a constant naming "
            "a section could not say which; a label has to be unique"
        )
    functions: dict[str, Function] = {}
    # the later sections are built first, so a function that names another is built
    # once the one it names exists
    for section in reversed(sections):
        functions[section.label] = _built(section, functions)
    return functions[sections[0].label]


def round_trips(function: Function) -> bool:
    """Whether writing and reading a function gives back the same bytecode."""
    rebuilt = from_assembly(to_assembly(function))
    return list(rebuilt.chunk.code) == list(function.chunk.code)


def chunk_of(text: str) -> Chunk:
    return from_assembly(text).chunk
