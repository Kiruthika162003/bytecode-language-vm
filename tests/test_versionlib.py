from __future__ import annotations

import pytest

from ember.errors import Arithmetic, TypeMismatch
from ember.interpreter import run_output, run_treewalk_output
from ember.versionlib import compare_versions, parse_version, version_names

QUOTE = chr(34)


def quoted(text: str) -> str:
    return QUOTE + text + QUOTE


def evaluate(expression: str) -> str:
    return run_output(f"print {expression};")[0]


class TestRegistration:
    def test_the_functions_are_named(self):
        assert "compareVersions" in version_names()
        assert "sortedVersions" in version_names()

    def test_the_names_are_sorted(self):
        assert version_names() == sorted(version_names())

    def test_there_are_sixteen_of_them(self):
        assert len(version_names()) == 16


class TestParsing:
    def test_the_three_numbers_are_read(self):
        assert parse_version("1.2.3")[:3] == (1, 2, 3)

    def test_a_prerelease_marker_is_read(self):
        assert parse_version("1.2.3-alpha")[3] == "alpha"

    def test_build_metadata_is_read(self):
        assert parse_version("1.2.3+build.7")[4] == "build.7"

    def test_both_suffixes_can_appear(self):
        found = parse_version("1.2.3-alpha+build")
        assert found[3] == "alpha"
        assert found[4] == "build"

    def test_whitespace_around_a_version_is_ignored(self):
        assert parse_version("  1.2.3  ")[:3] == (1, 2, 3)

    def test_a_two_part_version_is_refused(self):
        # rather than assuming a zero nobody wrote
        with pytest.raises(Arithmetic) as caught:
            parse_version("1.2")
        assert "three numbers" in str(caught.value)

    def test_the_refusal_says_what_to_do(self):
        with pytest.raises(Arithmetic) as caught:
            parse_version("1.2")
        assert "adding the zero" in str(caught.value)

    def test_a_four_part_version_is_refused(self):
        with pytest.raises(Arithmetic):
            parse_version("1.2.3.4")

    def test_a_part_that_is_not_a_number_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            parse_version("1.x.3")
        assert "is not a number" in str(caught.value)

    def test_an_empty_version_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            parse_version("")
        assert "cannot be empty" in str(caught.value)

    def test_a_trailing_hyphen_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            parse_version("1.2.3-")
        assert "no prerelease marker" in str(caught.value)

    def test_a_trailing_plus_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            parse_version("1.2.3+")
        assert "no build metadata" in str(caught.value)

    def test_a_program_gets_the_parts_as_a_list(self):
        found = evaluate(f"parseVersion({quoted('1.2.3-alpha+build')})")
        assert found == '[1, 2, 3, "alpha", "build"]'


class TestOrdering:
    @pytest.mark.parametrize(
        "left,right,expected",
        [
            ("1.0.0", "2.0.0", -1),
            ("2.0.0", "1.0.0", 1),
            ("1.0.0", "1.0.0", 0),
            ("1.9.0", "1.10.0", -1),
            ("1.0.9", "1.0.10", -1),
            ("1.2.3", "1.3.0", -1),
        ],
    )
    def test_the_numbers_compare_numerically(self, left, right, expected):
        assert compare_versions(left, right) == expected

    def test_ten_comes_after_two(self):
        # the case that stays hidden until the tenth release
        assert compare_versions("2.0.0", "10.0.0") == -1

    def test_text_comparison_would_get_that_wrong(self):
        # the mistake this library exists to avoid, shown rather than described
        as_text = sorted(["2.0.0", "10.0.0"])
        assert as_text == ["10.0.0", "2.0.0"]

    def test_the_major_number_wins_over_the_minor(self):
        assert compare_versions("1.99.99", "2.0.0") == -1

    def test_the_minor_number_wins_over_the_patch(self):
        assert compare_versions("1.1.99", "1.2.0") == -1


class TestPrereleases:
    def test_a_prerelease_sorts_before_its_release(self):
        assert compare_versions("1.0.0-alpha", "1.0.0") == -1

    def test_a_release_sorts_after_its_prerelease(self):
        assert compare_versions("1.0.0", "1.0.0-alpha") == 1

    def test_two_markers_compare_as_text(self):
        assert compare_versions("1.0.0-alpha", "1.0.0-beta") == -1

    def test_a_shorter_marker_sorts_below_a_longer_one(self):
        assert compare_versions("1.0.0-alpha", "1.0.0-alpha.1") == -1

    def test_numeric_parts_compare_numerically(self):
        assert compare_versions("1.0.0-alpha.2", "1.0.0-alpha.10") == -1

    def test_a_numeric_part_sorts_below_a_textual_one(self):
        assert compare_versions("1.0.0-1", "1.0.0-alpha") == -1

    def test_identical_markers_are_equal(self):
        assert compare_versions("1.0.0-alpha", "1.0.0-alpha") == 0

    def test_a_prerelease_is_recognised(self):
        assert evaluate(f"isPrerelease({quoted('1.0.0-alpha')})") == "true"

    def test_a_release_is_not_a_prerelease(self):
        assert evaluate(f"isPrerelease({quoted('1.0.0')})") == "false"

    def test_a_prerelease_of_a_later_version_still_sorts_later(self):
        assert compare_versions("1.0.0", "2.0.0-alpha") == -1


class TestBuildMetadata:
    def test_metadata_is_ignored_in_comparison(self):
        # the metadata records where a build came from, not what it contains
        assert compare_versions("1.0.0+build", "1.0.0") == 0

    def test_two_different_builds_are_equal(self):
        assert compare_versions("1.0.0+one", "1.0.0+two") == 0

    def test_metadata_does_not_hide_a_real_difference(self):
        assert compare_versions("1.0.0+x", "1.0.1+x") == -1

    def test_a_program_sees_them_as_the_same(self):
        source = f"sameVersion({quoted('1.0.0+a')}, {quoted('1.0.0+b')})"
        assert evaluate(source) == "true"


class TestComparingFromPrograms:
    def test_before_is_offered_directly(self):
        source = f"versionBefore({quoted('1.0.0')}, {quoted('2.0.0')})"
        assert evaluate(source) == "true"

    def test_after_is_offered_directly(self):
        source = f"versionAfter({quoted('2.0.0')}, {quoted('1.0.0')})"
        assert evaluate(source) == "true"

    def test_a_version_is_not_before_itself(self):
        source = f"versionBefore({quoted('1.0.0')}, {quoted('1.0.0')})"
        assert evaluate(source) == "false"

    def test_the_comparison_gives_minus_one_zero_or_one(self):
        source = f"compareVersions({quoted('1.0.0')}, {quoted('2.0.0')})"
        assert evaluate(source) == "-1"

    def test_a_valid_version_is_recognised(self):
        assert evaluate(f"isVersion({quoted('1.2.3')})") == "true"

    def test_an_invalid_version_is_recognised(self):
        assert evaluate(f"isVersion({quoted('1.2')})") == "false"

    def test_something_that_is_not_a_string_is_not_a_version(self):
        # asking whether a value is a version answers no rather than faulting
        assert evaluate("isVersion(5)") == "false"

    def test_comparing_something_that_is_not_a_string_is_refused(self):
        # comparing is a different question, and there is no answer to give
        with pytest.raises(TypeMismatch):
            run_output(f"print compareVersions(5, {quoted('1.0.0')});")


class TestParts:
    def test_the_major_can_be_asked_for(self):
        assert evaluate(f"majorOf({quoted('1.2.3')})") == "1"

    def test_the_minor_can_be_asked_for(self):
        assert evaluate(f"minorOf({quoted('1.2.3')})") == "2"

    def test_the_patch_can_be_asked_for(self):
        assert evaluate(f"patchOf({quoted('1.2.3')})") == "3"

    def test_the_next_major_resets_the_rest(self):
        assert evaluate(f"nextMajor({quoted('1.2.3')})") == "2.0.0"

    def test_the_next_minor_resets_the_patch(self):
        assert evaluate(f"nextMinor({quoted('1.2.3')})") == "1.3.0"

    def test_the_next_patch_moves_one(self):
        assert evaluate(f"nextPatch({quoted('1.2.3')})") == "1.2.4"

    def test_the_next_version_drops_any_prerelease(self):
        assert evaluate(f"nextPatch({quoted('1.2.3-alpha')})") == "1.2.4"


class TestSorting:
    def test_versions_sort_by_their_numbers(self):
        listed = "[" + ", ".join(quoted(one) for one in ["2.0.0", "10.0.0", "1.0.0"]) + "]"
        assert evaluate(f"sortedVersions({listed})") == '["1.0.0", "2.0.0", "10.0.0"]'

    def test_a_prerelease_sorts_before_its_release(self):
        listed = "[" + ", ".join(quoted(one) for one in ["1.0.0", "1.0.0-alpha"]) + "]"
        assert evaluate(f"sortedVersions({listed})") == '["1.0.0-alpha", "1.0.0"]'

    def test_sorting_nothing_gives_nothing(self):
        assert evaluate("sortedVersions([])") == "[]"

    def test_the_latest_is_the_last(self):
        listed = "[" + ", ".join(quoted(one) for one in ["2.0.0", "10.0.0", "1.0.0"]) + "]"
        assert evaluate(f"latestVersion({listed})") == "10.0.0"

    def test_the_latest_of_nothing_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output("print latestVersion([]);")
        assert "nothing to choose from" in str(caught.value)

    def test_an_invalid_version_in_the_list_is_refused(self):
        # a list of one was never checked while validation happened lazily, because
        # nothing is compared against a single element
        listed = "[" + quoted("1.2") + "]"
        with pytest.raises(Arithmetic):
            run_output(f"print sortedVersions({listed});")

    def test_an_invalid_version_beside_a_valid_one_is_refused(self):
        listed = "[" + quoted("1.0.0") + ", " + quoted("1.2") + "]"
        with pytest.raises(Arithmetic):
            run_output(f"print sortedVersions({listed});")

    def test_the_latest_of_an_invalid_list_is_refused(self):
        listed = "[" + quoted("nonsense") + "]"
        with pytest.raises(Arithmetic):
            run_output(f"print latestVersion({listed});")

    def test_sorting_something_that_is_not_a_list_is_refused(self):
        with pytest.raises(TypeMismatch):
            run_output(f"print sortedVersions({quoted('1.0.0')});")


class TestCompatibility:
    def test_a_later_patch_is_compatible(self):
        source = f"compatibleWith({quoted('1.2.3')}, {quoted('1.0.0')})"
        assert evaluate(source) == "true"

    def test_the_floor_itself_is_compatible(self):
        source = f"compatibleWith({quoted('1.0.0')}, {quoted('1.0.0')})"
        assert evaluate(source) == "true"

    def test_an_earlier_version_is_not(self):
        source = f"compatibleWith({quoted('0.9.0')}, {quoted('1.0.0')})"
        assert evaluate(source) == "false"

    def test_the_next_major_is_not(self):
        # which is the promise a major number is supposed to make
        source = f"compatibleWith({quoted('2.0.0')}, {quoted('1.0.0')})"
        assert evaluate(source) == "false"

    def test_a_prerelease_of_the_next_major_is_not(self):
        # it is below the next major, which is why saying below rather than sharing
        # the major let it through
        source = f"compatibleWith({quoted('2.0.0-alpha')}, {quoted('1.0.0')})"
        assert evaluate(source) == "false"

    def test_a_prerelease_of_the_same_major_above_the_floor_is_compatible(self):
        source = f"compatibleWith({quoted('1.5.0-alpha')}, {quoted('1.0.0')})"
        assert evaluate(source) == "true"

    def test_a_much_later_minor_of_the_same_major_is_compatible(self):
        source = f"compatibleWith({quoted('1.99.0')}, {quoted('1.0.0')})"
        assert evaluate(source) == "true"

    def test_a_prerelease_below_the_floor_is_not(self):
        source = f"compatibleWith({quoted('1.0.0-alpha')}, {quoted('1.0.0')})"
        assert evaluate(source) == "false"


class TestBothBackendsAgree:
    @pytest.mark.parametrize(
        "expression",
        [
            f"parseVersion({quoted('1.2.3-alpha+build')})",
            f"compareVersions({quoted('2.0.0')}, {quoted('10.0.0')})",
            f"versionBefore({quoted('1.0.0')}, {quoted('2.0.0')})",
            f"versionAfter({quoted('2.0.0')}, {quoted('1.0.0')})",
            f"sameVersion({quoted('1.0.0+a')}, {quoted('1.0.0+b')})",
            f"isVersion({quoted('1.2')})",
            f"isPrerelease({quoted('1.0.0-alpha')})",
            f"majorOf({quoted('1.2.3')})",
            f"minorOf({quoted('1.2.3')})",
            f"patchOf({quoted('1.2.3')})",
            f"nextMajor({quoted('1.2.3')})",
            f"nextMinor({quoted('1.2.3')})",
            f"nextPatch({quoted('1.2.3')})",
            "sortedVersions([" + quoted("2.0.0") + ", " + quoted("10.0.0") + "])",
            "latestVersion([" + quoted("2.0.0") + ", " + quoted("10.0.0") + "])",
            f"compatibleWith({quoted('1.2.3')}, {quoted('1.0.0')})",
        ],
    )
    def test_the_two_backends_agree(self, expression):
        source = f"print {expression};"
        assert run_output(source) == run_treewalk_output(source)
