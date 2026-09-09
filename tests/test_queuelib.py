from __future__ import annotations

import collections
import random

import pytest

from ember.errors import Arithmetic, TypeMismatch
from ember.interpreter import run_output, run_treewalk_output
from ember.queuelib import (
    _dequeue,
    _empty_queue,
    _enqueue,
    _queue_front,
    _queue_size,
    _queue_to_list,
    queue_names,
)


def evaluate(expression: str) -> str:
    return run_output(f"print {expression};")[0]


class TestRegistration:
    def test_the_functions_are_named(self):
        assert "enqueue" in queue_names()
        assert "ringPush" in queue_names()

    def test_the_names_are_sorted(self):
        assert queue_names() == sorted(queue_names())

    def test_there_are_twenty_three_of_them(self):
        assert len(queue_names()) == 23


class TestQueueOrder:
    def test_a_queue_gives_back_what_went_in_first(self):
        # the bug the classic reversal introduced: this used to give 3
        source = "let q = enqueue(enqueue(enqueue(newQueue(0), 1), 2), 3);"
        source += " print queueFront(q);"
        assert run_output(source) == ["1"]

    def test_the_whole_queue_reads_in_arrival_order(self):
        source = "let q = enqueue(enqueue(enqueue(newQueue(0), 1), 2), 3);"
        source += " print queueToList(q);"
        assert run_output(source) == ["[1, 2, 3]"]

    def test_taking_from_a_queue_takes_the_oldest(self):
        source = "let q = enqueue(enqueue(newQueue(0), 1), 2);"
        source += " print queueFront(dequeue(q));"
        assert run_output(source) == ["2"]

    def test_a_queue_drains_in_order(self):
        source = "let q = queueFrom([1, 2, 3]); let out = [];"
        source += " while (!queueEmpty(q)) { out = push(out, queueFront(q));"
        source += " q = dequeue(q); } print out;"
        assert run_output(source) == ["[1, 2, 3]"]

    def test_a_queue_from_a_list_keeps_its_order(self):
        assert evaluate("queueToList(queueFrom([7, 8, 9]))") == "[7, 8, 9]"

    def test_adding_after_draining_still_keeps_order(self):
        # the case where the back is carried over and then added to again
        source = "let q = queueFrom([1]); q = enqueue(q, 2); q = dequeue(q);"
        source += " q = enqueue(q, 3); print queueToList(q);"
        assert run_output(source) == ["[2, 3]"]


class TestAgainstTheHostDeque:
    def test_three_thousand_random_operations_agree(self):
        chooser = random.Random(11)
        mine = _empty_queue([])
        theirs: collections.deque = collections.deque()
        for _ in range(3000):
            if not theirs or chooser.random() < 0.55:
                value = chooser.randrange(1000)
                mine = _enqueue([mine, value])
                theirs.append(value)
            else:
                assert _queue_front([mine]) == theirs[0]
                mine = _dequeue([mine])
                theirs.popleft()
            assert _queue_size([mine]) == len(theirs)
            assert _queue_to_list([mine]) == list(theirs)


class TestQueueMeasuring:
    def test_an_empty_queue_is_empty(self):
        assert evaluate("queueEmpty(newQueue(0))") == "true"

    def test_a_queue_with_something_in_it_is_not(self):
        assert evaluate("queueEmpty(enqueue(newQueue(0), 1))") == "false"

    def test_the_size_counts_both_lists(self):
        source = "let q = queueFrom([1, 2]); q = enqueue(q, 3); print queueSize(q);"
        assert run_output(source) == ["3"]

    def test_an_empty_queue_has_no_size(self):
        assert evaluate("queueSize(newQueue(0))") == "0"

    def test_an_empty_queue_reads_as_nothing(self):
        assert evaluate("queueToList(newQueue(0))") == "[]"


class TestQueueRefusals:
    def test_taking_from_nothing_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output("print dequeue(newQueue(0));")
        assert "queue is empty" in str(caught.value)

    def test_looking_at_nothing_is_refused(self):
        with pytest.raises(Arithmetic):
            run_output("print queueFront(newQueue(0));")

    def test_a_list_of_the_wrong_shape_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output("print queueSize([1, 2, 3]);")
        assert "list of two lists" in str(caught.value)

    def test_something_that_is_not_a_list_is_refused(self):
        with pytest.raises(TypeMismatch):
            run_output("print queueSize(5);")

    def test_a_queue_whose_halves_are_not_lists_is_refused(self):
        with pytest.raises(TypeMismatch):
            run_output("print queueSize([1, 2]);")


class TestNothingIsModified:
    def test_adding_leaves_the_original_alone(self):
        source = "let q = newQueue(0); let r = enqueue(q, 1); print queueSize(q);"
        assert run_output(source) == ["0"]

    def test_taking_leaves_the_original_alone(self):
        source = "let q = queueFrom([1, 2]); let r = dequeue(q); print queueSize(q);"
        assert run_output(source) == ["2"]

    def test_a_queue_from_a_list_does_not_share_it(self):
        source = "let a = [1]; let q = queueFrom(a); q = enqueue(q, 2); print a;"
        assert run_output(source) == ["[1]"]


class TestRings:
    def test_a_new_ring_is_empty(self):
        assert evaluate("ringEmpty(newRing(3))") == "true"

    def test_a_new_ring_has_the_capacity_asked_for(self):
        assert evaluate("ringCapacity(newRing(3))") == "3"

    def test_pushing_adds_to_the_ring(self):
        assert evaluate("ringSize(ringPush(newRing(3), 1))") == "1"

    def test_the_contents_read_oldest_first(self):
        source = "let r = ringPush(ringPush(newRing(3), 1), 2); print ringToList(r);"
        assert run_output(source) == ["[1, 2]"]

    def test_the_oldest_and_newest_can_be_asked_for(self):
        source = "let r = ringPush(ringPush(newRing(3), 1), 2);"
        source += " print ringOldest(r); print ringNewest(r);"
        assert run_output(source) == ["1", "2"]

    def test_a_ring_becomes_full(self):
        source = "let r = ringPush(ringPush(ringPush(newRing(3), 1), 2), 3);"
        source += " print ringFull(r);"
        assert run_output(source) == ["true"]

    def test_pushing_onto_a_full_ring_is_refused(self):
        # rather than losing anything without being asked
        source = "let r = ringPush(ringPush(newRing(2), 1), 2); print ringPush(r, 3);"
        with pytest.raises(Arithmetic) as caught:
            run_output(source)
        assert "is full" in str(caught.value)

    def test_the_refusal_points_at_the_alternative(self):
        source = "let r = ringPush(ringPush(newRing(2), 1), 2); print ringPush(r, 3);"
        with pytest.raises(Arithmetic) as caught:
            run_output(source)
        assert "ringOverwrite" in str(caught.value)

    def test_overwriting_drops_the_oldest(self):
        source = "let r = ringPush(ringPush(newRing(2), 1), 2);"
        source += " r = ringOverwrite(r, 3); print ringToList(r);"
        assert run_output(source) == ["[2, 3]"]

    def test_overwriting_keeps_the_size(self):
        source = "let r = ringPush(ringPush(newRing(2), 1), 2);"
        source += " print ringSize(ringOverwrite(r, 3));"
        assert run_output(source) == ["2"]

    def test_overwriting_a_ring_with_room_just_adds(self):
        source = "let r = ringOverwrite(newRing(2), 1); print ringToList(r);"
        assert run_output(source) == ["[1]"]

    def test_taking_from_a_ring_takes_the_oldest(self):
        source = "let r = ringPush(ringPush(newRing(3), 1), 2);"
        source += " print ringToList(ringPop(r));"
        assert run_output(source) == ["[2]"]

    def test_a_ring_wraps_round(self):
        source = "let r = newRing(3);"
        source += " for (let i = 0; i < 7; i = i + 1) { r = ringOverwrite(r, i); }"
        source += " print ringToList(r);"
        assert run_output(source) == ["[4, 5, 6]"]

    def test_pushing_and_popping_round_the_ring_keeps_order(self):
        source = "let r = newRing(3); let out = [];"
        source += " for (let i = 0; i < 6; i = i + 1) { r = ringPush(r, i);"
        source += " out = push(out, ringOldest(r)); r = ringPop(r); }"
        source += " print out;"
        assert run_output(source) == ["[0, 1, 2, 3, 4, 5]"]

    def test_taking_from_an_empty_ring_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output("print ringPop(newRing(2));")
        assert "ring is empty" in str(caught.value)

    def test_looking_at_an_empty_ring_is_refused(self):
        with pytest.raises(Arithmetic):
            run_output("print ringOldest(newRing(2));")

    def test_a_ring_of_no_places_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output("print newRing(0);")
        assert "at least one place" in str(caught.value)

    def test_a_malformed_ring_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output("print ringSize([1, 2]);")
        assert "list of its contents" in str(caught.value)

    def test_a_ring_with_a_start_out_of_range_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output("print ringSize([[1, 2], 9, 0]);")
        assert "start of 9" in str(caught.value)

    def test_a_ring_with_a_count_out_of_range_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output("print ringSize([[1, 2], 0, 9]);")
        assert "count of 9" in str(caught.value)

    def test_a_ring_with_no_room_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output("print ringSize([[], 0, 0]);")
        assert "room in it" in str(caught.value)

    def test_a_ring_operation_leaves_the_original_alone(self):
        source = "let r = newRing(2); let s = ringPush(r, 1); print ringSize(r);"
        assert run_output(source) == ["0"]


class TestStacks:
    def test_pushing_adds_to_the_end(self):
        assert evaluate("stackPush([1], 2)") == "[1, 2]"

    def test_the_top_is_the_last_added(self):
        assert evaluate("stackTop([1, 2])") == "2"

    def test_popping_removes_the_last(self):
        assert evaluate("stackPop([1, 2])") == "[1]"

    def test_an_empty_stack_is_empty(self):
        assert evaluate("stackEmpty([])") == "true"

    def test_a_stack_with_something_is_not(self):
        assert evaluate("stackEmpty([1])") == "false"

    def test_popping_nothing_is_refused(self):
        with pytest.raises(Arithmetic) as caught:
            run_output("print stackPop([]);")
        assert "stack is empty" in str(caught.value)

    def test_looking_at_nothing_is_refused(self):
        with pytest.raises(Arithmetic):
            run_output("print stackTop([]);")

    def test_a_stack_gives_back_the_newest_first(self):
        source = "let s = [1, 2, 3]; let out = [];"
        source += " while (!stackEmpty(s)) { out = push(out, stackTop(s));"
        source += " s = stackPop(s); } print out;"
        assert run_output(source) == ["[3, 2, 1]"]

    def test_pushing_leaves_the_original_alone(self):
        source = "let a = [1]; let b = stackPush(a, 2); print a;"
        assert run_output(source) == ["[1]"]


class TestBothBackendsAgree:
    @pytest.mark.parametrize(
        "expression",
        [
            "queueToList(queueFrom([1, 2, 3]))",
            "queueFront(queueFrom([1, 2]))",
            "queueToList(dequeue(queueFrom([1, 2, 3])))",
            "queueSize(enqueue(queueFrom([1]), 2))",
            "queueEmpty(newQueue(0))",
            "ringToList(ringPush(ringPush(newRing(3), 1), 2))",
            "ringOldest(ringPush(newRing(2), 5))",
            "ringNewest(ringPush(ringPush(newRing(2), 1), 2))",
            "ringSize(ringPush(newRing(3), 1))",
            "ringCapacity(newRing(4))",
            "ringFull(ringPush(newRing(1), 1))",
            "ringToList(ringOverwrite(ringPush(newRing(1), 1), 2))",
            "stackPush([1], 2)",
            "stackTop([1, 2])",
            "stackPop([1, 2])",
            "stackEmpty([])",
        ],
    )
    def test_the_two_backends_agree(self, expression):
        source = f"print {expression};"
        assert run_output(source) == run_treewalk_output(source)
