from __future__ import annotations

import math

import pytest

from ember.errors import Arithmetic, TypeMismatch
from ember.geometrylib import (
    LEFT,
    RIGHT,
    STRAIGHT,
    cross,
    geometry_names,
    signed_area,
)
from ember.interpreter import run_output, run_treewalk_output

SQUARE = "[[0, 0], [4, 0], [4, 4], [0, 4]]"
CLOCKWISE = "[[0, 0], [0, 4], [4, 4], [4, 0]]"
TRIANGLE = "[[0, 0], [4, 0], [0, 3]]"
CONCAVE = "[[0, 0], [4, 0], [1, 1], [0, 4]]"


def evaluate(expression: str) -> str:
    return run_output(f"print {expression};")[0]


class TestRegistration:
    def test_the_functions_are_named(self):
        assert "turn" in geometry_names()
        assert "convexHull" in geometry_names()

    def test_the_names_are_sorted(self):
        assert geometry_names() == sorted(geometry_names())

    def test_there_are_seventeen_of_them(self):
        assert len(geometry_names()) == 17


class TestTurns:
    def test_a_left_turn_is_recognised(self):
        assert evaluate("turn([0, 0], [1, 0], [1, 1])") == LEFT

    def test_a_right_turn_is_recognised(self):
        assert evaluate("turn([0, 0], [1, 0], [1, -1])") == RIGHT

    def test_collinear_points_turn_neither_way(self):
        # its own answer rather than folded into a turn
        assert evaluate("turn([0, 0], [1, 1], [2, 2])") == STRAIGHT

    def test_repeated_points_are_collinear(self):
        assert evaluate("turn([0, 0], [0, 0], [1, 1])") == STRAIGHT

    def test_the_cross_product_signs_the_turn(self):
        assert cross((0, 0), (1, 0), (1, 1)) > 0
        assert cross((0, 0), (1, 0), (1, -1)) < 0
        assert cross((0, 0), (1, 1), (2, 2)) == 0

    def test_the_cross_product_is_exact_on_integers(self):
        assert cross((0, 0), (3, 0), (0, 4)) == 12


class TestDistances:
    def test_a_familiar_triangle(self):
        assert evaluate("distance([0, 0], [3, 4])") == "5.0"

    def test_the_distance_to_itself_is_zero(self):
        assert evaluate("distance([2, 2], [2, 2])") == "0.0"

    def test_the_squared_distance_stays_exact(self):
        # no square root, so integers stay integers
        assert evaluate("squaredDistance([0, 0], [3, 4])") == "25"

    def test_the_midpoint_is_halfway(self):
        assert evaluate("midpoint([0, 0], [4, 4])") == "[2.0, 2.0]"

    def test_the_midpoint_of_a_point_is_itself(self):
        assert evaluate("midpoint([1, 1], [1, 1])") == "[1.0, 1.0]"


class TestSegments:
    def test_a_point_on_a_segment_is_recognised(self):
        assert evaluate("onSegment([2, 0], [0, 0], [4, 0])") == "true"

    def test_a_point_off_the_line_is_not(self):
        assert evaluate("onSegment([2, 1], [0, 0], [4, 0])") == "false"

    def test_a_point_past_the_end_is_not(self):
        assert evaluate("onSegment([5, 0], [0, 0], [4, 0])") == "false"

    def test_an_endpoint_is_on_the_segment(self):
        assert evaluate("onSegment([0, 0], [0, 0], [4, 0])") == "true"

    def test_two_crossing_segments_cross(self):
        assert evaluate("segmentsCross([0, 0], [2, 2], [0, 2], [2, 0])") == "true"

    def test_two_parallel_segments_do_not(self):
        assert evaluate("segmentsCross([0, 0], [2, 0], [0, 1], [2, 1])") == "false"

    def test_two_segments_on_one_line_but_apart_do_not(self):
        assert evaluate("segmentsCross([0, 0], [1, 1], [2, 2], [3, 3])") == "false"

    def test_segments_touching_at_an_endpoint_do_cross(self):
        # so a chain of segments has no gaps at its joints
        assert evaluate("segmentsCross([0, 0], [1, 1], [1, 1], [2, 0])") == "true"

    def test_overlapping_segments_cross(self):
        assert evaluate("segmentsCross([0, 0], [3, 3], [1, 1], [2, 2])") == "true"

    def test_a_segment_ending_on_another_crosses_it(self):
        assert evaluate("segmentsCross([0, 0], [4, 0], [2, 0], [2, 4])") == "true"


class TestPolygons:
    def test_the_area_of_a_square(self):
        assert evaluate(f"area({SQUARE})") == "16.0"

    def test_the_area_of_a_triangle(self):
        assert evaluate(f"area({TRIANGLE})") == "6.0"

    def test_the_area_is_never_negative(self):
        # a negative area surprises everyone who has not read the docstring
        assert float(evaluate(f"area({CLOCKWISE})")) > 0

    def test_the_winding_of_a_counterclockwise_polygon(self):
        assert evaluate(f"winding({SQUARE})") == LEFT

    def test_the_winding_of_a_clockwise_polygon(self):
        assert evaluate(f"winding({CLOCKWISE})") == RIGHT

    def test_a_degenerate_polygon_winds_neither_way(self):
        assert evaluate("winding([[0, 0], [1, 1], [2, 2]])") == STRAIGHT

    def test_the_signed_area_carries_the_direction(self):
        counter = signed_area([(0, 0), (4, 0), (4, 4), (0, 4)])
        clock = signed_area([(0, 0), (0, 4), (4, 4), (4, 0)])
        assert counter > 0
        assert clock == -counter

    def test_the_perimeter_of_a_square(self):
        assert evaluate(f"perimeter({SQUARE})") == "16.0"

    def test_the_perimeter_of_a_triangle(self):
        assert float(evaluate(f"perimeter({TRIANGLE})")) == pytest.approx(12.0)

    def test_the_centroid_of_a_square(self):
        assert evaluate(f"centroid({SQUARE})") == "[2.0, 2.0]"

    def test_a_polygon_of_two_points_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output("print area([[0, 0], [1, 1]]);")
        assert "at least three points" in str(caught.value)

    def test_a_convex_polygon_is_recognised(self):
        assert evaluate(f"isConvex({SQUARE})") == "true"

    def test_a_concave_polygon_is_recognised(self):
        assert evaluate(f"isConvex({CONCAVE})") == "false"

    def test_a_triangle_is_always_convex(self):
        assert evaluate(f"isConvex({TRIANGLE})") == "true"


class TestContainment:
    def test_a_point_well_inside_is_inside(self):
        assert evaluate(f"insidePolygon([2, 2], {SQUARE})") == "true"

    def test_a_point_outside_is_outside(self):
        assert evaluate(f"insidePolygon([5, 5], {SQUARE})") == "false"

    def test_a_point_on_an_edge_counts_as_inside(self):
        # so adjacent polygons cover the plane without holes at their shared edges
        assert evaluate(f"insidePolygon([0, 2], {SQUARE})") == "true"

    def test_a_corner_counts_as_inside(self):
        assert evaluate(f"insidePolygon([4, 4], {SQUARE})") == "true"

    def test_a_point_just_outside_an_edge_is_outside(self):
        assert evaluate(f"insidePolygon([-0.001, 2], {SQUARE})") == "false"

    def test_containment_works_for_a_triangle(self):
        assert evaluate(f"insidePolygon([1, 1], {TRIANGLE})") == "true"
        assert evaluate(f"insidePolygon([3, 3], {TRIANGLE})") == "false"

    def test_containment_works_for_a_concave_polygon(self):
        assert evaluate(f"insidePolygon([0.5, 0.5], {CONCAVE})") == "true"
        assert evaluate(f"insidePolygon([3, 3], {CONCAVE})") == "false"

    def test_containment_does_not_depend_on_the_winding(self):
        assert evaluate(f"insidePolygon([2, 2], {CLOCKWISE})") == "true"


class TestBoundingBoxes:
    def test_the_box_covers_every_point(self):
        assert evaluate("boundingBox([[1, 5], [3, 2], [0, 9]])") == "[[0, 2], [3, 9]]"

    def test_one_point_gives_a_box_of_no_size(self):
        assert evaluate("boundingBox([[2, 3]])") == "[[2, 3], [2, 3]]"

    def test_no_points_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output("print boundingBox([]);")
        assert "at least one point" in str(caught.value)


class TestConvexHulls:
    def test_an_interior_point_is_dropped(self):
        source = "convexHull([[0, 0], [4, 0], [4, 4], [0, 4], [2, 2]])"
        assert evaluate(source) == "[[0, 0], [4, 0], [4, 4], [0, 4]]"

    def test_the_hull_of_a_square_is_the_square(self):
        assert evaluate(f"convexHull({SQUARE})") == "[[0, 0], [4, 0], [4, 4], [0, 4]]"

    def test_the_hull_does_not_repeat_its_first_point(self):
        # a caller counting vertices should not have to know one appears twice
        found = evaluate(f"convexHull({SQUARE})")
        assert found.count("[0, 0]") == 1

    def test_the_hull_of_three_points_is_all_of_them(self):
        assert len(evaluate("convexHull([[0, 0], [1, 0], [0, 1]])").split("], [")) == 3

    def test_the_hull_of_two_points_is_both(self):
        assert evaluate("convexHull([[0, 0], [1, 1]])") == "[[0, 0], [1, 1]]"

    def test_the_hull_of_one_point_is_it(self):
        assert evaluate("convexHull([[2, 2]])") == "[[2, 2]]"

    def test_the_hull_of_nothing_is_nothing(self):
        assert evaluate("convexHull([])") == "[]"

    def test_duplicate_points_appear_once(self):
        assert evaluate("convexHull([[0, 0], [0, 0], [1, 1]])") == "[[0, 0], [1, 1]]"

    def test_collinear_points_are_dropped_from_the_hull(self):
        source = "convexHull([[0, 0], [1, 0], [2, 0], [1, 1]])"
        assert evaluate(source).count("], [") == 2

    def test_a_hull_is_convex(self):
        source = "isConvex(convexHull([[0, 0], [4, 0], [4, 4], [0, 4], [2, 2]]))"
        assert evaluate(source) == "true"


class TestTransforms:
    def test_translating_moves_every_point(self):
        assert evaluate(f"translated({SQUARE}, [1, 1])") == "[[1, 1], [5, 1], [5, 5], [1, 5]]"

    def test_translating_by_nothing_changes_nothing(self):
        assert evaluate(f"translated({SQUARE}, [0, 0])") == SQUARE

    def test_translating_does_not_change_the_area(self):
        assert evaluate(f"area(translated({SQUARE}, [9, 9]))") == evaluate(f"area({SQUARE})")

    def test_scaling_about_the_origin_multiplies(self):
        assert evaluate("scaledAbout([[1, 1]], [0, 0], 2)") == "[[2, 2]]"

    def test_scaling_about_a_point_leaves_it_fixed(self):
        assert evaluate("scaledAbout([[2, 2]], [2, 2], 5)") == "[[2, 2]]"

    def test_scaling_by_two_quadruples_the_area(self):
        scaled = float(evaluate(f"area(scaledAbout({SQUARE}, [0, 0], 2))"))
        assert scaled == pytest.approx(4 * float(evaluate(f"area({SQUARE})")))

    def test_rotating_a_quarter_turn_preserves_the_area(self):
        turned = float(evaluate(f"area(rotatedAbout({SQUARE}, [2, 2], 0.25))"))
        assert turned == pytest.approx(16.0)

    def test_rotating_a_whole_turn_returns_the_shape(self):
        turned = evaluate("rotatedAbout([[1, 0]], [0, 0], 1)")
        first = float(turned[2:].split(",")[0])
        assert first == pytest.approx(1.0)

    def test_rotating_about_a_point_leaves_it_fixed(self):
        assert evaluate("rotatedAbout([[2, 2]], [2, 2], 0.3)") == "[[2.0, 2.0]]"

    def test_a_quarter_turn_moves_a_point_as_expected(self):
        turned = evaluate("rotatedAbout([[1, 0]], [0, 0], 0.25)")
        pieces = turned[2:-2].split(", ")
        assert float(pieces[0]) == pytest.approx(0.0, abs=1e-9)
        assert float(pieces[1]) == pytest.approx(1.0)

    def test_the_rotation_uses_turns_rather_than_radians(self):
        # a whole turn is one, which is why no constant appears in a caller
        turned = evaluate("rotatedAbout([[1, 0]], [0, 0], 0.5)")
        assert float(turned[2:-2].split(", ")[0]) == pytest.approx(-1.0)


class TestRefusals:
    @pytest.mark.parametrize(
        "call",
        [
            "turn([0, 0], [1, 1], 5)",
            "distance([0, 0], 5)",
            "midpoint(5, [0, 0])",
            "onSegment([0, 0], [1, 1], 5)",
        ],
    )
    def test_something_that_is_not_a_point_is_refused(self, call):
        with pytest.raises(TypeMismatch) as caught:
            run_output(f"print {call};")
        assert "list of two numbers" in str(caught.value)

    def test_a_point_with_three_numbers_is_refused(self):
        with pytest.raises(TypeMismatch):
            run_output("print distance([0, 0, 0], [1, 1]);")

    def test_a_point_of_strings_is_refused(self):
        with pytest.raises(TypeMismatch) as caught:
            run_output('print distance(["a", "b"], [1, 1]);')
        assert "needs numbers" in str(caught.value)

    def test_a_polygon_that_is_not_a_list_is_refused(self):
        with pytest.raises(TypeMismatch):
            run_output("print area(5);")

    def test_a_list_of_points_that_is_not_a_list_is_refused(self):
        with pytest.raises(TypeMismatch):
            run_output("print boundingBox(5);")


class TestBothBackendsAgree:
    @pytest.mark.parametrize(
        "expression",
        [
            "turn([0, 0], [1, 0], [1, 1])",
            "distance([0, 0], [3, 4])",
            "squaredDistance([1, 1], [4, 5])",
            "midpoint([0, 0], [3, 3])",
            "onSegment([2, 0], [0, 0], [4, 0])",
            "segmentsCross([0, 0], [2, 2], [0, 2], [2, 0])",
            f"area({SQUARE})",
            f"winding({SQUARE})",
            f"perimeter({TRIANGLE})",
            f"centroid({SQUARE})",
            f"insidePolygon([2, 2], {SQUARE})",
            "boundingBox([[1, 5], [3, 2]])",
            "convexHull([[0, 0], [4, 0], [4, 4], [0, 4], [2, 2]])",
            f"isConvex({CONCAVE})",
            f"translated({SQUARE}, [1, 1])",
            "scaledAbout([[1, 1]], [0, 0], 3)",
            "rotatedAbout([[1, 0]], [0, 0], 0.25)",
        ],
    )
    def test_the_two_backends_agree(self, expression):
        source = f"print {expression};"
        assert run_output(source) == run_treewalk_output(source)


class TestAgainstIndependentArithmetic:
    def test_the_area_of_a_regular_polygon_approaches_a_circle(self):
        # a check the library cannot fake: many sided polygons approach pi
        source = "let points = [];" + chr(10)
        source += "for (let i = 0; i < 200; i = i + 1) {" + chr(10)
        source += "  let a = i / 200;" + chr(10)
        source += "  points = push(points, [cos(a * 6.283185307179586), "
        source += "sin(a * 6.283185307179586)]);" + chr(10)
        source += "}" + chr(10) + "print area(points);"
        assert float(run_output(source)[0]) == pytest.approx(math.pi, rel=1e-3)

    def test_the_perimeter_of_a_regular_polygon_approaches_a_circle(self):
        source = "let points = [];" + chr(10)
        source += "for (let i = 0; i < 200; i = i + 1) {" + chr(10)
        source += "  let a = i / 200;" + chr(10)
        source += "  points = push(points, [cos(a * 6.283185307179586), "
        source += "sin(a * 6.283185307179586)]);" + chr(10)
        source += "}" + chr(10) + "print perimeter(points);"
        assert float(run_output(source)[0]) == pytest.approx(2 * math.pi, rel=1e-3)
