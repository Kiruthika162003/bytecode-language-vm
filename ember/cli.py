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
  format <file>       print the program in one canonical layout
  lint <file>         report what compiles but a reader would question
  verify <file>       check the emitted bytecode is well formed
  test <file>         run the program's test functions and report which held
  coverage <file>     run the program and report which lines never ran
  docs <file>         print a reference of what the program declares
  types <file>        report the definite type mistakes a program contains
  step <file>         show what the machine did, instruction by instruction
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


def _execute(source: str, path: str | None = None) -> int:
    from ember.errors import EmberError
    from ember.interpreter import run

    try:
        machine = run(source, path=path)
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


def _format(source: str) -> int:
    from ember.errors import EmberError
    from ember.formatter import format_program
    from ember.parser import parse
    from ember.scanner import scan

    try:
        statements = parse(scan(source))
    except EmberError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    print(format_program(statements), end="")
    return 0


def _step(source: str) -> int:
    from ember.errors import EmberError
    from ember.tracer import trace

    try:
        record = trace(source, cap=2000)
    except EmberError as error:
        # a program that never compiled has no trace; a runtime fault is in one
        print(f"error: {error}", file=sys.stderr)
        return 1
    for line in record.render(limit=200):
        print(line)
    if record.output:
        print()
        print("what it printed:")
        for printed in record.output:
            print("  " + printed)
    return 1 if record.refused else 0


def _types(source: str) -> int:
    from ember.errors import EmberError
    from ember.typecheck import check, report

    try:
        lines = report(source)
    except EmberError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    for line in lines:
        print(line)
    # a definite type mistake will fault at runtime, so it fails the command
    return 1 if check(source) else 0


def _docs(source: str) -> int:
    from ember.docgen import coverage_of, render
    from ember.errors import EmberError

    try:
        text = render(source)
    except EmberError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    if not text:
        print("this program declares nothing at its top level")
        return 0
    print(text)
    print()
    print(f"{coverage_of(source)} percent of the declarations carry a comment")
    return 0


def _test(source: str) -> int:
    from ember.errors import EmberError
    from ember.testrunner import run_suite

    try:
        suite = run_suite(source)
    except EmberError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    for line in suite.render():
        print(line)
    # a failing test is a failing command, which is what a build needs from it
    return 0 if suite.all_held else 1


def _coverage(source: str) -> int:
    from ember.coverage import measure
    from ember.errors import EmberError

    try:
        report = measure(source)
    except EmberError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    for line in report.render(source):
        print(line)
    # coverage is information, not a verdict, so an incomplete report still succeeds
    return 0


def _verify(source: str) -> int:
    from ember.errors import EmberError
    from ember.interpreter import build
    from ember.verifier import faults_deeply, verify_deeply

    try:
        function = build(source)
    except EmberError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    found = verify_deeply(function)
    if not found:
        print("the bytecode is well formed")
        return 0
    for problem in found:
        print(problem.render())
    print()
    bad = len(faults_deeply(function))
    noun = "problem" if len(found) == 1 else "problems"
    print(f"{len(found)} {noun}, {bad} of them faults")
    # only a fault means the machine would misbehave, so only a fault fails
    return 1 if bad else 0


def _lint(source: str) -> int:
    from ember.analyzer import analyze
    from ember.errors import EmberError
    from ember.parser import parse
    from ember.scanner import scan

    try:
        statements = parse(scan(source))
    except EmberError as error:
        print(f"error: {error}", file=sys.stderr)
        return 1
    found = analyze(statements)
    if not found:
        print("nothing to report")
        return 0
    for diagnostic in found:
        print(diagnostic.render())
    print()
    print(f"{len(found)} diagnostics")
    # a diagnostic is advice, not a failure, so the status stays zero and a
    # linter that refused to let code run is a linter people turn off
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
    if command in (
        "run",
        "eval",
        "disassemble",
        "optimized",
        "profile",
        "format",
        "lint",
        "verify",
        "test",
        "coverage",
        "docs",
        "types",
        "step",
    ):
        if not rest:
            print(f"{command} needs an argument", file=sys.stderr)
            return 2
        if command == "eval":
            return _execute(rest[0])
        source = _read(rest[0])
        if source is None:
            return 2
        if command == "run":
            # a file may import its neighbours, so the path travels with the source
            return _execute(source, path=rest[0])
        if command == "profile":
            return _profile(source)
        if command == "format":
            return _format(source)
        if command == "lint":
            return _lint(source)
        if command == "verify":
            return _verify(source)
        if command == "test":
            return _test(source)
        if command == "coverage":
            return _coverage(source)
        if command == "docs":
            return _docs(source)
        if command == "types":
            return _types(source)
        if command == "step":
            return _step(source)
        return _disassemble(source, optimize=command == "optimized")
    print(f"unknown command {command!r}\n\n{_USAGE}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
