from __future__ import annotations

from ember.docgen import (
    ClassDoc,
    FunctionDoc,
    Parameter,
    ValueDoc,
    coverage_of,
    describe,
    render,
)

NEWLINE = chr(10)
QUOTE = chr(34)


def program(*lines: str) -> str:
    return NEWLINE.join(lines) + NEWLINE


DOCUMENTED = program(
    "// how many times to try",
    "const RETRIES = 3;",
    "",
    "// Add two numbers together.",
    "// Both must be numbers.",
    "fn add(a, b) {",
    "  return a + b;",
    "}",
    "",
    "fn bare(x) {",
    "  return x;",
    "}",
    "",
    "// A point in the plane.",
    "class Point {",
    "  // Build a point.",
    "  init(x, y) {",
    "    this.x = x;",
    "  }",
    "",
    "  reach() {",
    "    return this.x;",
    "  }",
    "}",
)


class TestSignatures:
    def test_a_plain_function_lists_its_parameters(self):
        assert describe("fn f(a, b) { return a; }").functions[0].signature() == "f(a, b)"

    def test_a_function_with_no_parameters(self):
        assert describe("fn f() { return 1; }").functions[0].signature() == "f()"

    def test_a_default_is_shown(self):
        assert describe("fn f(a = 2) { return a; }").functions[0].signature() == "f(a = 2)"

    def test_a_string_default_keeps_its_quotes(self):
        source = "fn f(a = " + QUOTE + "hi" + QUOTE + ") { return a; }"
        expected = "f(a = " + QUOTE + "hi" + QUOTE + ")"
        assert describe(source).functions[0].signature() == expected

    def test_a_rest_parameter_is_marked(self):
        found = describe("fn f(...rest) { return 1; }").functions[0]
        assert found.signature() == "f(...rest)"
        assert found.is_variadic

    def test_a_default_attaches_to_the_right_parameter(self):
        # the defaults cover the last named parameters, not the first
        source = "fn f(x, y = 2, ...rest) { return x; }"
        assert describe(source).functions[0].signature() == "f(x, y = 2, ...rest)"

    def test_two_defaults_attach_in_order(self):
        source = "fn f(a = 1, b = 2) { return a; }"
        assert describe(source).functions[0].signature() == "f(a = 1, b = 2)"

    def test_a_required_parameter_before_a_default_stays_required(self):
        found = describe("fn f(x, y = 2) { return x; }").functions[0]
        assert found.required == 1

    def test_a_function_with_only_defaults_requires_nothing(self):
        assert describe("fn f(a = 1) { return a; }").functions[0].required == 0

    def test_a_rest_parameter_is_not_required(self):
        assert describe("fn f(...rest) { return 1; }").functions[0].required == 0

    def test_a_plain_function_is_not_variadic(self):
        assert not describe("fn f(a) { return a; }").functions[0].is_variadic


class TestComments:
    def test_a_comment_above_a_function_is_attached(self):
        found = describe(DOCUMENTED).function_named("add")
        assert found.comment == "Add two numbers together. Both must be numbers."

    def test_a_function_with_no_comment_has_none(self):
        assert describe(DOCUMENTED).function_named("bare").comment == ""

    def test_a_comment_above_a_class_is_attached(self):
        assert describe(DOCUMENTED).class_named("Point").comment == "A point in the plane."

    def test_a_comment_above_a_method_is_attached(self):
        found = describe(DOCUMENTED).class_named("Point").method_named("init")
        assert found.comment == "Build a point."

    def test_a_method_with_no_comment_has_none(self):
        found = describe(DOCUMENTED).class_named("Point").method_named("reach")
        assert found.comment == ""

    def test_a_comment_above_a_value_is_attached(self):
        assert describe(DOCUMENTED).values[0].comment == "how many times to try"

    def test_a_comment_separated_by_a_blank_line_is_not_attached(self):
        source = program("// detached", "", "fn f() { return 1; }")
        assert describe(source).functions[0].comment == ""

    def test_a_comment_after_code_on_the_line_above_is_not_attached(self):
        source = program("print 1;", "fn f() { return 1; }")
        assert describe(source).functions[0].comment == ""

    def test_several_comment_lines_join_in_source_order(self):
        source = program("// first", "// second", "fn f() { return 1; }")
        assert describe(source).functions[0].comment == "first second"

    def test_a_comment_on_the_very_first_line_is_attached(self):
        source = program("// leading", "fn f() { return 1; }")
        assert describe(source).functions[0].comment == "leading"


class TestClasses:
    def test_a_class_lists_its_methods(self):
        found = describe(DOCUMENTED).class_named("Point")
        assert [method.name for method in found.methods] == ["init", "reach"]

    def test_a_class_with_no_superclass_says_only_its_name(self):
        assert describe("class C { }").classes[0].signature() == "class C"

    def test_a_subclass_names_what_it_inherits(self):
        source = "class A { } class B < A { }"
        assert describe(source).class_named("B").signature() == "class B < A"

    def test_a_superclass_is_recorded(self):
        source = "class A { } class B < A { }"
        assert describe(source).class_named("B").superclass == "A"

    def test_a_class_with_no_superclass_records_none(self):
        assert describe("class C { }").classes[0].superclass is None

    def test_a_method_that_is_absent_is_not_found(self):
        assert describe("class C { }").classes[0].method_named("nope") is None


class TestValues:
    def test_a_const_is_marked_as_one(self):
        assert describe("const X = 1;").values[0].is_const

    def test_a_let_is_not(self):
        assert not describe("let x = 1;").values[0].is_const

    def test_a_const_renders_with_its_keyword(self):
        assert describe("const X = 1;").values[0].render()[0] == "const X"

    def test_a_let_renders_with_its_keyword(self):
        assert describe("let x = 1;").values[0].render()[0] == "let x"

    def test_a_local_inside_a_function_is_not_top_level(self):
        assert describe("fn f() { let inner = 1; return inner; }").values == []


class TestCounting:
    def test_the_count_covers_every_kind(self):
        found = describe(DOCUMENTED)
        assert found.count == 4

    def test_the_documented_count_excludes_the_bare_ones(self):
        assert describe(DOCUMENTED).documented == 3

    def test_the_undocumented_are_named(self):
        assert describe(DOCUMENTED).undocumented() == ["bare"]

    def test_the_share_is_a_percentage(self):
        assert coverage_of(DOCUMENTED) == 75

    def test_a_fully_documented_program_reaches_a_hundred(self):
        source = program("// said", "fn f() { return 1; }")
        assert coverage_of(source) == 100

    def test_a_program_declaring_nothing_counts_as_complete(self):
        assert coverage_of("print 1;") == 100

    def test_a_program_declaring_nothing_has_no_entries(self):
        assert describe("print 1;").count == 0


class TestRendering:
    def test_the_reference_groups_by_kind(self):
        rendered = render(DOCUMENTED)
        assert "values" in rendered
        assert "functions" in rendered
        assert "classes" in rendered

    def test_a_signature_appears(self):
        assert "add(a, b)" in render(DOCUMENTED)

    def test_a_comment_appears_below_its_signature(self):
        lines = render(DOCUMENTED).split(NEWLINE)
        at = next(i for i, line in enumerate(lines) if "add(a, b)" in line)
        assert "Add two numbers together." in lines[at + 1]

    def test_a_method_is_indented_under_its_class(self):
        lines = render(DOCUMENTED).split(NEWLINE)
        assert any(line.startswith("    init(x, y)") for line in lines)

    def test_a_program_with_only_functions_has_no_other_headings(self):
        rendered = render("fn f() { return 1; }")
        assert "functions" in rendered
        assert "classes" not in rendered

    def test_a_program_declaring_nothing_renders_empty(self):
        assert render("print 1;") == ""


class TestRecords:
    def test_a_parameter_renders_plainly(self):
        assert Parameter(name="a").render() == "a"

    def test_a_parameter_with_a_default_renders_it(self):
        assert Parameter(name="a", default="1").render() == "a = 1"

    def test_a_rest_parameter_ignores_a_default(self):
        assert Parameter(name="r", default="1", is_rest=True).render() == "...r"

    def test_a_function_doc_renders_its_comment_indented(self):
        doc = FunctionDoc(name="f", comment="says something")
        assert doc.render() == ["f()", "  says something"]

    def test_a_function_doc_without_a_comment_renders_one_line(self):
        assert FunctionDoc(name="f").render() == ["f()"]

    def test_a_class_doc_renders_its_methods(self):
        doc = ClassDoc(name="C", methods=[FunctionDoc(name="m")])
        assert doc.render() == ["class C", "  m()"]

    def test_a_value_doc_renders_its_comment(self):
        doc = ValueDoc(name="x", comment="a thing")
        assert doc.render() == ["let x", "  a thing"]

    def test_a_declaration_records_its_line(self):
        source = program("print 1;", "fn f() { return 1; }")
        assert describe(source).functions[0].line == 2
