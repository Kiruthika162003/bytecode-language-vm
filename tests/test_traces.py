from __future__ import annotations

import pytest

from ember.traces.finding import Finding
from ember.traces.registry import TRACES, broken, run_all


class TestFinding:
    def test_a_holding_finding_renders_as_holds(self):
        assert Finding("x", "a claim", True).render().startswith("[holds] x:")

    def test_a_broken_finding_is_marked(self):
        assert "BROKEN" in Finding("x", "a claim", False).render()


class TestRegistry:
    def test_there_are_twenty_one_traces(self):
        assert len(TRACES) == 21

    def test_every_trace_is_callable(self):
        assert all(callable(trace) for trace in TRACES)

    def test_the_names_are_distinct(self):
        names = [finding.name for finding in run_all()]
        assert len(set(names)) == len(names)


class TestEveryTraceHolds:
    @pytest.mark.parametrize("trace", TRACES, ids=lambda t: t.__module__.split(".")[-1])
    def test_the_trace_holds(self, trace):
        finding = trace()
        assert finding.holds, finding.render()

    def test_nothing_is_broken(self):
        assert broken() == []


class TestClaimsCarryNumbers:
    @pytest.mark.parametrize("trace", TRACES, ids=lambda t: t.__module__.split(".")[-1])
    def test_the_claim_states_a_measurement(self, trace):
        claim = trace().claim
        # a claim without a number in it is an adjective, not a measurement
        assert any(character.isdigit() for character in claim), claim
        assert len(claim) > 40
