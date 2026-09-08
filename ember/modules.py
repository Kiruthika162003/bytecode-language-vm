"""Module loading: resolve imports into one program before anything is compiled.

A program that outgrows one file needs a way to name another, and there are two
honest ways to provide it. One gives every file its own namespace and makes the
machine resolve a global against the module that owns the function using it,
which is the better design and a substantial change to every global instruction.
The other resolves imports before compiling, splicing each imported file's
statements into one program, which is what this module does. That choice is worth
stating plainly because its weakness is real: all files share one global
namespace, so two modules that happen to declare the same name would collide.
Rather than let the second silently win, the loader computes what each file
declares at its top level and refuses a collision by naming both files, which
turns the design's weakness from a source of baffling bugs into an error at load
time. Three other rules make repeated imports safe. A file is loaded once
however many files import it, so a diamond of dependencies does not run anything
twice. A cycle is refused with the chain that formed it, because splicing a cycle
has no meaning and looping forever would be the alternative. And a path is
resolved relative to the file doing the importing rather than to the working
directory, so a module can be moved with its neighbours and still find them. The
statements come back in dependency order, every import before the file that
needed it, which is what lets the ordinary top-to-bottom compiler handle the
result without knowing modules exist at all.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from ember import stmtnodes as s
from ember.errors import Resolve
from ember.parser import parse
from ember.scanner import scan

SUFFIX = ".ember"


def declared_names(statements: list[s.Stmt]) -> dict[str, int]:
    """The names a file binds at its top level, with the line each was bound on."""
    names: dict[str, int] = {}
    for statement in statements:
        if isinstance(statement, (s.LetStmt, s.FunctionStmt, s.ClassStmt)):
            names.setdefault(statement.name.lexeme, statement.name.line)
    return names


@dataclass
class LoadReport:
    """What the loader did, so a caller can see the graph it walked."""

    order: list[str] = field(default_factory=list)
    owners: dict[str, str] = field(default_factory=dict)

    @property
    def files(self) -> int:
        return len(self.order)


class Loader:
    def __init__(self, read: object | None = None) -> None:
        # the reader is injectable so a caller can supply files from memory, which
        # is what lets the tests describe a module graph without touching a disk
        self._read = read
        self._loaded: set[str] = set()
        self._stack: list[str] = []
        self.report = LoadReport()

    def _read_text(self, path: Path) -> str:
        if self._read is not None:
            return self._read(str(path))  # type: ignore[operator]
        if not path.exists():
            raise Resolve(
                f"there is no file at {path}; an import names a file relative to the "
                "one importing it"
            )
        return path.read_text(encoding="utf-8")

    def _resolve(self, raw: str, importer: Path) -> Path:
        target = Path(raw)
        if not target.suffix:
            target = target.with_suffix(SUFFIX)
        if target.is_absolute():
            return target
        return (importer.parent / target).resolve()

    def load(self, source: str, path: str | Path = "main.ember") -> list[s.Stmt]:
        root = Path(path).resolve()
        return self._expand(parse(scan(source)), root)

    def _expand(self, statements: list[s.Stmt], path: Path) -> list[s.Stmt]:
        key = str(path)
        self._loaded.add(key)
        self._stack.append(key)
        self.report.order.append(key)
        self._claim(statements, key)
        expanded: list[s.Stmt] = []
        for statement in statements:
            if not isinstance(statement, s.ImportStmt):
                expanded.append(statement)
                continue
            expanded.extend(self._import(statement, path))
        self._stack.pop()
        return expanded

    def _import(self, statement: s.ImportStmt, importer: Path) -> list[s.Stmt]:
        target = self._resolve(statement.path, importer)
        key = str(target)
        if key in self._stack:
            chain = " -> ".join(Path(entry).name for entry in [*self._stack, key])
            raise Resolve(
                f"the imports form a cycle: {chain}; splicing a cycle has no meaning, "
                "so one of these imports must be removed"
            )
        if key in self._loaded:
            # already spliced in by an earlier import, so nothing runs twice
            return []
        text = self._read_text(target)
        return self._expand(parse(scan(text)), target)

    def _claim(self, statements: list[s.Stmt], key: str) -> None:
        for name, line in declared_names(statements).items():
            owner = self.report.owners.get(name)
            if owner is not None and owner != key:
                raise Resolve(
                    f"both {Path(owner).name} and {Path(key).name} declare {name!r} at "
                    f"their top level, and imported files share one global namespace, "
                    f"so the one on line {line} would replace the other; rename one"
                )
            self.report.owners[name] = key


def load_program(
    source: str, path: str | Path = "main.ember", read: object | None = None
) -> list[s.Stmt]:
    return Loader(read=read).load(source, path)


def load_with_report(
    source: str, path: str | Path = "main.ember", read: object | None = None
) -> tuple[list[s.Stmt], LoadReport]:
    loader = Loader(read=read)
    statements = loader.load(source, path)
    return statements, loader.report
