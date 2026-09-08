from __future__ import annotations

import pytest

from ember.chunk import Chunk
from ember.classes import BoundMethod, EmberClass, Instance
from ember.closure import Closure
from ember.errors import Arity, Resolve, Syntax, TypeMismatch, Unbound
from ember.function import Function
from ember.interpreter import run, run_output


def _closure(name: str, arity: int = 0) -> Closure:
    return Closure(Function(name, arity, Chunk()))


class TestClassObject:
    def test_a_class_starts_with_no_methods(self):
        assert EmberClass("Point").find_method("m") is None

    def test_a_declared_method_is_found(self):
        klass = EmberClass("Point")
        method = _closure("sum")
        klass.methods["sum"] = method
        assert klass.find_method("sum") is method

    def test_arity_is_zero_without_an_initializer(self):
        assert EmberClass("Point").arity == 0

    def test_arity_follows_the_initializer(self):
        klass = EmberClass("Point")
        klass.methods["init"] = _closure("init", 2)
        assert klass.arity == 2
        assert klass.initializer is not None


class TestInstanceObject:
    def test_an_instance_links_to_its_class_and_has_no_fields(self):
        klass = EmberClass("Point")
        instance = Instance(klass)
        assert instance.klass is klass
        assert instance.fields == {}

    def test_the_repr_names_the_class(self):
        assert "Point" in repr(Instance(EmberClass("Point")))


class TestBoundMethodObject:
    def test_it_remembers_the_receiver(self):
        instance = Instance(EmberClass("Point"))
        method = _closure("sum")
        bound = BoundMethod(instance, method)
        assert bound.receiver is instance
        assert bound.name == "sum"

    def test_it_prints_like_a_plain_function(self):
        bound = BoundMethod(Instance(EmberClass("P")), _closure("sum"))
        assert repr(bound) == "<fn sum>"


class TestMethods:
    def test_a_method_is_called_through_an_instance(self):
        assert run_output('class G { greet() { return "hi"; } } print G().greet();') == ["hi"]

    def test_an_initializer_sets_fields(self):
        source = (
            "class Point { init(x, y) { this.x = x; this.y = y; }"
            " sum() { return this.x + this.y; } }"
            " let p = Point(3, 4); print p.x; print p.sum();"
        )
        assert run_output(source) == ["3", "7"]

    def test_calling_a_class_yields_the_instance_not_nil(self):
        assert run_output("class C { init() { this.v = 1; } } print C().v;") == ["1"]

    def test_a_method_can_return_this_for_chaining(self):
        source = (
            "class Acc { init() { this.t = 0; } add(n) { this.t = this.t + n; return this; } }"
            " print Acc().add(3).add(4).t;"
        )
        assert run_output(source) == ["7"]

    def test_state_persists_across_method_calls(self):
        source = (
            "class C { init() { this.n = 0; } bump() { this.n = this.n + 1; return this.n; } }"
            " let c = C(); print c.bump(); print c.bump();"
        )
        assert run_output(source) == ["1", "2"]


class TestFields:
    def test_a_field_can_be_assigned_after_construction(self):
        source = "class B { init(v) { this.v = v; } } let b = B(1); b.v = 9; print b.v;"
        assert run_output(source) == ["9"]

    def test_a_field_shadows_a_method_of_the_same_name(self):
        source = (
            'class S { name() { return "method"; } }'
            ' let s = S(); s.name = "field"; print s.name;'
        )
        assert run_output(source) == ["field"]

    def test_compound_assignment_works_on_a_field(self):
        source = "class A { init() { this.k = 5; } } let a = A(); a.k += 3; print a.k;"
        assert run_output(source) == ["8"]


class TestBinding:
    def test_a_method_keeps_its_receiver_when_stored(self):
        source = (
            "class D { init(v) { this.v = v; } get() { return this.v; } }"
            " let d = D(7); let f = d.get; print f();"
        )
        assert run_output(source) == ["7"]

    def test_a_nested_function_can_capture_this(self):
        source = (
            "class E { init() { this.v = 9; }"
            " make() { fn inner() { return this.v; } return inner; } }"
            " print E().make()();"
        )
        assert run_output(source) == ["9"]


class TestTypeReporting:
    def test_a_class_and_an_instance_report_their_kinds(self):
        assert run_output("class T { m() { return 1; } } print type(T); print type(T());") == [
            "class",
            "T",
        ]

    def test_printing_a_class_and_an_instance(self):
        assert run_output("class T {} print T; print T();") == ["<class T>", "<T instance>"]


class TestClassErrors:
    def test_this_outside_a_method_is_refused(self):
        with pytest.raises(Syntax):
            run("print this;")

    def test_an_initializer_returning_a_value_is_refused(self):
        with pytest.raises(Syntax):
            run("class C { init() { return 5; } }")

    def test_a_duplicate_method_is_refused(self):
        with pytest.raises(Resolve):
            run("class C { m() { return 1; } m() { return 2; } }")

    def test_a_property_on_a_non_instance_is_refused(self):
        with pytest.raises(TypeMismatch):
            run("let x = 5; print x.field;")

    def test_a_missing_property_is_refused(self):
        with pytest.raises(Unbound):
            run("class C {} print C().missing;")

    def test_arguments_to_a_class_without_an_initializer_are_refused(self):
        with pytest.raises(Arity):
            run("class C {} C(1);")

    def test_the_wrong_initializer_arity_is_refused(self):
        with pytest.raises(Arity):
            run("class C { init(a) { this.a = a; } } C();")
