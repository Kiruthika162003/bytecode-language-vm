"""The command line: run a program, inspect what it compiled to, or sweep the traces.

This is the front door for a person rather than for another module, and it
offers only what someone actually reaches for. Running a file or a fragment
executes it and prints what it printed. Disassembling shows the bytecode a
program compiled to, which is the fastest way to see whether the compiler did
what was expected, and it accepts the optimiser flag so the two forms can be
put side by side. The trace commands sweep the recorded claims: one prints
every claim with its verdict, one reports only whether anything is broken so
it can gate a commit, and one gives the count. Errors are handled the way a
tool should handle them rather than the way a library does: a fault in the
user's program is reported as a message and a non-zero exit status, not as a
stack trace of this runtime's own internals, since the reader's mistake is in
their program and showing them the machine's frames would bury that. A fault
in the runtime itself is deliberately left to propagate, because that one is
a bug here and its traceback is the useful thing.
"""

from __future__ import annotations

import sys
from pathlib import Path

_NEWLINE = chr(10)

_USAGE = """usage: python -m ember.cli <command> [argument]

  run <file>          execute a program file and print its output
  eval <source>       execute a source fragment and print its output
  disassemble <file>  show the bytecode a program compiles to
  optimized <file>    show the bytecode after the optimizer runs
  profile <file>      run a program and report where the work went
  repl                start an interactive session
  traces              print every recorded claim and whether it holds
  check               report whether any trace is broken
  summary             print how many traces there are
"""


def _read(path: str) -> str | None:
    # returns None rather than exiting, so main stays a function that reports a
    # status instead of one that sometimes terminates the process from inside
    location = Path(path)
    if not location.exists():
        print(f"there is no file at {path}", file=sys.stderr)
        return None
    return location.read_text(encoding="utf-8")


def _execute(source: str) -> int:
    from ember.errors import EmberError
    from ember.interpreter import run

    try:
        machine = run(source)
    except EmberError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    for line in machine.output:
        print(line)
    return 0


def _disassemble(source: str, optimize: bool) -> int:
    from ember.disassembler import disassemble
    from ember.errors import EmberError
    from ember.interpreter import build

    try:
        function = build(source, optimize=optimize)
    except EmberError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    label = "optimized" if optimize else "script"
    print(disassemble(function.chunk, label))
    return 0


def _profile(source: str) -> int:
    from ember.builtins import install_builtins
    from ember.errors import EmberError
    from ember.interpreter import build
    from ember.profiler import render
    from ember.vm import VM

    machine = VM()
    install_builtins(machine)
    profile = machine.enable_profiling()
    try:
        function = build(source)
        machine.interpret(function)
    except EmberError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    for line in machine.output:
        print(line)
    print()
    print(render(profile, source))
    return 0


def _repl() -> int:
    from ember.repl import Session, is_incomplete

    session = Session()
    print("ember session. an empty line cancels a pending input; ctrl-d ends it.")
    pending: list[str] = []
    while True:
        prompt = "... " if pending else ">>> "
        try:
            line = input(prompt)
        except EOFError:
            print()
            return 0
        if not line.strip() and pending:
            # an empty line abandons a half-written input rather than running it
            pending.clear()
            continue
        pending.append(line)
        source = _NEWLINE.join(pending)
        if is_incomplete(source):
            continue
        pending.clear()
        printed, error = session.evaluate_safely(source)
        for output in printed:
            print(output)
        if error is not None:
            print(f"error: {error}", file=sys.stderr)


def _traces() -> int:
    from ember.traces.registry import broken, run_all

    findings = run_all()
    for finding in findings:
        print(finding.render())
    failures = broken(findings)
    print(f"\n{len(findings)} traces, {len(failures)} broken")
    return 1 if failures else 0


def _check() -> int:
    from ember.traces.registry import broken

    failures = broken()
    if not failures:
        print("all traces hold")
        return 0
    for finding in failures:
        print(finding.render(), file=sys.stderr)
    return 1


def _summary() -> int:
    from ember.traces.registry import TRACES, broken

    print(f"{len(TRACES)} traces ({len(broken())} broken)")
    return 0


def main(argv: list[str] | None = None) -> int:
    arguments = list(sys.argv[1:] if argv is None else argv)
    if not arguments:
        print(_USAGE, file=sys.stderr)
        return 2
    command = arguments[0]
    rest = arguments[1:]
    if command == "traces":
        return _traces()
    if command == "check":
        return _check()
    if command == "summary":
        return _summary()
    if command == "repl":
        return _repl()
    if command in ("run", "eval", "disassemble", "optimized", "profile"):
        if not rest:
            print(f"{command} needs an argument", file=sys.stderr)
            return 2
        if command == "eval":
            return _execute(rest[0])
        source = _read(rest[0])
        if source is None:
            return 2
        if command == "run":
            return _execute(source)
        if command == "profile":
            return _profile(source)
        return _disassemble(source, optimize=command == "optimized")
    print(f"unknown command {command!r}\n\n{_USAGE}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
