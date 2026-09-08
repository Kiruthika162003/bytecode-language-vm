"""Ember: a small bytecode-compiled scripting language and the machine that runs it.

The package is organized as a pipeline. Source text is scanned into
tokens, tokens are parsed into a syntax tree, the tree is resolved and
compiled to bytecode, and a stack virtual machine executes the
bytecode. Each stage lives in its own set of modules so that a stage
can be read, tested, and reasoned about without dragging the whole
runtime along. The supporting machinery, the value model, the hash
table, the interner, the garbage collector, and the standard builtins,
lives beside the pipeline and is likewise separable.
"""

from __future__ import annotations

__version__ = "0.1.0"
