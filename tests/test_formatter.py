from __future__ import annotations

import pytest

from ember.formatter import format_program
from ember.interpreter import run_output
from ember.parser import parse
from ember.scanner import scan

PROGRAMS = [
    "let x=1+2*3;",
    "const PI=3;",
    'if(1>0){print "big";}else{print "small";}',
    'if(1>0)print "one-liner";',
    "let n=3;while(n>0){n=n-1;}",
    "for(let i=0;i<3;i=i+1){print i;}",
    "for(k in [1,2,3])print k;",
    "fn add(a,b){return a+b;}print add(1,2);",
    "class A{init(v){this.v=v;}get(){return this.v;}}print A(4).get();",
    "class A{m(){return 1;}}class B<A{m(){return super.m()+1;}}print B().m();",
    'let m={"a":1,"b":2};print m["a"];',
    "let l=[1,2,3];l[0]=9;print l;",
    "print (1+2)*3;",
    "print 1+2*3;",
    "print (1+2)*(3+4);",
    "print 1-(2-3);",
    "print -(1+2);",
    "print ~(1|2);",
    "print true and false or true;",
    "print not false;",
    "print 1>0?1:2;",
    'try{throw "e";}catch(err){print err;}',
    "fn outer(){let c=0;fn inc(){c=c+1;return c;}return inc;}print outer()();",
    "for(i in [1,2,3]){if(i==2)continue;if(i==3)break;print i;}",
    "let a=[1,2];print len(a);",
    "fn f(){return;}print f();",
    "{ }",
    "class E{}print E;",
    "print 12&10|3^1;",
    "print 1<<3>>1;",
    "let s=0;for(i in [1,2,3])s=s+i;print s;",
]


def formatted(source: str) -> str:
    return format_program(parse(scan(source)))


class TestIdempotence:
    @pytest.mark.parametrize("source", PROGRAMS)
    def test_formatting_twice_changes_nothing(self, source: str):
        once = formatted(source)
        assert formatted(once) == once


class TestMeaningIsPreserved:
    @pytest.mark.parametrize("source", PROGRAMS)
    def test_the_formatted_program_behaves_the_same(self, source: str):
        assert run_output(formatted(source)) == run_output(source)


class TestParentheses:
    @pytest.mark.parametrize(
        ("source", "expected"),
        [
            ("print 1+2*3;", "print 1 + 2 * 3;"),
            ("print (1+2)*3;", "print (1 + 2) * 3;"),
            ("print 2*3+4;", "print 2 * 3 + 4;"),
            ("print 2*(3+4);", "print 2 * (3 + 4);"),
            ("print 1-2-3;", "print 1 - 2 - 3;"),
            ("print 1-(2-3);", "print 1 - (2 - 3);"),
            ("print (1+2)*(3+4);", "print (1 + 2) * (3 + 4);"),
            ("print -(1+2);", "print -(1 + 2);"),
            ("print ~(1|2);", "print ~(1 | 2);"),
        ],
    )
    def test_only_the_needed_parentheses_survive(self, source: str, expected: str):
        assert formatted(source).strip() == expected

    def test_redundant_parentheses_are_dropped(self):
        # the tree records grouping, so a group that changes nothing disappears
        assert formatted("print (1);").strip() == "print 1;"
        assert formatted("print ((1+2));").strip() == "print 1 + 2;"

    def test_comparison_already_binds_tighter_than_equality(self):
        # so no parentheses are needed to keep the meaning
        assert formatted("print (1<2)==true;").strip() == "print 1 < 2 == true;"


class TestLayout:
    def test_a_block_is_indented_two_spaces(self):
        text = formatted('if(1>0){print "a";}')
        assert '  print "a";' in text

    def test_a_nested_block_indents_further(self):
        text = formatted("fn f(){if(1>0){return 1;}}")
        assert "    return 1;" in text

    def test_a_brace_opens_on_the_same_line(self):
        assert formatted("fn f(){return 1;}").startswith("fn f() {")

    def test_an_else_follows_the_closing_brace(self):
        text = formatted('if(1>0){print "a";}else{print "b";}')
        assert "} else {" in text

    def test_an_empty_block_is_compact(self):
        assert formatted("{ }").strip() == "{ }"

    def test_an_empty_class_is_compact(self):
        assert formatted("class E{}").strip() == "class E { }"

    def test_a_method_omits_the_fn_keyword(self):
        text = formatted("class C{m(){return 1;}}")
        assert "  m() {" in text
        assert "fn m" not in text

    def test_a_superclass_is_printed(self):
        assert "class B < A" in formatted("class A{}class B<A{}")

    def test_a_one_line_body_goes_on_its_own_line(self):
        text = formatted('if(1>0)print "x";')
        assert text.splitlines()[0] == "if (1 > 0)"
        assert text.splitlines()[1] == '  print "x";'


class TestStrings:
    def test_a_string_is_requoted(self):
        assert formatted('print "hi";').strip() == 'print "hi";'

    def test_an_embedded_quote_is_escaped(self):
        source = 'print "say \\"hi\\"";'
        assert run_output(formatted(source)) == run_output(source)

    def test_a_newline_escape_survives_a_round_trip(self):
        source = 'print "a\\nb";'
        assert run_output(formatted(source)) == run_output(source)


class TestLiterals:
    def test_the_literal_keywords_print_as_written(self):
        assert formatted("print true; print false; print nil;").strip() == (
            "print true;" + chr(10) + "print false;" + chr(10) + "print nil;"
        )

    def test_a_float_keeps_its_point(self):
        assert formatted("print 2.5;").strip() == "print 2.5;"
