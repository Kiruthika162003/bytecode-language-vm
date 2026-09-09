"""A reference for the standard library, generated from the library rather than written.

The library grew one module at a time and is now large enough that nobody, including
whoever wrote it, can list what is in it. A written reference would be out of date the day
after it was written, which is the usual fate of hand maintained documentation, so this one
is generated from the registries the libraries already keep. Adding a native to a library
adds it to the reference, and removing one removes it, without anybody remembering to.

Grouping by library is what makes it readable, and it is also the only grouping
available: a native knows its name and its arity and nothing else, so the module it was
registered in is the only fact about it beyond its signature. That turns out to be a good
grouping anyway, because a library is a set of functions someone chose to put together.

The one thing this reference cannot give is what each function does. A native is a host function
with a docstring the language cannot see, and threading those through the registries would mean
every library carrying prose it never uses at runtime. What is offered instead is the shape,
which answers the questions a reference is usually consulted for: does this exist, what is it
called, and how many arguments does it take. Anything more is in the module that defines it.

A check comes with the listing, because a reference generated from registries can be
wrong in one specific way: two libraries registering the same name, where whichever
installs last silently wins. The first run of this found two: the text library had
redefined repeating a string and splitting one into lines, both of which the core string
library already provided, and the two versions of splitting into lines did not even agree
about a carriage return. Nothing had failed, because both versions passed the obvious
tests. So the reference reports collisions, the duplicates are gone, and a test pins the
count at zero.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ember.bitlib import bit_names
from ember.builtins import builtin_names
from ember.chartlib import chart_names
from ember.csvlib import csv_names
from ember.datelib import date_names
from ember.difflib import diff_names
from ember.encodelib import encode_names
from ember.fraclib import fraction_names
from ember.geometrylib import geometry_names
from ember.hashlib import hash_names
from ember.heaplib import heap_names
from ember.higherorder import higher_order_names
from ember.intervallib import interval_names
from ember.jsonlib import json_names
from ember.listlib import list_names
from ember.maplib import map_names
from ember.mathlib import math_names
from ember.matrixlib import matrix_names
from ember.prettylib import pretty_names
from ember.queuelib import queue_names
from ember.randomlib import random_names
from ember.regexlib import regex_names
from ember.schemalib import schema_names
from ember.setlib import set_names
from ember.sortlib import sort_names
from ember.statelib import state_names
from ember.statlib import stat_names
from ember.stringlib import string_names
from ember.textlib import text_names
from ember.unitlib import unit_names
from ember.versionlib import version_names

_LIBRARIES = {
    "bits": bit_names,
    "charts": chart_names,
    "comma separated values": csv_names,
    "dates": date_names,
    "differences": diff_names,
    "encodings": encode_names,
    "fractions": fraction_names,
    "geometry": geometry_names,
    "hashes": hash_names,
    "heaps": heap_names,
    "higher order": higher_order_names,
    "intervals": interval_names,
    "json": json_names,
    "lists": list_names,
    "maps": map_names,
    "mathematics": math_names,
    "matrices": matrix_names,
    "patterns": regex_names,
    "pretty printing": pretty_names,
    "queues": queue_names,
    "random": random_names,
    "schemas": schema_names,
    "sets": set_names,
    "sorting": sort_names,
    "state machines": state_names,
    "statistics": stat_names,
    "strings": string_names,
    "text": text_names,
    "units": unit_names,
    "versions": version_names,
}


@dataclass
class Reference:
    """Every library, what it registers, and any name two libraries both claim."""

    libraries: dict[str, list[str]] = field(default_factory=dict)
    collisions: dict[str, list[str]] = field(default_factory=dict)

    @property
    def total(self) -> int:
        return sum(len(names) for names in self.libraries.values())

    @property
    def library_count(self) -> int:
        return len(self.libraries)

    def library_of(self, name: str) -> str | None:
        for library, names in self.libraries.items():
            if name in names:
                return library
        return None

    def largest(self) -> tuple[str, int]:
        if not self.libraries:
            return ("", 0)
        found = max(self.libraries.items(), key=lambda pair: (len(pair[1]), pair[0]))
        return (found[0], len(found[1]))

    def render(self) -> list[str]:
        lines: list[str] = []
        for library in sorted(self.libraries):
            names = self.libraries[library]
            lines.append(f"{library} ({len(names)})")
            lines.append("  " + ", ".join(names))
        lines.append("")
        lines.append(
            f"{self.total} functions across {self.library_count} libraries"
        )
        for name, claimants in sorted(self.collisions.items()):
            lines.append(f"{name} is registered by {' and '.join(claimants)}")
        return lines


def reference() -> Reference:
    """Read the registries, and notice any name two of them both claim."""
    found = Reference()
    claimed: dict[str, list[str]] = {}
    for library, lister in _LIBRARIES.items():
        names = lister()
        found.libraries[library] = names
        for name in names:
            claimed.setdefault(name, []).append(library)
    # whichever library installs last silently wins, so a repeat is a real problem
    found.collisions = {
        name: libraries for name, libraries in claimed.items() if len(libraries) > 1
    }
    return found


def unlisted() -> list[str]:
    """Natives the machine has that no library here claims, which the core supplies."""
    listed: set[str] = set()
    for lister in _LIBRARIES.values():
        listed |= set(lister())
    return sorted(set(builtin_names()) - listed)


def missing_from_machine() -> list[str]:
    """Names a library registers that the machine does not end up with."""
    listed: set[str] = set()
    for lister in _LIBRARIES.values():
        listed |= set(lister())
    return sorted(listed - set(builtin_names()))


def render() -> str:
    return chr(10).join(reference().render())
