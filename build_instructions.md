# Building and executing ember

## There is no build step

`ember` is pure Python and imports nothing outside the standard library. Every module
under `ember/` uses only `collections`, `dataclasses`, `enum`, `math`, `pathlib`,
`random`, `re`, `struct`, `sys`, and `typing`. There is no compile step, no code
generation, no native extension, and no lockfile, so "building" is cloning the repository
and running it in place.

```bash
git clone https://github.com/Kiruthika162003/bytecode-language-vm.git
cd bytecode-language-vm
python -m ember.cli eval 'print 1 + 2 * 3;'
```

That prints `7`. If it does, the runtime is working and nothing further is needed.

The one dependency is `pytest`, and only for running the test suite. The runtime itself
does not need it.

```bash
python -m pip install pytest
```

## Python version

`pyproject.toml` declares `requires-python = ">=3.11"`, which is the floor the syntax
targets. The only interpreter this has actually been measured on is CPython 3.14.5, so
treat 3.11 as declared rather than verified. Check what you have:

```bash
python --version
```

## Run everything from the repository root

There is no `tests/__init__.py`, and two test modules import each other through the
`tests.` prefix. That works because the interpreter puts the current directory on the
import path, which means the invocation form matters:

```bash
python -m pytest tests/ -q
```

Use `python -m pytest`, not a bare `pytest`. The bare command relies on a console script
being on `PATH` and does not reliably put the repository root on the import path, so the
example tests fail to import. This is a real fragility rather than a preference, and
naming it here is cheaper than debugging it later.

The same applies to the CLI. `python -m ember.cli` works from the repository root without
installing anything.

## Writing and running a program

A program is a single file. The conventional extension is `.ember`, which is what the
import resolver appends when an import names a file without one, but the CLI does not
require it and will read any path you give it.

Save this as `greet.ember`:

```
fn greet(name) {
  return "hello, " + name;
}

fn testGreetNamesTheCaller() {
  if (greet("ada") != "hello, ada") {
    throw "greet did not name the caller";
  }
}

print greet("ada");
```

```bash
python -m ember.cli run greet.ember
```

```
hello, ada
```

A function whose name begins with `test` is a test. The runner calls it with no arguments,
a return is a pass, and a thrown value is a failure. Each test runs on its own freshly
built machine, so one test cannot change what the next one sees.

```bash
python -m ember.cli test greet.ember
```

```
testGreetNamesTheCaller: passed
1 tests: 1 passed
```

## Every command

All 22 subcommands, each shown against the program above. The 16 that take a file argument
accept any readable path; `eval` takes source text directly; `repl`, `traces`, `check`,
`summary`, and `names` take nothing.

### Executing

| Command | What it does |
| --- | --- |
| `run <file>` | Compile and execute, printing the program's output |
| `eval <source>` | The same, on a source fragment given on the command line |
| `repl` | An interactive session, one statement at a time |

```bash
python -m ember.cli eval 'let xs = [3, 1, 2]; print sorted(xs);'
```

### Seeing the bytecode

| Command | What it does |
| --- | --- |
| `disassemble <file>` | The bytecode as emitted, with line numbers and the constant pool |
| `optimized <file>` | The same after the optimiser runs, for comparing the two |
| `assemble <file>` | The bytecode as assembly text, which the assembler reads back |
| `step <file>` | Every instruction the machine executed, with the stack at each one |
| `graph <file>` | The control flow graph in DOT format, for `dot` or any graph tool |

```bash
python -m ember.cli disassemble greet.ember
python -m ember.cli graph greet.ember > program.dot
```

### Checking before running

| Command | What it does |
| --- | --- |
| `verify <file>` | Whether the bytecode is well formed, separating faults from warnings |
| `types <file>` | The definite type mistakes, which are the ones that must fault |
| `lint <file>` | What compiles but a reader would question |
| `format <file>` | The program in one canonical layout |
| `docs <file>` | A reference of what the program declares |

```bash
python -m ember.cli types greet.ember
```

```
no definite type mistakes found, which is not a proof there are none
```

`verify` finds nothing in anything this compiler emits, and one of the traces exists to
check exactly that. It reports unreachable code as a warning rather than a fault, because
unreachable code is safe to run. It is there for bytecode arriving from elsewhere: a saved
file, an assembled listing, a hand edit.

### Measuring

| Command | What it does |
| --- | --- |
| `profile <file>` | Where the work went, counted by instruction and by function |
| `bench <file>` | Instruction counts under each optimiser setting, side by side |
| `coverage <file>` | Which emitted lines never ran |
| `holds <file>` | What the machine is still holding when the program ends |

```bash
python -m ember.cli bench greet.ember
```

Instruction counts are reproducible and comparable. They are not timings. A native sort of
three hundred values costs two instructions, so the count measures work the machine
dispatched rather than time anybody waited.

### Checking the implementation itself

| Command | What it does |
| --- | --- |
| `traces` | All 24 recorded claims and whether each still holds |
| `check` | Whether any trace is broken, for scripting |
| `summary` | How many traces there are |
| `names` | Every function the standard library provides, grouped by library |

```bash
python -m ember.cli check
```

```
all traces hold
```

## Exit codes

Measured, not assumed. They differ between commands in ways worth knowing before you put
one in a script:

| Code | When |
| --- | --- |
| `0` | Success, and also `lint` with diagnostics, and `verify` with warnings but no faults |
| `1` | A compile or runtime error, a failing test, a definite type mistake, a verifier fault, a broken trace |
| `2` | No command given, a command missing its argument, or a file that does not exist |

The asymmetry is deliberate. `lint` reports advice, so having something to say is not
failure. `verify` fails only on a fault, because only a fault means the machine would
misbehave. But it means `lint` cannot gate a build on its own, which is a real limitation:
to fail a build on lint output you have to check whether the output was `nothing to
report`.

## The full gate

This is the sequence to run before trusting a change. Each step is cheap and each catches
something the others do not.

```bash
python -m ruff check .
python -m pytest tests/ -q
python -m ember.cli check
```

Expected output, as of the last commit:

```
All checks passed!
5320 passed
all traces hold
```

`ruff` is the only development tool beyond `pytest`, configured in `pyproject.toml` at a
96 column line length targeting py311. Install it with `python -m pip install ruff`. It is
not needed to run anything.

## Running the examples

The eleven programs in `examples/` are essays that run. Each prints its measurements rather
than asserting them, and each closes by naming a cost, a limit, or a refusal.

```bash
python -m examples.first_program
python -m examples.two_backends
python -m examples.patterns_and_their_limits
python -m examples.where_the_cost_is
```

They are modules rather than scripts, so run them with `-m` from the repository root. A
test asserts that every module in `examples/` is covered by one of the two example test
lists, so a new example that nobody runs fails the suite.

## Saving and loading bytecode

There is no CLI subcommand for this, only a library API. Compiled bytecode round trips
through a byte string beginning with the magic number `EMBR`:

```python
from ember.bytecodeio import deserialize, serialize
from ember.interpreter import build

function = build('print "hello";')
data = serialize(function)
same = deserialize(data)
```

Loading refuses a wrong magic number and a wrong version rather than guessing, and the
remedy in both messages is to recompile the source. `python -m examples.saving_bytecode`
shows the round trip preserving the disassembly, the line table, and the output.

## Using it as a library

Nothing is installed, so add the repository root to the import path or work from inside it.

```python
from ember.interpreter import run_output, run_treewalk_output

print(run_output('print 1 + 2;'))          # the stack machine
print(run_treewalk_output('print 1 + 2;')) # the tree walker, for comparison
```

Both backends take the same source and return the same list of printed lines. Comparing
them is how the implementation checks itself, and it is available to anything built on top.

## What is not here

There is no packaging step and no installed entry point. `pyproject.toml` carries project
metadata and the `ruff` configuration, but no `[build-system]` table and no console script,
so `pip install .` has not been tested and there is no `ember` command on your `PATH`.
Every invocation goes through `python -m`.

There is no continuous integration configuration, no container image, and no cross platform
matrix. The commands above were run on Windows with Git Bash and CPython 3.14.5, and while
nothing in them is platform specific, that is the only environment they have been measured
in.
