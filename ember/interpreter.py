"""The interpreter facade: one call that carries source all the way to a result.

The stages of this runtime, scanning, parsing, compiling, and executing,
are kept in separate modules so each can be understood alone, but almost
every user of the runtime wants all of them at once: give me source, run
it, tell me what it printed. This module is that front door. It threads a
program through the whole pipeline and hands back the machine that ran
it, so a caller can read the printed output and the instrumentation, the
instruction count and the deepest stack, without reassembling the stages
itself. Keeping the facade thin is the point. It adds no behavior of its
own beyond wiring, so that a test or a tool exercising the pipeline
exercises the real stages and not a parallel shortcut that could drift
from them. Two entry points are offered because two needs recur: one
returns the whole machine for a caller that wants to inspect its state,
and one returns just the list of printed lines for the common case of
checking what a program said. Both install the standard builtins by
default so that a program can reach the small library the language ships
with, and both accept turning that off for a test that wants the language
bare. Any failure along the way surfaces as the same exception family the
stages raise, so a caller catches one kind of error regardless of which
stage produced it.
"""

from __future__ import annotations

from ember.blockopt import optimise_deeply
from ember.builtins import install_builtins
from ember.compiler import compile_program
from ember.function import Function
from ember.modules import load_program
from ember.optimizer import optimize_program
from ember.parser import parse
from ember.peephole import optimize_function
from ember.scanner import scan
from ember.treewalk import TreeWalker
from ember.vm import VM


def build(
    source: str,
    optimize: bool = False,
    peephole: bool = False,
    blocks: bool = False,
    path: str | None = None,
) -> Function:
    """Compile source, optionally through each of the three optimisers.

    The optimisers are separate flags rather than one, because they work at
    different altitudes and each is worth being able to measure alone: the tree
    passes fold and prune what the program says, the peephole pass rewrites
    neighbouring instructions, and the block pass needs the whole control flow
    graph to remove what no path reaches. They run in that order, from the
    highest altitude to the lowest, so each sees what the one before left.
    Passing a path turns imports on, since an import names a file relative to the
    one importing it and a fragment with no path has no neighbours to name.
    """
    statements = load_program(source, path) if path is not None else parse(scan(source))
    if optimize:
        statements = optimize_program(statements)
    function = compile_program(statements)
    if peephole:
        optimize_function(function)
    if blocks:
        optimise_deeply(function)
    return function


def run(
    source: str,
    with_builtins: bool = True,
    optimize: bool = False,
    peephole: bool = False,
    blocks: bool = False,
    path: str | None = None,
) -> VM:
    function = build(
        source, optimize=optimize, peephole=peephole, blocks=blocks, path=path
    )
    machine = VM()
    if with_builtins:
        install_builtins(machine)
    machine.interpret(function)
    return machine


def run_output(
    source: str,
    with_builtins: bool = True,
    optimize: bool = False,
    peephole: bool = False,
    blocks: bool = False,
    path: str | None = None,
) -> list[str]:
    return run(
        source,
        with_builtins=with_builtins,
        optimize=optimize,
        peephole=peephole,
        blocks=blocks,
        path=path,
    ).output


def run_treewalk(
    source: str, with_builtins: bool = True, optimize: bool = False
) -> TreeWalker:
    walker = TreeWalker()
    if with_builtins:
        install_builtins(walker)
    statements = parse(scan(source))
    if optimize:
        statements = optimize_program(statements)
    walker.run(statements)
    return walker


def run_treewalk_output(
    source: str, with_builtins: bool = True, optimize: bool = False
) -> list[str]:
    return run_treewalk(source, with_builtins=with_builtins, optimize=optimize).output
