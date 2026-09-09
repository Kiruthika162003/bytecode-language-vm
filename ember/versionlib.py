"""Version numbers: comparing them correctly, which string comparison does not.

Comparing versions as text is wrong in a way that stays hidden until the tenth release. Version
ten comes before version nine alphabetically, and every project that compared its versions as
strings discovered this the day it shipped a tenth of something. The fix is to compare the parts
numerically, and the parts are what a version format defines.

The format here is the common three part one: a major, a minor and a patch number, optionally
followed by a prerelease marker after a hyphen and build metadata after a plus. Those two
suffixes have opposite behaviours, which is the part worth writing down. A prerelease sorts
before the release it precedes, so a version with a prerelease marker is always below the same
version without one, which is what makes an alpha come before the release rather than after it.
Build metadata is ignored entirely in comparison, so two versions differing only in their build
are equal, because the metadata records where a build came from rather than what it contains.

Comparing prerelease markers themselves follows the same rule as the numbers, applied to the
dot separated parts: a part that is all digits compares numerically against another such part,
and anything else compares as text, with a numeric part sorting below a textual one. A version
with fewer prerelease parts sorts below one that shares its prefix and has more, so alpha comes
before alpha dot one. Those rules look arbitrary written down and each of them exists because
the obvious alternative orders some real pair of versions wrongly.

Strictness on the way in is deliberate. A version missing its patch number is refused rather
than assumed to be zero, because a program comparing two versions where one was guessed at is
comparing something nobody wrote. A caller with a two part version can say what it means by
adding the zero, which takes one line and is then visible.
"""

from __future__ import annotations

from typing import Any

from ember.errors import Arithmetic, TypeMismatch
from ember.valueops import type_name


def _text(value: Any, who: str) -> str:
    if not isinstance(value, str):
        raise TypeMismatch(f"{who} needs a version as a string, not a {type_name(value)}")
    return value


def parse_version(text: str) -> tuple[int, int, int, str, str]:
    """The three numbers, the prerelease marker, and the build metadata."""
    rest = text.strip()
    if not rest:
        raise Arithmetic("a version cannot be empty")
    build = ""
    if "+" in rest:
        rest, _, build = rest.partition("+")
        if not build:
            raise Arithmetic(f"{text!r} ends with a plus and no build metadata")
    prerelease = ""
    if "-" in rest:
        rest, _, prerelease = rest.partition("-")
        if not prerelease:
            raise Arithmetic(f"{text!r} ends with a hyphen and no prerelease marker")
    parts = rest.split(".")
    if len(parts) != 3:
        raise Arithmetic(
            f"a version has three numbers separated by dots, and {text!r} has "
            f"{len(parts)}; a two part version can say what it means by adding the zero"
        )
    numbers: list[int] = []
    for part in parts:
        if not part.isdigit():
            raise Arithmetic(f"{part!r} in {text!r} is not a number")
        numbers.append(int(part))
    return numbers[0], numbers[1], numbers[2], prerelease, build


def _prerelease_parts(marker: str) -> list[str]:
    return marker.split(".") if marker else []


def _compare_part(left: str, right: str) -> int:
    """A numeric part compares numerically and sorts below a textual one."""
    left_numeric = left.isdigit()
    right_numeric = right.isdigit()
    if left_numeric and right_numeric:
        return (int(left) > int(right)) - (int(left) < int(right))
    if left_numeric != right_numeric:
        # a numeric part sorts below a textual one
        return -1 if left_numeric else 1
    return (left > right) - (left < right)


def _compare_prerelease(left: str, right: str) -> int:
    if left == right:
        return 0
    if not left:
        # no marker means the release itself, which sorts above any prerelease of it
        return 1
    if not right:
        return -1
    ours = _prerelease_parts(left)
    theirs = _prerelease_parts(right)
    for one, other in zip(ours, theirs, strict=False):
        found = _compare_part(one, other)
        if found:
            return found
    # a shorter marker sorts below a longer one sharing its prefix
    return (len(ours) > len(theirs)) - (len(ours) < len(theirs))


def compare_versions(left: str, right: str) -> int:
    ours = parse_version(left)
    theirs = parse_version(right)
    for one, other in zip(ours[:3], theirs[:3], strict=True):
        if one != other:
            return -1 if one < other else 1
    return _compare_prerelease(ours[3], theirs[3])


def _parse(args: list[Any]) -> list[Any]:
    major, minor, patch, prerelease, build = parse_version(_text(args[0], "parseVersion"))
    return [major, minor, patch, prerelease, build]


def _compare(args: list[Any]) -> int:
    left = _text(args[0], "compareVersions")
    right = _text(args[1], "compareVersions")
    return compare_versions(left, right)


def _before(args: list[Any]) -> bool:
    return _compare(args) < 0


def _after(args: list[Any]) -> bool:
    return _compare(args) > 0


def _same(args: list[Any]) -> bool:
    """Equal when everything but the build metadata matches, since that is ignored."""
    return _compare(args) == 0


def _is_valid(args: list[Any]) -> bool:
    try:
        parse_version(_text(args[0], "isVersion"))
    except (Arithmetic, TypeMismatch):
        return False
    return True


def _is_prerelease(args: list[Any]) -> bool:
    return bool(parse_version(_text(args[0], "isPrerelease"))[3])


def _major_of(args: list[Any]) -> int:
    return parse_version(_text(args[0], "majorOf"))[0]


def _minor_of(args: list[Any]) -> int:
    return parse_version(_text(args[0], "minorOf"))[1]


def _patch_of(args: list[Any]) -> int:
    return parse_version(_text(args[0], "patchOf"))[2]


def _next_major(args: list[Any]) -> str:
    major, _, _, _, _ = parse_version(_text(args[0], "nextMajor"))
    return f"{major + 1}.0.0"


def _next_minor(args: list[Any]) -> str:
    major, minor, _, _, _ = parse_version(_text(args[0], "nextMinor"))
    return f"{major}.{minor + 1}.0"


def _next_patch(args: list[Any]) -> str:
    major, minor, patch, _, _ = parse_version(_text(args[0], "nextPatch"))
    return f"{major}.{minor}.{patch + 1}"


def _sorted_versions(args: list[Any]) -> list[str]:
    values = args[0]
    if not isinstance(values, list):
        raise TypeMismatch(f"sortedVersions needs a list, not a {type_name(values)}")
    texts = [_text(one, "sortedVersions") for one in values]
    # every version is parsed before any is compared. Validating lazily meant a list
    # of one was never checked at all, because nothing is compared against a single
    # element, so an unparseable version sorted quietly into a list of itself.
    for one in texts:
        parse_version(one)
    # an insertion sort using the comparison, since the natural order is wrong here
    ordered: list[str] = []
    for one in texts:
        at = 0
        while at < len(ordered) and compare_versions(ordered[at], one) <= 0:
            at += 1
        ordered.insert(at, one)
    return ordered


def _latest(args: list[Any]) -> str:
    ordered = _sorted_versions(args)
    if not ordered:
        raise Arithmetic("latestVersion has nothing to choose from")
    return ordered[-1]


def _satisfies(args: list[Any]) -> bool:
    """Whether a version shares a floor's major number and is at least the floor.

    The first version of this said below the next major rather than sharing the major,
    which reads the same and is not. A prerelease of the next major is below the next
    major, so a version like two point zero alpha counted as compatible with a floor of
    one, which is the opposite of what a major number promises. Comparing the major
    numbers directly says what was meant and has no such edge.
    """
    version = _text(args[0], "compatibleWith")
    floor = _text(args[1], "compatibleWith")
    if parse_version(version)[0] != parse_version(floor)[0]:
        return False
    return compare_versions(version, floor) >= 0


_REGISTRY: dict[str, tuple[int, Any]] = {
    "parseVersion": (1, _parse),
    "compareVersions": (2, _compare),
    "versionBefore": (2, _before),
    "versionAfter": (2, _after),
    "sameVersion": (2, _same),
    "isVersion": (1, _is_valid),
    "isPrerelease": (1, _is_prerelease),
    "majorOf": (1, _major_of),
    "minorOf": (1, _minor_of),
    "patchOf": (1, _patch_of),
    "nextMajor": (1, _next_major),
    "nextMinor": (1, _next_minor),
    "nextPatch": (1, _next_patch),
    "sortedVersions": (1, _sorted_versions),
    "latestVersion": (1, _latest),
    "compatibleWith": (2, _satisfies),
}


def install_version_library(machine: Any) -> None:
    for name, (arity, handler) in _REGISTRY.items():
        machine.define_native(name, arity, handler)


def version_names() -> list[str]:
    return sorted(_REGISTRY)
