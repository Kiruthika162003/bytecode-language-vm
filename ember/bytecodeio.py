"""The bytecode file format: write a compiled function out and read it back exactly.

Compiling costs real time, and a program that has not changed since it was
last compiled should not have to be scanned, parsed, and compiled again.
That is what a serialized form buys, and this module defines one. A file
begins with a short magic number and a format version, which is the part
worth insisting on: without them a reader handed an unrelated file would
happily interpret its bytes as instructions and fail somewhere deep and
confusingly, and without a version an old reader handed a newer file would
do the same. Both are checked before a single instruction is read, so a
mismatch is reported as exactly what it is. After the header comes one
function record, and because a function's constant pool can itself hold
functions, the format is recursive: a nested function is written inline as
another complete record, which is how a whole program with its methods and
closures fits in one stream without a separate table or any need for
forward references. Constants are tagged by type so a reader knows how to
decode each, integers and lengths ride the variable-length encoding so
small values cost one byte, and the line table is written in its already
compressed run form rather than replayed byte by byte. The property that
matters is exact round-tripping: what comes back must be indistinguishable
from what went in, including the line information an error message will
later need, and that is what the tests assert rather than merely checking
the code array. The honest limit is that the format is not portable across
versions of this runtime; it is a cache, keyed by a version that is
expected to change whenever the instruction set does, not an archive.
"""

from __future__ import annotations

import struct
from typing import Any

from ember.chunk import Chunk
from ember.errors import Compile
from ember.function import Function
from ember.leb128 import decode_signed, decode_unsigned, encode_signed, encode_unsigned
from ember.linetable import LineTable

MAGIC = b"EMBR"
VERSION = 1

_TAG_NIL = 0
_TAG_TRUE = 1
_TAG_FALSE = 2
_TAG_INT = 3
_TAG_FLOAT = 4
_TAG_STRING = 5
_TAG_FUNCTION = 6


def _write_string(out: bytearray, text: str) -> None:
    encoded = text.encode("utf-8")
    out += encode_unsigned(len(encoded))
    out += encoded


def _read_string(data: bytes, offset: int) -> tuple[str, int]:
    length, offset = decode_unsigned(data, offset)
    end = offset + length
    if end > len(data):
        raise Compile("a string in the bytecode stream runs past the end of the data")
    return data[offset:end].decode("utf-8"), end


def _write_constant(out: bytearray, value: Any) -> None:
    if value is None:
        out.append(_TAG_NIL)
    elif value is True:
        out.append(_TAG_TRUE)
    elif value is False:
        out.append(_TAG_FALSE)
    elif isinstance(value, Function):
        out.append(_TAG_FUNCTION)
        _write_function(out, value)
    elif isinstance(value, int):
        out.append(_TAG_INT)
        out += encode_signed(value)
    elif isinstance(value, float):
        out.append(_TAG_FLOAT)
        out += struct.pack("<d", value)
    elif isinstance(value, str):
        out.append(_TAG_STRING)
        _write_string(out, value)
    else:
        raise Compile(
            f"a value of type {type(value).__name__} cannot be written to a "
            "bytecode file; only nil, booleans, numbers, strings, and functions can"
        )


def _read_constant(data: bytes, offset: int) -> tuple[Any, int]:
    if offset >= len(data):
        raise Compile("the bytecode stream ends where a constant was expected")
    tag = data[offset]
    offset += 1
    if tag == _TAG_NIL:
        return None, offset
    if tag == _TAG_TRUE:
        return True, offset
    if tag == _TAG_FALSE:
        return False, offset
    if tag == _TAG_INT:
        return decode_signed(data, offset)
    if tag == _TAG_FLOAT:
        end = offset + 8
        if end > len(data):
            raise Compile("a float in the bytecode stream runs past the end of the data")
        return struct.unpack("<d", data[offset:end])[0], end
    if tag == _TAG_STRING:
        return _read_string(data, offset)
    if tag == _TAG_FUNCTION:
        return _read_function(data, offset)
    raise Compile(f"the constant tag {tag} is not one this format defines")


def _write_function(out: bytearray, function: Function) -> None:
    _write_string(out, function.name)
    out += encode_unsigned(function.arity)
    out += encode_unsigned(function.upvalue_count)
    chunk = function.chunk
    out += encode_unsigned(len(chunk.code))
    out += bytes(chunk.code)
    runs = chunk.line_runs
    out += encode_unsigned(len(runs))
    for line, count in runs:
        out += encode_unsigned(line)
        out += encode_unsigned(count)
    out += encode_unsigned(len(chunk.constants))
    for value in chunk.constants:
        _write_constant(out, value)


def _read_function(data: bytes, offset: int) -> tuple[Function, int]:
    name, offset = _read_string(data, offset)
    arity, offset = decode_unsigned(data, offset)
    upvalue_count, offset = decode_unsigned(data, offset)
    code_length, offset = decode_unsigned(data, offset)
    end = offset + code_length
    if end > len(data):
        raise Compile("the code array runs past the end of the bytecode data")
    code = list(data[offset:end])
    offset = end
    run_count, offset = decode_unsigned(data, offset)
    runs: list[tuple[int, int]] = []
    for _ in range(run_count):
        line, offset = decode_unsigned(data, offset)
        count, offset = decode_unsigned(data, offset)
        runs.append((line, count))
    constant_count, offset = decode_unsigned(data, offset)
    constants: list[Any] = []
    for _ in range(constant_count):
        value, offset = _read_constant(data, offset)
        constants.append(value)
    chunk = Chunk()
    chunk.code = code
    chunk.constants = constants
    chunk.adopt_line_table(LineTable.from_runs(runs))
    if chunk.line_length != len(code):
        raise Compile(
            f"the line table covers {chunk.line_length} bytes but the code is "
            f"{len(code)}; the file is inconsistent"
        )
    return Function(name, arity, chunk, upvalue_count), offset


def serialize(function: Function) -> bytes:
    out = bytearray()
    out += MAGIC
    out += encode_unsigned(VERSION)
    _write_function(out, function)
    return bytes(out)


def deserialize(data: bytes) -> Function:
    if len(data) < len(MAGIC):
        raise Compile("the data is too short to be a bytecode file")
    if data[: len(MAGIC)] != MAGIC:
        raise Compile(
            f"the data does not start with the {MAGIC.decode()} magic number, so "
            "it is not a bytecode file this reader understands"
        )
    version, offset = decode_unsigned(data, len(MAGIC))
    if version != VERSION:
        raise Compile(
            f"the file is format version {version} but this reader understands "
            f"version {VERSION}; recompile the source"
        )
    function, offset = _read_function(data, offset)
    if offset != len(data):
        raise Compile(
            f"{len(data) - offset} trailing bytes follow the function record; the "
            "file has extra data the format does not define"
        )
    return function
