# ember

A programming language, implemented twice, with the machinery to prove the two agree.

`ember` is a complete implementation of a small dynamically typed language: a scanner, a
parser, a compiler that emits bytecode, a stack machine that runs it, and a second
tree-walking interpreter that runs the same syntax tree without compiling anything. The
second backend exists because it is the only way to tell whether the first one is right.
A compiler bug and a virtual machine bug look identical from outside, and having two
independent paths from source to output means a disagreement points at one of them.

```
let names = ["ada", "grace", "alan"];
for (let i = 0; i < len(names); i = i + 1) {
  print "hello, " + names[i];
}
```

```bash
python -m ember.cli run hello.ember
```

## What is here

| | |
| --- | --- |
| Front end | scanner, parser, 57 opcodes, compiler, constant pool, line table |
| Back ends | a stack machine and a tree-walking interpreter, differentially tested |
| Optimisers | tree folding, bytecode peephole, block level |
| Analysis | control flow graph, dominators, liveness, reachability, complexity, call graph |
| Checking | bytecode verifier, type checker, linter, coverage, profiler, tracer |
| Library | 460 functions across 31 libraries |
| Tooling | 22 command line subcommands, an assembler, a disassembler, a formatter, a REPL |
| Evidence | 5,320 tests and 24 traces |

## The claim each part makes

**Two back ends, compared on every program.** The stack machine compiles to bytecode and
dispatches instructions. The tree walker evaluates the syntax tree directly. Every
library test runs its expressions through both and compares the output, and a random
program generator feeds six configurations at once: the tree walker, plain bytecode, and
bytecode after each of the three optimisers, plus all of them together. An optimiser that
changes what a program means shows up as a disagreement rather than as a bug report six
months later. What this does not give is proof. Two implementations written by the same
hand can share a misconception, and agreement between them is evidence about the
implementations, not about the language definition.

**A verifier that is useless on purpose.** The bytecode verifier finds nothing in anything
this compiler emits, and one of the traces exists to check exactly that. It is there for
bytecode arriving from anywhere else: a saved file, an assembled listing, a hand edit. The
interesting part was making it survive malformed input. The first version raised a host
error on a chunk whose last instruction was missing its operand, which meant the tool for
reporting bad bytecode crashed on bad bytecode. It now reports a truncated operand and an
undecodable instruction as findings, because a checker that crashes is not a checker.

**Three optimisers that each buy something different.** Tree folding collapses constant
arithmetic before any bytecode exists and shrinks both the instruction stream and the
constant pool. The peephole pass rewrites instruction sequences and cannot touch the pool,
so a constant it makes unreachable stays there. The block pass works on the control flow
graph and is the only one that removes unreachable code. The examples print the byte and
constant counts side by side, and the honest reading is that folding does most of the work
on the programs anybody writes.

## Measurement kept its corrections

The design of most of this library was decided by measuring it against something
independent, and where a first attempt was wrong the wrong version is recorded beside the
right one in the module that holds it. A partial list, because these are the parts most
worth reading:

- Kahan summation loses a value entirely under cancellation. Summing `1e16`, `1.0`, and
  `-1e16` gave `0.0`. Neumaier summation gives `1.0`, and a test still records what Kahan
  does so nobody restores it.
- The Easter computus was wrong for all ten years first tested. The anonymous Gregorian
  algorithm replaced it and matches published dates for twelve out of twelve.
- The random library's weighted choice picked the heavy option 4,000 times out of 4,000.
  A raw xorshift seeded from small sequential integers produces tiny first outputs. Passing
  the seed through SplitMix64 gives a ratio of 2.93 against an expected 3.00.
- The queue returned its items in the wrong order. The classic banker's queue reversal is
  correct only when prepending, and this queue appends. Removing the reversal and checking
  3,000 random operations against the host's own deque gives zero differences.
- The generated library reference found two names claimed by two libraries each. The text
  library had redefined splitting a string into lines, the string library already provided
  it, and the two versions disagreed about a carriage return before a newline. Every test
  of both libraries passed the whole time. That is what the reference is for: nothing
  failed, and something was wrong.

## Traces

`python -m ember.cli traces` prints 24 recorded claims and whether each still holds.
A trace is not a test. A test asks whether a function returns what it should; a trace
states a property of the whole system in a sentence with numbers in it, and re-derives
those numbers every time it runs. The library trace reports that 443 functions across 31
libraries are each registered by exactly one of them, that no name is claimed twice, and
that every registered name reaches the machine. It found the collision above.

```bash
python -m ember.cli check
```

## The honest limits

There is no garbage collector. Values are host objects and the host collects them, which
means a cycle between two closures is the host's problem and not this machine's, and a
program that wants to know its own memory use cannot ask.

There are no user-defined types beyond classes with single inheritance, and no modules
beyond a single file. A program is one file, which keeps the compiler simple and makes
anything large unpleasant to write.

Instruction counts are not timings. The profiler counts what the machine dispatched, which
is reproducible and comparable, and one of the examples shows a native sort of three
hundred values costing two instructions. The count is a measure of work the machine did,
not of time anybody waited.

The regular expression engine has a step limit, and the limit cannot distinguish a slow
match from a runaway one. It refuses both. A legitimate pattern over a large enough subject
will be refused for looking like an attack, and that is a price this engine chooses to pay.

The type checker reports only mistakes that must fault, and is silent about anything
involving a function parameter, because a parameter has no declared type. Four separate
checks can all pass on a program that computes the wrong answer, because not one of them
knows what the program was supposed to compute.

## Running it

```bash
python -m pytest tests/ -q
python -m ember.cli check
python -m ember.cli names
python -m examples.first_program
```

The eleven example programs in `examples/` are each an essay that runs. They print their
measurements rather than asserting them, and every one closes by naming a cost, a limit, or
a refusal, which a test enforces.

`build_instructions.md` covers all of this in detail: what to install, every subcommand with
its output, the exit code each one uses, and what has not been tested.
