"""Points, segments and polygons in the plane, with the degenerate cases decided.

Plane geometry is mostly arithmetic, and where it goes wrong is the cases that are almost
something else: three points nearly in a line, two segments touching at an endpoint, a point
exactly on a polygon's edge. Every one of those has to be decided one way, and the decisions
here are written down because a caller cannot guess them and a program silently disagreeing
with its geometry library is very hard to debug.

The cross product does the work. For three points, the sign of the cross product of the two
vectors between them says whether the turn is left, right, or straight, and almost everything
else follows: whether two segments cross, whether a polygon is wound clockwise, what its area
is, and which points form its hull. Computing it on integers is exact, which is why the
functions that answer a yes or no question do it that way where they can, and comparisons
against zero use a tolerance only when floats are involved.

The decisions. Three collinear points turn neither way, and that is reported as its own answer
rather than folded into one of the turns, because a caller asking about a turn usually needs to
know. Two segments that touch at an endpoint do intersect, since they share a point and
pretending otherwise makes a chain of segments have gaps at its joints. A point exactly on a
polygon's boundary counts as inside, which is the choice that makes a set of adjacent polygons
cover the plane without holes at their shared edges, and its cost is that two polygons sharing
an edge both contain the points on it. A polygon's area is returned unsigned with the winding
available separately, because a negative area surprises everyone who has not read this
paragraph.

Polygons are lists of points and points are lists of two numbers, so everything prints and
serialises like any other value. The convex hull uses the monotone chain method, sorting the
points and building the two halves, which costs the sorting and no more, and it returns the
hull without repeating the first point at the end: a caller drawing it closes the loop, and a
caller counting vertices should not have to know that one of them appears twice.
"""

from __future__ import annotations

import math
from typing import Any

from ember.errors import Arithmetic, TypeMismatch
from ember.valueops import type_name

_TOLERANCE = 1e-12

LEFT = "left"
RIGHT = "right"
STRAIGHT = "straight"


def _number(value: Any, who: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeMismatch(f"{who} needs numbers, and found a {type_name(value)}")
    return value


def _point(value: Any, who: str) -> tuple[float, float]:
    if not isinstance(value, list) or len(value) != 2:
        raise TypeMismatch(
            f"{who} needs a point as a list of two numbers, not a {type_name(value)}"
        )
    return _number(value[0], who), _number(value[1], who)


def _polygon(value: Any, who: str) -> list[tuple[float, float]]:
    if not isinstance(value, list):
        raise TypeMismatch(
            f"{who} needs a polygon as a list of points, not a {type_name(value)}"
        )
    if len(value) < 3:
        raise Arithmetic(
            f"{who} needs at least three points to make a polygon, and this has {len(value)}"
        )
    return [_point(one, who) for one in value]


def _points(value: Any, who: str) -> list[tuple[float, float]]:
    if not isinstance(value, list):
        raise TypeMismatch(f"{who} needs a list of points, not a {type_name(value)}")
    return [_point(one, who) for one in value]


def cross(
    first: tuple[float, float],
    second: tuple[float, float],
    third: tuple[float, float],
) -> float:
    """The cross product of the two vectors from the first point, which signs the turn."""
    return (second[0] - first[0]) * (third[1] - first[1]) - (second[1] - first[1]) * (
        third[0] - first[0]
    )


def _turn_of(args: list[Any]) -> str:
    first = _point(args[0], "turn")
    second = _point(args[1], "turn")
    third = _point(args[2], "turn")
    value = cross(first, second, third)
    if abs(value) <= _TOLERANCE:
        # collinear is its own answer rather than folded into a turn
        return STRAIGHT
    return LEFT if value > 0 else RIGHT


def _distance(args: list[Any]) -> float:
    first = _point(args[0], "distance")
    second = _point(args[1], "distance")
    return math.hypot(second[0] - first[0], second[1] - first[1])


def _squared_distance(args: list[Any]) -> float:
    """The distance without the square root, which stays exact on integers."""
    first = _point(args[0], "squaredDistance")
    second = _point(args[1], "squaredDistance")
    return (second[0] - first[0]) ** 2 + (second[1] - first[1]) ** 2


def _midpoint(args: list[Any]) -> list[float]:
    first = _point(args[0], "midpoint")
    second = _point(args[1], "midpoint")
    return [(first[0] + second[0]) / 2, (first[1] + second[1]) / 2]


def _on_segment(
    point: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
) -> bool:
    if abs(cross(start, end, point)) > _TOLERANCE:
        return False
    return (
        min(start[0], end[0]) - _TOLERANCE <= point[0] <= max(start[0], end[0]) + _TOLERANCE
        and min(start[1], end[1]) - _TOLERANCE <= point[1] <= max(start[1], end[1]) + _TOLERANCE
    )


def _point_on_segment(args: list[Any]) -> bool:
    point = _point(args[0], "onSegment")
    start = _point(args[1], "onSegment")
    end = _point(args[2], "onSegment")
    return _on_segment(point, start, end)


def _segments_cross(args: list[Any]) -> bool:
    """Whether two segments share any point, endpoints included."""
    first_start = _point(args[0], "segmentsCross")
    first_end = _point(args[1], "segmentsCross")
    second_start = _point(args[2], "segmentsCross")
    second_end = _point(args[3], "segmentsCross")
    one = cross(first_start, first_end, second_start)
    two = cross(first_start, first_end, second_end)
    three = cross(second_start, second_end, first_start)
    four = cross(second_start, second_end, first_end)
    straddles = (one > 0) != (two > 0) and (three > 0) != (four > 0)
    if straddles and abs(one) > _TOLERANCE and abs(two) > _TOLERANCE:
        return True
    # touching at an endpoint counts, so a chain of segments has no gaps at its joints
    return any(
        _on_segment(point, start, end)
        for point, start, end in (
            (second_start, first_start, first_end),
            (second_end, first_start, first_end),
            (first_start, second_start, second_end),
            (first_end, second_start, second_end),
        )
    )


def signed_area(corners: list[tuple[float, float]]) -> float:
    """Twice the area with a sign, which is the shoelace sum before halving."""
    total = 0.0
    for index, point in enumerate(corners):
        following = corners[(index + 1) % len(corners)]
        total += point[0] * following[1] - following[0] * point[1]
    return total / 2


def _area_of(args: list[Any]) -> float:
    """The area, unsigned, because a negative area surprises everyone."""
    return abs(signed_area(_polygon(args[0], "area")))


def _winding_of(args: list[Any]) -> str:
    corners = _polygon(args[0], "winding")
    area = signed_area(corners)
    if abs(area) <= _TOLERANCE:
        return STRAIGHT
    return LEFT if area > 0 else RIGHT


def _perimeter_of(args: list[Any]) -> float:
    corners = _polygon(args[0], "perimeter")
    total = 0.0
    for index, point in enumerate(corners):
        following = corners[(index + 1) % len(corners)]
        total += math.hypot(following[0] - point[0], following[1] - point[1])
    return total


def _centroid_of(args: list[Any]) -> list[float]:
    """The average of the corners, which is not the centre of area for a general shape."""
    corners = _polygon(args[0], "centroid")
    return [
        sum(point[0] for point in corners) / len(corners),
        sum(point[1] for point in corners) / len(corners),
    ]


def _inside_polygon(args: list[Any]) -> bool:
    """Whether a point is inside, counting the boundary as inside."""
    point = _point(args[0], "insidePolygon")
    corners = _polygon(args[1], "insidePolygon")
    for index, corner in enumerate(corners):
        following = corners[(index + 1) % len(corners)]
        if _on_segment(point, corner, following):
            # the boundary counts, so adjacent polygons cover the plane without holes
            return True
    inside = False
    for index, corner in enumerate(corners):
        following = corners[(index + 1) % len(corners)]
        crosses = (corner[1] > point[1]) != (following[1] > point[1])
        if not crosses:
            continue
        span = following[1] - corner[1]
        where = corner[0] + (point[1] - corner[1]) * (following[0] - corner[0]) / span
        if point[0] < where:
            inside = not inside
    return inside


def _bounding_box(args: list[Any]) -> list[list[float]]:
    corners = _points(args[0], "boundingBox")
    if not corners:
        raise Arithmetic("boundingBox needs at least one point")
    return [
        [min(point[0] for point in corners), min(point[1] for point in corners)],
        [max(point[0] for point in corners), max(point[1] for point in corners)],
    ]


def _convex_hull(args: list[Any]) -> list[list[float]]:
    """The monotone chain hull, costing the sorting and no more."""
    corners = sorted(set(_points(args[0], "convexHull")))
    if len(corners) < 3:
        return [list(point) for point in corners]
    lower: list[tuple[float, float]] = []
    for point in corners:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 0:
            lower.pop()
        lower.append(point)
    upper: list[tuple[float, float]] = []
    for point in reversed(corners):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 0:
            upper.pop()
        upper.append(point)
    # the last of each chain is the first of the other, so both are dropped once
    return [list(point) for point in lower[:-1] + upper[:-1]]


def _is_convex(args: list[Any]) -> bool:
    corners = _polygon(args[0], "isConvex")
    signs: set[bool] = set()
    for index in range(len(corners)):
        value = cross(
            corners[index],
            corners[(index + 1) % len(corners)],
            corners[(index + 2) % len(corners)],
        )
        if abs(value) > _TOLERANCE:
            signs.add(value > 0)
    return len(signs) <= 1


def _translated(args: list[Any]) -> list[list[float]]:
    corners = _points(args[0], "translated")
    by = _point(args[1], "translated")
    return [[point[0] + by[0], point[1] + by[1]] for point in corners]


def _scaled_about(args: list[Any]) -> list[list[float]]:
    corners = _points(args[0], "scaledAbout")
    about = _point(args[1], "scaledAbout")
    factor = _number(args[2], "scaledAbout")
    return [
        [about[0] + (point[0] - about[0]) * factor, about[1] + (point[1] - about[1]) * factor]
        for point in corners
    ]


def _rotated_about(args: list[Any]) -> list[list[float]]:
    corners = _points(args[0], "rotatedAbout")
    about = _point(args[1], "rotatedAbout")
    turns = _number(args[2], "rotatedAbout")
    angle = turns * 2 * math.pi
    cosine = math.cos(angle)
    sine = math.sin(angle)
    moved: list[list[float]] = []
    for point in corners:
        across = point[0] - about[0]
        up = point[1] - about[1]
        moved.append(
            [
                about[0] + across * cosine - up * sine,
                about[1] + across * sine + up * cosine,
            ]
        )
    return moved


_REGISTRY: dict[str, tuple[int, Any]] = {
    "turn": (3, _turn_of),
    "distance": (2, _distance),
    "squaredDistance": (2, _squared_distance),
    "midpoint": (2, _midpoint),
    "onSegment": (3, _point_on_segment),
    "segmentsCross": (4, _segments_cross),
    "area": (1, _area_of),
    "winding": (1, _winding_of),
    "perimeter": (1, _perimeter_of),
    "centroid": (1, _centroid_of),
    "insidePolygon": (2, _inside_polygon),
    "boundingBox": (1, _bounding_box),
    "convexHull": (1, _convex_hull),
    "isConvex": (1, _is_convex),
    "translated": (2, _translated),
    "scaledAbout": (3, _scaled_about),
    "rotatedAbout": (3, _rotated_about),
}


def install_geometry_library(machine: Any) -> None:
    for name, (arity, handler) in _REGISTRY.items():
        machine.define_native(name, arity, handler)


def geometry_names() -> list[str]:
    return sorted(_REGISTRY)
