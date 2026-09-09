from __future__ import annotations

from ember.builtins import install_builtins
from ember.interpreter import build
from ember.reachability import (
    Report,
    after_running,
    held_by_globals,
    largest_holders,
    reachable,
    report_of,
)
from ember.vm import VM


def machine_after(source: str) -> VM:
    machine = VM()
    install_builtins(machine)
    machine.interpret(build(source))
    return machine


class TestRoots:
    def test_a_global_is_reachable(self):
        report = after_running("let a = [1, 2, 3];")
        assert report.of_kind("list") >= 1

    def test_the_builtins_are_reachable(self):
        # every native is a global, so they are all held
        assert after_running("print 1;").of_kind("native") > 100

    def test_the_root_count_is_reported(self):
        assert after_running("let a = 1;").roots > 0

    def test_a_value_never_bound_is_not_reachable(self):
        # the list is built and discarded, so nothing leads to it afterwards
        without = after_running("print 1;").of_kind("list")
        discarded = after_running("let x = len([1, 2, 3]);").of_kind("list")
        assert discarded == without


class TestFollowingValues:
    def test_a_list_leads_to_its_elements(self):
        source = "let a = [];"
        source += " for (let i = 0; i < 50; i = i + 1) { a = push(a, i); }"
        assert after_running(source).of_kind("int") >= 50

    def test_a_nested_list_is_followed(self):
        report = after_running("let a = [[1], [2]];")
        assert report.of_kind("list") >= 3

    def test_a_map_leads_to_its_keys_and_values(self):
        source = 'let m = {"key": [1, 2]};'
        report = after_running(source)
        assert report.of_kind("list") >= 1
        assert report.of_kind("string") >= 1

    def test_a_closure_leads_to_what_it_captured(self):
        source = "fn make() { let held = [1, 2, 3]; fn get() { return held; } return get; }"
        source += " let g = make();"
        report = after_running(source)
        assert report.of_kind("closure") >= 1
        assert report.of_kind("upvalue") >= 1

    def test_a_closure_leads_to_its_function(self):
        source = "fn f() { return 1; } let g = f;"
        assert after_running(source).of_kind("function") >= 1

    def test_a_function_leads_to_its_constant_pool(self):
        # a nested function is held by whatever holds the one that could call it
        source = "fn outer() { fn inner() { return 1; } return inner; } let o = outer;"
        assert after_running(source).of_kind("function") >= 2

    def test_an_instance_leads_to_its_fields(self):
        source = "class A { } let a = A(); a.field = [1, 2];"
        report = after_running(source)
        assert report.of_kind("instance") >= 1
        assert report.of_kind("list") >= 1

    def test_an_instance_leads_to_its_class(self):
        source = "class A { m() { return 1; } } let a = A();"
        assert after_running(source).of_kind("class") >= 1

    def test_a_class_leads_to_its_methods(self):
        source = "class A { m() { return 1; } } let a = A;"
        assert after_running(source).of_kind("closure") >= 1

    def test_a_subclass_does_not_lead_to_its_superclass(self):
        # this machine copies methods down, so nothing points upwards
        both = "class A { m() { return 1; } } class B < A { } let b = B();"
        only_sub = "class B { m() { return 1; } } let b = B();"
        assert after_running(both).of_kind("class") > after_running(only_sub).of_kind("class")


class TestCycles:
    def test_a_list_holding_itself_terminates(self):
        report = after_running("let a = []; a = push(a, a);")
        assert report.total > 0

    def test_a_self_referencing_list_is_counted_once(self):
        report = after_running("let a = []; a = push(a, a);")
        plain = after_running("let a = [];")
        assert report.of_kind("list") == plain.of_kind("list")

    def test_two_lists_referring_to_each_other_terminate(self):
        source = "let a = []; let b = []; a = push(a, b); b = push(b, a);"
        assert after_running(source).total > 0

    def test_an_instance_holding_itself_terminates(self):
        source = "class A { } let a = A(); a.self = a;"
        assert after_running(source).of_kind("instance") >= 1


class TestIdentityRatherThanEquality:
    def test_two_equal_lists_count_as_two_values(self):
        # a program holding both is holding twice as much
        one = after_running("let a = [1, 2, 3];").of_kind("list")
        two = after_running("let a = [1, 2, 3]; let b = [1, 2, 3];").of_kind("list")
        assert two == one + 1

    def test_two_bindings_to_one_list_count_as_one(self):
        one = after_running("let a = [1, 2, 3];").of_kind("list")
        shared = after_running("let a = [1, 2, 3]; let b = a;").of_kind("list")
        assert shared == one

    def test_the_walk_returns_values_keyed_by_identity(self):
        machine = machine_after("let a = [1, 2];")
        found = reachable(machine)
        assert all(isinstance(marker, int) for marker in found)


class TestReports:
    def test_the_total_is_the_sum_of_the_counts(self):
        report = after_running("let a = [1, 2]; let b = 3;")
        assert report.total == sum(report.counts.values())

    def test_the_kinds_are_sorted(self):
        report = after_running("let a = [1, 2];")
        assert report.kinds() == sorted(report.kinds())

    def test_an_absent_kind_counts_zero(self):
        assert after_running("let a = 1;").of_kind("nowhere") == 0

    def test_the_report_renders_its_total(self):
        lines = after_running("let a = 1;").render()
        assert "values reachable from" in lines[0]

    def test_the_report_lists_the_kinds(self):
        lines = after_running("let a = [1, 2];")
        assert any("list" in line for line in lines.render())

    def test_the_largest_collections_are_named(self):
        source = "let big = [];"
        source += " for (let i = 0; i < 100; i = i + 1) { big = push(big, i); }"
        report = after_running(source)
        assert any(size >= 100 for _, size in report.biggest)

    def test_the_summary_is_short(self):
        assert after_running("let a = 1;").summary().endswith("reachable")

    def test_an_empty_report_totals_nothing(self):
        assert Report().total == 0

    def test_the_number_of_largest_entries_can_be_chosen(self):
        machine = machine_after("let a = [1]; let b = [2]; let c = [3];")
        assert len(report_of(machine, largest=2).biggest) == 2


class TestHoldersByName:
    def test_a_global_holding_a_large_list_is_named(self):
        source = "let big = [];"
        source += " for (let i = 0; i < 300; i = i + 1) { big = push(big, i); }"
        source += " let small = 1;"
        machine = machine_after(source)
        assert largest_holders(machine, 1)[0][0] == "big"

    def test_the_count_reflects_what_the_name_leads_to(self):
        source = "let big = [];"
        source += " for (let i = 0; i < 50; i = i + 1) { big = push(big, i); }"
        machine = machine_after(source)
        assert held_by_globals(machine)["big"] >= 50

    def test_a_small_global_holds_little(self):
        machine = machine_after("let small = 1;")
        assert held_by_globals(machine)["small"] == 1

    def test_every_global_appears(self):
        machine = machine_after("let a = 1; let b = 2;")
        held = held_by_globals(machine)
        assert "a" in held
        assert "b" in held

    def test_the_holders_are_sorted_by_size(self):
        source = "let big = []; let bigger = [];"
        source += " for (let i = 0; i < 20; i = i + 1) { big = push(big, i); }"
        source += " for (let i = 0; i < 40; i = i + 1) { bigger = push(bigger, i); }"
        machine = machine_after(source)
        found = [name for name, _ in largest_holders(machine, 2)]
        assert found[0] == "bigger"

    def test_a_shared_list_is_counted_under_both_names(self):
        # each name is walked separately, so a shared structure appears under each
        machine = machine_after("let a = [1, 2, 3]; let b = a;")
        held = held_by_globals(machine)
        assert held["a"] == held["b"]


class TestUpvalues:
    def test_a_closed_upvalue_leads_to_its_value(self):
        source = "fn make() { let held = [1, 2]; fn get() { return held; } return get; }"
        source += " let g = make();"
        report = after_running(source)
        assert report.of_kind("upvalue") >= 1
        assert report.of_kind("list") >= 1

    def test_two_closures_sharing_an_upvalue_share_it(self):
        source = "fn make() { let c = 0;"
        source += " fn up() { c = c + 1; return c; } fn down() { c = c - 1; return c; }"
        source += " return [up, down]; } let pair = make();"
        report = after_running(source)
        # one variable captured by two closures is one upvalue, not two
        assert report.of_kind("upvalue") == 1

    def test_a_program_with_no_closures_has_no_upvalues(self):
        assert after_running("let a = 1;").of_kind("upvalue") == 0


class TestAfterRunning:
    def test_a_program_that_grows_holds_more_than_one_that_does_not(self):
        growing = "let a = [];"
        growing += " for (let i = 0; i < 200; i = i + 1) { a = push(a, i); }"
        assert after_running(growing).total > after_running("let a = 1;").total

    def test_folding_does_not_change_what_is_held(self):
        source = "let a = [1, 2, 3];"
        assert after_running(source).total == after_running(source, optimize=True).total

    def test_a_program_printing_nothing_still_holds_its_globals(self):
        assert after_running("let a = [1];").of_kind("list") >= 1
