from __future__ import annotations

import pytest

from ember.errors import Syntax, TypeMismatch, Unbound
from ember.interpreter import run, run_output


class TestInheritedMethods:
    def test_a_subclass_inherits_a_method(self):
        source = 'class A { greet() { return "A"; } } class B < A {} print B().greet();'
        assert run_output(source) == ["A"]

    def test_a_subclass_can_override_a_method(self):
        source = (
            'class A { greet() { return "A"; } }'
            ' class B < A { greet() { return "B"; } }'
            " print B().greet(); print A().greet();"
        )
        assert run_output(source) == ["B", "A"]

    def test_an_inherited_initializer_runs(self):
        source = (
            "class A { init(x) { this.x = x; } } class B < A {}"
            " print B(5).x;"
        )
        assert run_output(source) == ["5"]


class TestSuper:
    def test_super_reaches_the_overridden_method(self):
        source = (
            'class A { greet() { return "A"; } }'
            ' class B < A { greet() { return super.greet() + "+B"; } }'
            " print B().greet();"
        )
        assert run_output(source) == ["A+B"]

    def test_super_init_chains_construction(self):
        source = (
            "class A { init(x) { this.x = x; } }"
            " class B < A { init(x, y) { super.init(x); this.y = y; }"
            " sum() { return this.x + this.y; } }"
            " print B(3, 4).sum();"
        )
        assert run_output(source) == ["7"]

    def test_super_works_through_three_levels(self):
        source = (
            "class A { m() { return 1; } }"
            " class B < A { m() { return super.m() + 1; } }"
            " class C < B { m() { return super.m() + 1; } }"
            " print C().m();"
        )
        assert run_output(source) == ["3"]

    def test_a_subclass_instance_reports_its_own_type(self):
        source = 'class A { name() { return "A"; } } class B < A {} print type(B());'
        assert run_output(source) == ["B"]


class TestInheritanceErrors:
    def test_self_inheritance_is_refused(self):
        with pytest.raises(Syntax):
            run("class A < A {}")

    def test_inheriting_from_a_non_class_is_refused(self):
        with pytest.raises(TypeMismatch):
            run("let x = 1; class B < x {}")

    def test_super_outside_a_method_is_refused(self):
        with pytest.raises(Syntax):
            run("class A {} print super.m();")

    def test_super_without_a_superclass_is_refused(self):
        with pytest.raises(Syntax):
            run("class A { m() { return super.m(); } }")

    def test_super_naming_a_missing_method_is_refused(self):
        with pytest.raises(Unbound):
            run("class A {} class B < A { m() { return super.nope(); } } B().m();")

    def test_super_must_be_followed_by_a_dot_and_name(self):
        with pytest.raises(Syntax):
            run("class A { m() { return 1; } } class B < A { m() { return super; } }")
