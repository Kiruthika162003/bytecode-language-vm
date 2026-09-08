"""Writing compiled code to bytes and reading it back, and what must survive the trip.

Compiling costs time, and a program that has not changed should not pay it
twice, which is what a serialized form is for. The requirement is not that the
bytes be small but that what comes back be indistinguishable from what went out,
and this example checks that in the way that actually catches mistakes. Comparing
the code arrays would miss a lost constant or a mangled line table, so it
compares the disassembly, which renders the instructions, the constants they
point at, and the source line each came from. It also counts the function records,
because the format writes a nested function inline inside its parent's constant
pool, and a miscount would mean a whole nesting level was silently dropped. Then
it runs both and compares output, which is the only end-to-end check. The size is
reported last, and it is small mostly because lengths and indices ride a
variable-length encoding where a value under 128 costs one byte. The example ends
on what the format is not: it carries a version, and a reader refuses a file
written by a different one, because the instruction set is expected to change and
a stale cache silently misinterpreted would be far worse than a refused one. It
is a cache, not an archive.
"""

from __future__ import annotations

from ember.builtins import install_builtins
from ember.bytecodeio import MAGIC, VERSION, deserialize, serialize
from ember.disassembler import disassemble
from ember.errors import Compile
from ember.function import Function
from ember.interpreter import build
from ember.vm import VM

PROGRAM = """class Account {
  init(owner, balance) { this.owner = owner; this.balance = balance; }
  deposit(amount) { this.balance = this.balance + amount; return this; }
  describe() { return this.owner + " has " + str(this.balance); }
}
class Savings < Account {
  describe() { return super.describe() + " saved"; }
}
fn counter() { let n = 0; fn tick() { n = n + 1; return n; } return tick; }
let tick = counter();
let a = Savings("ada", 100);
print a.deposit(50).describe();
print tick(); print tick();
print len("hello") + 1;
print nil; print true; print 2.5; print -7;
"""


def _records(function: Function) -> int:
    total = 1
    for constant in function.chunk.constants:
        if isinstance(constant, Function):
            total += _records(constant)
    return total


def _output(function: Function) -> list[str]:
    machine = VM()
    install_builtins(machine)
    machine.interpret(function)
    return machine.output


def main() -> None:
    original = build(PROGRAM)
    blob = serialize(original)
    restored = deserialize(blob)

    print("a program with two classes, inheritance, and a closure factory")
    print(f"  compiled to {len(original.chunk.code)} bytes in the top-level chunk")
    print(f"  serialized to {len(blob)} bytes in total")
    print(f"  the file begins with the magic number {MAGIC.decode()!r} "
          f"and format version {VERSION}")

    print()
    print("what has to survive, checked the way that catches mistakes:")
    same_text = disassemble(original.chunk, "x") == disassemble(restored.chunk, "x")
    print(f"  disassembly identical: {same_text}")
    print("  (comparing the disassembly rather than the code array, because that")
    print("   also compares the constants and the line each instruction came from)")
    before = [original.chunk.line_at(i) for i in range(len(original.chunk.code))]
    after = [restored.chunk.line_at(i) for i in range(len(restored.chunk.code))]
    print(f"  line table identical: {before == after}")
    print(f"  function records: {_records(original)} out, {_records(restored)} back")
    print("  (nested functions are written inline in their parent's pool, so a")
    print("   miscount would mean a nesting level was dropped)")
    print(f"  output identical: {_output(original) == _output(restored)}")
    print(f"  and what it printed: {_output(restored)}")

    print()
    print("a file from a different format version is refused, not guessed at:")
    tampered = blob[: len(MAGIC)] + bytes([VERSION + 9]) + blob[len(MAGIC) + 1 :]
    try:
        deserialize(tampered)
        print("  it was accepted, which would be a bug")
    except Compile as error:
        print(f"  {error}")

    print()
    print("and an unrelated file is refused before any instruction is read:")
    try:
        deserialize(b"NOPE" + blob[4:])
        print("  it was accepted, which would be a bug")
    except Compile as error:
        print(f"  {error}")

    print()
    print("what this format is not:")
    print("  it is a cache keyed by a version, not an archive. the instruction set")
    print("  is expected to change, and a stale file silently misinterpreted would")
    print("  be far worse than one refused, so the version check comes first")


if __name__ == "__main__":
    main()
