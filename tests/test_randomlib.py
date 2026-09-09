from __future__ import annotations

import collections

import pytest

from ember.errors import Arithmetic, TypeMismatch
from ember.interpreter import run_output, run_treewalk_output
from ember.randomlib import Stream, mixed, random_names


def evaluate(expression: str) -> str:
    return run_output(f"print {expression};")[0]


class TestRegistration:
    def test_the_functions_are_named(self):
        assert "shuffled" in random_names()
        assert "randomBelow" in random_names()

    def test_the_names_are_sorted(self):
        assert random_names() == sorted(random_names())

    def test_there_are_twelve_of_them(self):
        assert len(random_names()) == 12

    def test_nothing_can_be_seeded_from_outside(self):
        # a run that cannot be reproduced cannot be debugged from a report
        assert not any(name.lower() == "seed" for name in random_names())


class TestDeterminism:
    def test_the_same_seed_gives_the_same_number(self):
        assert evaluate("randomBits(7)") == evaluate("randomBits(7)")

    def test_a_different_seed_gives_a_different_number(self):
        assert evaluate("randomBits(7)") != evaluate("randomBits(8)")

    def test_the_same_seed_gives_the_same_list(self):
        assert evaluate("randomList(3, 5, 100)") == evaluate("randomList(3, 5, 100)")

    def test_the_same_seed_gives_the_same_shuffle(self):
        assert evaluate("shuffled(9, [1,2,3,4,5])") == evaluate("shuffled(9, [1,2,3,4,5])")

    def test_a_stream_repeats_from_the_same_seed(self):
        one = Stream(3)
        first = [one.next_bits() for _ in range(5)]
        another = Stream(3)
        assert [another.next_bits() for _ in range(5)] == first

    def test_a_stream_advances_rather_than_repeating(self):
        stream = Stream(3)
        assert len({stream.next_bits() for _ in range(5)}) == 5


class TestSeedMixing:
    def test_a_small_seed_becomes_a_populated_word(self):
        # the bug that forced this step: a raw small seed gave a tiny first output
        assert mixed(1) > (1 << 40)

    def test_mixing_is_deterministic(self):
        assert mixed(5) == mixed(5)

    def test_different_seeds_mix_differently(self):
        assert mixed(1) != mixed(2)

    def test_mixing_never_returns_zero(self):
        # xorshift cannot start from zero, so the one forbidden state is replaced
        assert all(mixed(seed) != 0 for seed in range(200))

    def test_a_seed_of_zero_is_an_ordinary_seed(self):
        assert Stream(0).next_bits() != 0

    def test_a_program_can_use_seed_zero(self):
        assert evaluate("randomBelow(0, 10)") != ""

    def test_consecutive_seeds_give_unrelated_first_outputs(self):
        firsts = [Stream(seed).next_bits() for seed in range(1, 20)]
        assert len(set(firsts)) == 19
        assert min(firsts) > (1 << 40)


class TestDistribution:
    def test_a_shuffle_gives_every_ordering_a_similar_share(self):
        counts: collections.Counter = collections.Counter()
        for seed in range(1, 6001):
            counts[evaluate(f"shuffled({seed}, [1,2,3])")] += 1
        assert len(counts) == 6
        assert max(counts.values()) - min(counts.values()) < 200

    def test_a_weighted_pick_respects_its_weights(self):
        # before the seed was mixed this chose the heavier value every single time
        counts: collections.Counter = collections.Counter()
        for seed in range(1, 2001):
            counts[evaluate(f'weightedPick({seed}, ["a","b"], [3,1])')] += 1
        ratio = counts["a"] / counts["b"]
        assert 2.5 < ratio < 3.5

    def test_a_number_below_a_limit_covers_the_range(self):
        seen = {evaluate(f"randomBelow({seed}, 10)") for seed in range(1, 400)}
        assert len(seen) == 10

    def test_a_fraction_is_spread_across_the_unit_interval(self):
        values = [float(evaluate(f"randomFraction({seed})")) for seed in range(1, 300)]
        assert min(values) < 0.2
        assert max(values) > 0.8

    def test_a_die_covers_all_its_faces(self):
        rolled = {int(v) for v in evaluate("dice(1, 200, 6)")[1:-1].split(", ")}
        assert rolled == {1, 2, 3, 4, 5, 6}


class TestRanges:
    def test_a_number_below_a_limit_stays_below_it(self):
        for seed in range(1, 40):
            assert int(evaluate(f"randomBelow({seed}, 5)")) < 5

    def test_a_number_below_a_limit_is_never_negative(self):
        for seed in range(1, 40):
            assert int(evaluate(f"randomBelow({seed}, 5)")) >= 0

    def test_a_number_between_bounds_stays_inside_them(self):
        for seed in range(1, 40):
            value = int(evaluate(f"randomBetween({seed}, 10, 12)"))
            assert 10 <= value <= 12

    def test_a_range_of_one_value_gives_that_value(self):
        assert evaluate("randomBetween(5, 7, 7)") == "7"

    def test_a_limit_of_zero_is_refused(self):
        with pytest.raises(Arithmetic):
            run_output("print randomBelow(1, 0);")

    def test_a_backwards_range_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output("print randomBetween(1, 5, 2);")
        assert "empty" in str(caught.value)

    def test_a_fraction_stays_inside_the_unit_interval(self):
        for seed in range(1, 40):
            value = float(evaluate(f"randomFraction({seed})"))
            assert 0.0 <= value < 1.0


class TestLists:
    def test_a_list_has_the_count_asked_for(self):
        assert evaluate("len(randomList(1, 5, 10))") == "5"

    def test_a_list_of_zero_is_empty(self):
        assert evaluate("randomList(1, 0, 10)") == "[]"

    def test_a_negative_count_is_refused(self):
        with pytest.raises(Arithmetic):
            run_output("print randomList(1, -1, 10);")

    def test_a_list_of_fractions_has_the_count_asked_for(self):
        assert evaluate("len(randomFractions(1, 4))") == "4"

    def test_the_values_in_a_list_differ_from_one_another(self):
        # a stream advances, so one seed gives a run rather than one number repeated
        values = evaluate("randomList(1, 6, 1000)")
        assert len(set(values[1:-1].split(", "))) > 1

    def test_dice_roll_the_count_asked_for(self):
        assert evaluate("len(dice(1, 4, 6))") == "4"

    def test_a_die_with_no_sides_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output("print dice(1, 1, 0);")
        assert "at least one side" in str(caught.value)


class TestPicking:
    def test_a_pick_comes_from_the_list(self):
        for seed in range(1, 20):
            assert evaluate(f'pick({seed}, ["a","b","c"])') in ("a", "b", "c")

    def test_picking_from_one_value_gives_it(self):
        assert evaluate('pick(4, ["only"])') == "only"

    def test_picking_from_nothing_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output("print pick(1, []);")
        assert "nothing to choose from" in str(caught.value)

    def test_picking_from_something_that_is_not_a_list_is_refused(self):
        with pytest.raises(TypeMismatch):
            run_output("print pick(1, 5);")

    def test_a_seed_that_is_not_whole_is_refused(self):
        with pytest.raises(TypeMismatch):
            run_output("print randomBits(1.5);")


class TestShuffling:
    def test_a_shuffle_keeps_every_value(self):
        assert evaluate("ordered(shuffled(7, [1,2,3,4,5]))") == "[1, 2, 3, 4, 5]"

    def test_a_shuffle_keeps_the_length(self):
        assert evaluate("len(shuffled(7, [1,2,3,4,5]))") == "5"

    def test_shuffling_nothing_gives_nothing(self):
        assert evaluate("shuffled(1, [])") == "[]"

    def test_shuffling_one_value_gives_it_back(self):
        assert evaluate("shuffled(1, [9])") == "[9]"

    def test_a_shuffle_does_not_disturb_the_original(self):
        source = "let a = [1,2,3]; let b = shuffled(4, a); print a;"
        assert run_output(source) == ["[1, 2, 3]"]

    def test_a_shuffle_sometimes_changes_the_order(self):
        moved = sum(
            1
            for seed in range(1, 40)
            if evaluate(f"shuffled({seed}, [1,2,3,4])") != "[1, 2, 3, 4]"
        )
        assert moved > 30


class TestSampling:
    def test_a_sample_has_the_count_asked_for(self):
        assert evaluate("len(sample(1, [1,2,3,4,5], 3))") == "3"

    def test_a_sample_never_repeats_a_value(self):
        for seed in range(1, 30):
            drawn = evaluate(f"sample({seed}, [1,2,3,4,5], 3)")
            values = drawn[1:-1].split(", ")
            assert len(set(values)) == len(values)

    def test_a_sample_of_everything_is_a_shuffle(self):
        assert evaluate("ordered(sample(3, [1,2,3], 3))") == "[1, 2, 3]"

    def test_a_sample_of_nothing_is_empty(self):
        assert evaluate("sample(1, [1,2,3], 0)") == "[]"

    def test_asking_for_more_than_there_is_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output("print sample(1, [1,2], 5);")
        assert "never repeats" in str(caught.value)

    def test_the_refusal_points_at_the_alternative(self):
        with pytest.raises(Arithmetic) as caught:
            run_output("print sample(1, [1,2], 5);")
        assert "randomList" in str(caught.value)

    def test_a_negative_count_is_refused(self):
        with pytest.raises(Arithmetic):
            run_output("print sample(1, [1,2], -1);")


class TestWeighting:
    def test_a_weight_of_zero_is_never_chosen(self):
        for seed in range(1, 40):
            assert evaluate(f'weightedPick({seed}, ["never","always"], [0,1])') == "always"

    def test_mismatched_lengths_are_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output('print weightedPick(1, ["a","b"], [1]);')
        assert "one weight for each value" in str(caught.value)

    def test_all_weights_zero_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output('print weightedPick(1, ["a","b"], [0,0]);')
        assert "every weight is zero" in str(caught.value)

    def test_a_negative_weight_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output('print weightedPick(1, ["a","b"], [1,-1]);')
        assert "cannot be negative" in str(caught.value)

    def test_a_weight_that_is_not_a_number_is_refused(self):
        with pytest.raises(TypeMismatch):
            run_output('print weightedPick(1, ["a","b"], [1,"two"]);')

    def test_picking_from_nothing_is_refused(self):
        with pytest.raises(Arithmetic):
            run_output("print weightedPick(1, [], []);")


class TestCarryingAStreamForward:
    def test_the_next_seed_differs_from_the_seed(self):
        assert evaluate("nextSeed(5)") != "5"

    def test_the_next_seed_is_reproducible(self):
        assert evaluate("nextSeed(5)") == evaluate("nextSeed(5)")

    def test_a_chain_of_seeds_gives_a_changing_sequence(self):
        source = (
            "let s = 1; let seen = [];"
            + chr(10)
            + "for (let i = 0; i < 4; i = i + 1) { s = nextSeed(s);"
            + " seen = push(seen, s % 100); }"
            + chr(10)
            + "print len(distinct(seen));"
        )
        assert int(run_output(source)[0]) > 1


class TestBothBackendsAgree:
    @pytest.mark.parametrize(
        "expression",
        [
            "randomBits(7)",
            "randomFraction(7)",
            "randomBelow(7, 100)",
            "randomBetween(7, 1, 6)",
            "randomList(7, 5, 50)",
            "randomFractions(7, 3)",
            'pick(7, ["a","b","c"])',
            "shuffled(7, [1,2,3,4,5])",
            "sample(7, [1,2,3,4,5], 3)",
            'weightedPick(7, ["a","b"], [1,1])',
            "nextSeed(7)",
            "dice(7, 5, 6)",
        ],
    )
    def test_the_two_backends_agree(self, expression):
        source = f"print {expression};"
        assert run_output(source) == run_treewalk_output(source)
