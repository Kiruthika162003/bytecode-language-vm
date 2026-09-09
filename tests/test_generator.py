from __future__ import annotations

import pytest

from ember.errors import EmberError
from ember.generator import Generator, Scope, program_for, programs
from ember.interpreter import run_output
from ember.parser import parse
from ember.scanner import scan


class TestScope:
    def test_a_fresh_scope_has_no_names(self):
        scope = Scope()
        assert not scope.has_numbers()
        assert scope.functions == []

    def test_the_next_name_avoids_what_is_taken(self):
        scope = Scope(numbers=["a", "b"], strings=["c"])
        assert scope.next_name == "d"

    def test_it_keeps_going_when_the_alphabet_runs_out(self):
        scope = Scope(numbers=list("abcdefgh"))
        assert scope.next_name not in scope.numbers

    def test_a_bound_number_is_reported(self):
        assert Scope(numbers=["a"]).has_numbers()


class TestDeterminism:
    def test_the_same_seed_gives_the_same_program(self):
        assert program_for(11) == program_for(11)

    def test_different_seeds_usually_differ(self):
        assert program_for(1) != program_for(2)

    def test_the_depth_changes_what_comes_out(self):
        assert program_for(5, depth=1) != program_for(5, depth=4)

    def test_a_batch_is_reproducible(self):
        assert programs(4, first_seed=20) == programs(4, first_seed=20)

    def test_a_batch_has_the_count_asked_for(self):
        assert len(programs(7)) == 7


class TestGeneratedProgramsParse:
    @pytest.mark.parametrize("seed", range(30))
    def test_every_program_parses(self, seed):
        parse(scan(program_for(seed)))

    @pytest.mark.parametrize("seed", range(30))
    def test_every_program_runs_without_refusing(self, seed):
        # the generator only builds what is certain to compile and to terminate
        run_output(program_for(seed))

    @pytest.mark.parametrize("statements", [1, 3, 12])
    def test_a_longer_program_still_runs(self, statements):
        run_output(program_for(99, statements))

    def test_every_program_prints_something(self):
        for seed in range(20):
            assert run_output(program_for(seed))


class TestExpressionShapes:
    def test_a_number_expression_evaluates_to_a_number(self):
        maker = Generator(seed=3)
        for _ in range(30):
            printed = run_output(f"print {maker.number_expression()};")
            assert printed
            float(printed[0])

    def test_a_string_expression_evaluates_without_refusing(self):
        maker = Generator(seed=4)
        for _ in range(20):
            assert run_output(f"print {maker.string_expression()};")

    def test_a_condition_evaluates_to_a_boolean(self):
        maker = Generator(seed=5)
        for _ in range(20):
            printed = run_output(f"print {maker.condition()};")
            assert printed[0] in ("true", "false")

    def test_a_zero_depth_expression_is_a_leaf(self):
        maker = Generator(seed=6)
        leaf = maker.number_expression(0)
        assert "(" not in leaf

    def test_no_division_is_ever_by_a_zero_literal(self):
        # a literal divisor is how the generator avoids drowning in one fault
        for seed in range(40):
            assert "/ 0)" not in program_for(seed)
            assert "% 0)" not in program_for(seed)


class TestNothingIsUnbound:
    @pytest.mark.parametrize("seed", range(25))
    def test_no_program_reads_a_name_it_did_not_bind(self, seed):
        # an unbound name would refuse at runtime, so a clean run is the proof
        run_output(program_for(seed))

    def test_a_block_does_not_leak_its_locals(self):
        # the scope tracks what was emitted, so a program must be kept whole: a
        # generator whose statements are discarded will name a binding it dropped
        maker = Generator(seed=8)
        emitted = [maker.statement() for _ in range(10)]
        run_output(chr(10).join(emitted) + chr(10) + "print 1;" + chr(10))

    def test_a_loop_variable_does_not_escape_the_loop(self):
        for seed in range(15):
            run_output(program_for(seed, 8))


class TestTermination:
    @pytest.mark.parametrize("seed", range(15))
    def test_every_program_finishes(self, seed):
        # every generated loop counts over a fixed range, so none can spin
        run_output(program_for(seed, 10))

    def test_no_while_loop_is_ever_generated(self):
        for seed in range(40):
            assert "while" not in program_for(seed)


class TestRefusalsStayPossible:
    def test_a_hand_written_fault_still_refuses(self):
        # the generator avoids faults; the language must still produce them
        with pytest.raises(EmberError):
            run_output("print 1 / 0;")

    def test_an_unbound_name_still_refuses(self):
        with pytest.raises(EmberError):
            run_output("print nowhere;")
