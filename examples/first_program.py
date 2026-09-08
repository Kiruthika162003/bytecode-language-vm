"""A first program, followed through every stage from text to output.

The pipeline is easy to describe and easy to lose track of, so this example
takes six words of source and shows what each stage makes of them. The scanner
turns the text into tokens, which is where a keyword stops being a run of
letters and becomes a decision. The parser folds that flat list into a tree,
which is where precedence stops being a rule in a table and becomes a shape.
The compiler flattens the tree into bytecode, which is where the shape becomes
an order of operations. And the machine runs the bytecode. Printing all four
side by side makes one thing visible that reading the code does not: the
program shrinks at every stage except the last, from characters to a handful of
tokens to a smaller tree to a dozen bytes. The honest note this example ends on
is that the shrinking is not compression but discarding. Whitespace, comments,
and the exact spelling of the grouping are gone by the time the bytecode
exists, which is why the formatter can print the tree back as source but can
never print back the source that was written.
"""

from __future__ import annotations

from ember.disassembler import disassemble
from ember.interpreter import build, run
from ember.parser import parse
from ember.scanner import scan

SOURCE = "let total = 1 + 2 * 3;"


def main() -> None:
    print("source:")
    print(f"  {SOURCE}")

    tokens = scan(SOURCE)
    print(f"scanned into {len(tokens)} tokens (the last is the end marker):")
    print("  " + " ".join(token.kind.name for token in tokens))

    statements = parse(tokens)
    declaration = statements[0]
    print(f"parsed into {len(statements)} statement, a {type(declaration).__name__}")
    print(f"  the name it binds is {declaration.name.lexeme!r}")
    print("  its value is a tree, not a list, so precedence is already settled")

    function = build(SOURCE)
    print(f"compiled to {len(function.chunk.code)} bytes with "
          f"{len(function.chunk.constants)} constants:")
    for line in disassemble(function.chunk, "script").splitlines()[1:]:
        print(f"  {line}")

    machine = run(SOURCE + " print total;")
    print(f"run: printed {machine.output} in {machine.instruction_count} instructions")

    print()
    print("what the stages cost, honestly:")
    print(f"  {len(SOURCE)} characters became {len(tokens)} tokens "
          f"became {len(function.chunk.code)} bytes")
    print("  but that is discarding, not compression: the spacing, any comments,")
    print("  and the exact grouping are gone, which is why the tree can be printed")
    print("  back as source and the original text cannot be recovered from it")


if __name__ == "__main__":
    main()
