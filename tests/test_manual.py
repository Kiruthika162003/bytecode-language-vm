from __future__ import annotations

import pytest

from ember.builtins import builtin_names
from ember.manual import (
    Reference,
    missing_from_machine,
    reference,
    render,
    unlisted,
)


class TestNoCollisions:
    def test_no_name_is_claimed_by_two_libraries(self):
        # the first run of this found two, and whichever installs last had been
        # silently winning; the count is pinned here so the next one cannot hide
        assert reference().collisions == {}

    def test_the_total_matches_the_sum_of_the_libraries(self):
        found = reference()
        assert found.total == sum(len(names) for names in found.libraries.values())

    def test_every_name_appears_once_across_the_libraries(self):
        found = reference()
        every = [name for names in found.libraries.values() for name in names]
        assert len(every) == len(set(every))


class TestAgreementWithTheMachine:
    def test_every_registered_name_reaches_the_machine(self):
        assert missing_from_machine() == []

    def test_the_names_the_core_supplies_are_listed_separately(self):
        # the core builtins belong to no library module
        assert "len" in unlisted()
        assert "print" not in unlisted()

    def test_the_libraries_and_the_core_account_for_everything(self):
        found = reference()
        listed = {name for names in found.libraries.values() for name in names}
        assert listed | set(unlisted()) == set(builtin_names())

    def test_a_library_function_is_not_in_the_unlisted_set(self):
        assert "mean" not in unlisted()


class TestTheListing:
    def test_there_are_many_libraries(self):
        assert reference().library_count > 20

    def test_there_are_many_functions(self):
        assert reference().total > 300

    def test_a_function_can_be_traced_to_its_library(self):
        assert reference().library_of("mean") == "statistics"

    def test_a_name_no_library_has_traces_to_nothing(self):
        assert reference().library_of("nowhere") is None

    def test_the_largest_library_is_named(self):
        library, count = reference().largest()
        assert library
        assert count > 10

    def test_an_empty_reference_has_no_largest(self):
        assert Reference().largest() == ("", 0)

    def test_an_empty_reference_totals_nothing(self):
        assert Reference().total == 0

    def test_every_library_lists_its_names_sorted(self):
        for names in reference().libraries.values():
            assert names == sorted(names)

    def test_no_library_is_empty(self):
        for library, names in reference().libraries.items():
            assert names, f"{library} registers nothing"


class TestRendering:
    def test_every_library_gets_a_heading(self):
        lines = reference().render()
        assert any(line.startswith("statistics (") for line in lines)

    def test_the_total_is_reported(self):
        assert any("functions across" in line for line in reference().render())

    def test_a_function_appears_in_its_library(self):
        text = render()
        assert "mean" in text

    def test_no_collision_is_reported(self):
        assert not any("is registered by" in line for line in reference().render())

    def test_the_rendered_form_is_text(self):
        assert isinstance(render(), str)

    def test_the_rendered_form_is_ascii(self):
        assert all(ord(character) < 128 for character in render())

    def test_a_collision_would_be_reported(self):
        # the report exists to be read, so it is checked on a made up one
        made = Reference(
            libraries={"one": ["shared"], "two": ["shared"]},
            collisions={"shared": ["one", "two"]},
        )
        assert any("shared is registered by one and two" in line for line in made.render())


class TestSpotChecks:
    @pytest.mark.parametrize(
        "name,library",
        [
            ("mean", "statistics"),
            ("toJson", "json"),
            ("heapify", "heaps"),
            ("fnv1a", "hashes"),
            ("convertTo", "units"),
            ("compareVersions", "versions"),
            ("matches", "patterns"),
            ("pretty", "pretty printing"),
            ("determinant", "matrices"),
            ("interval", "intervals"),
            ("barChart", "charts"),
            ("move", "state machines"),
            ("enqueue", "queues"),
            ("diff", "differences"),
            ("isValid", "schemas"),
            ("toBase64", "encodings"),
            ("turn", "geometry"),
            ("fraction", "fractions"),
            ("countOnes", "bits"),
            ("fromCsv", "comma separated values"),
        ],
    )
    def test_a_function_belongs_to_the_library_it_should(self, name, library):
        assert reference().library_of(name) == library

    @pytest.mark.parametrize(
        "name",
        ["mean", "toJson", "heapify", "matches", "convertTo", "pretty", "diff"],
    )
    def test_every_spot_checked_function_reaches_the_machine(self, name):
        assert name in builtin_names()
