from __future__ import annotations

import re

import pytest

from ember.cfg import build_graph, graph_of
from ember.dotgraph import (
    _escaped,
    function_to_dot,
    program_to_dot,
    summary_of,
    to_dot,
)
from ember.function import Function
from ember.instructions import Program
from ember.interpreter import build
from ember.traces.verifytrace import CORPUS

NEWLINE = chr(10)
QUOTE = chr(34)

LOOPING = "let s = 0;" + NEWLINE + "while (s < 3) { s = s + 1; }" + NEWLINE
NESTED = "fn f(n) { if (n < 2) return n; return f(n-1); }" + NEWLINE + LOOPING


def edges_of(text: str) -> list[tuple[str, str]]:
    """Only whole lines that are edges: an arrow inside a label is not one."""
    found = [re.match(r"^\s*(\w+) -> (\w+);$", line) for line in text.splitlines()]
    return [match.groups() for match in found if match]


def declared_in(text: str) -> set[str]:
    return set(re.findall(r"^\s*(\w+) \[label=", text, re.M))


class TestOneGraph:
    def test_the_document_opens_and_closes(self):
        text = to_dot(graph_of(build(LOOPING)))
        assert text.startswith("digraph")
        assert text.rstrip().endswith("}")

    def test_the_braces_balance(self):
        text = to_dot(graph_of(build(LOOPING)))
        assert text.count("{") == text.count("}")

    def test_the_name_is_used(self):
        assert to_dot(graph_of(build(LOOPING)), "chosen").startswith("digraph chosen")

    def test_there_is_a_node_per_block(self):
        graph = graph_of(build(LOOPING))
        assert len(declared_in(to_dot(graph))) == graph.count

    def test_there_is_an_edge_per_successor(self):
        graph = graph_of(build(LOOPING))
        expected = sum(len(block.successors) for block in graph.blocks)
        assert len(edges_of(to_dot(graph))) == expected

    def test_every_edge_names_a_declared_node(self):
        text = to_dot(graph_of(build(LOOPING)))
        declared = declared_in(text)
        for first, second in edges_of(text):
            assert first in declared
            assert second in declared

    def test_a_node_carries_its_instructions(self):
        text = to_dot(graph_of(build("print 1 + 2;")))
        assert "ADD" in text

    def test_a_node_carries_its_number(self):
        assert "block 0" in to_dot(graph_of(build("print 1;")))

    def test_a_long_block_is_truncated(self):
        source = "print 1; print 2; print 3; print 4; print 5; print 6; print 7;"
        assert "more" in to_dot(graph_of(build(source)))

    def test_a_loop_header_is_marked(self):
        assert "peripheries=2" in to_dot(graph_of(build(LOOPING)))

    def test_a_program_with_no_loop_marks_no_header(self):
        assert "peripheries=2" not in to_dot(graph_of(build("print 1;")))

    def test_an_unreachable_block_is_marked(self):
        program = build("fn f() { return 1; } print f();")
        inner = next(c for c in program.chunk.constants if isinstance(c, Function))
        assert "style=dashed" in to_dot(graph_of(inner))

    def test_a_reachable_program_marks_nothing_dashed(self):
        assert "style=dashed" not in to_dot(graph_of(build("print 1;")))

    def test_an_empty_graph_renders_an_empty_document(self):
        text = to_dot(build_graph(Program()))
        assert edges_of(text) == []
        assert declared_in(text) == set()

    def test_a_function_can_be_rendered_directly(self):
        assert function_to_dot(build("print 1;")).startswith("digraph")


class TestWholePrograms:
    def test_each_function_gets_a_cluster(self):
        text = program_to_dot(build(NESTED))
        assert text.count("subgraph cluster_") == 2

    def test_the_script_is_labelled(self):
        assert "<script>" in program_to_dot(build(NESTED))

    def test_a_named_function_is_labelled(self):
        text = program_to_dot(build(NESTED))
        assert QUOTE + "f" + QUOTE in text

    def test_every_edge_names_a_declared_node(self):
        # the bug this caught: renaming only the first name on an edge line left
        # every arrow pointing at whatever node held that name in another cluster
        text = program_to_dot(build(NESTED))
        declared = declared_in(text)
        for first, second in edges_of(text):
            assert first in declared
            assert second in declared

    def test_every_edge_stays_inside_its_cluster(self):
        text = program_to_dot(build(NESTED))
        for first, second in edges_of(text):
            assert first.split("b")[0] == second.split("b")[0]

    def test_the_node_names_do_not_collide_between_functions(self):
        text = program_to_dot(build(NESTED))
        assert "f0b0" in text
        assert "f1b0" in text

    def test_the_braces_balance(self):
        text = program_to_dot(build(NESTED))
        assert text.count("{") == text.count("}")

    def test_a_program_with_one_function_has_one_cluster(self):
        assert program_to_dot(build("print 1;")).count("subgraph cluster_") == 1

    def test_a_program_with_a_class_gets_a_cluster_per_method(self):
        source = "class A { m() { return 1; } n() { return 2; } } print A().m();"
        assert program_to_dot(build(source)).count("subgraph cluster_") == 3


class TestEscaping:
    def test_a_backslash_in_a_label_is_escaped(self):
        # defensive: no label this module builds holds one, and one later might
        assert _escaped(chr(92)) == chr(92) + chr(92)

    def test_a_quote_in_a_label_is_escaped(self):
        assert _escaped(QUOTE) == chr(92) + QUOTE

    def test_a_newline_becomes_its_escape(self):
        # this one is genuinely required, since a node holds several lines
        assert _escaped(NEWLINE) == chr(92) + "n"

    def test_no_label_holds_a_raw_newline(self):
        for line in to_dot(graph_of(build(LOOPING))).splitlines():
            assert NEWLINE not in line

    def test_the_quotes_around_a_label_balance(self):
        for line in to_dot(graph_of(build(LOOPING))).splitlines():
            if "label=" in line:
                unescaped = line.replace(chr(92) + QUOTE, "")
                assert unescaped.count(QUOTE) % 2 == 0


class TestTheCorpus:
    @pytest.mark.parametrize("source", CORPUS)
    def test_every_corpus_program_renders(self, source):
        text = program_to_dot(build(source))
        assert text.count("{") == text.count("}")

    @pytest.mark.parametrize("source", CORPUS)
    def test_every_edge_resolves(self, source):
        text = program_to_dot(build(source))
        declared = declared_in(text)
        for first, second in edges_of(text):
            assert first in declared
            assert second in declared

    @pytest.mark.parametrize("source", CORPUS[:8])
    def test_every_document_is_ascii(self, source):
        text = program_to_dot(build(source))
        assert all(ord(character) < 128 for character in text)


class TestThePlainListing:
    def test_there_is_a_line_per_block(self):
        graph = graph_of(build(LOOPING))
        assert len(summary_of(graph)) == graph.count

    def test_a_block_says_where_it_goes(self):
        lines = summary_of(graph_of(build(LOOPING)))
        assert any("goes to" in line for line in lines)

    def test_a_block_with_no_successor_says_nothing_follows(self):
        lines = summary_of(graph_of(build("print 1;")))
        assert any("goes to nothing" in line for line in lines)

    def test_a_loop_header_is_named(self):
        lines = summary_of(graph_of(build(LOOPING)))
        assert any("loop header" in line for line in lines)

    def test_an_unreachable_block_is_named(self):
        program = build("fn f() { return 1; } print f();")
        inner = next(c for c in program.chunk.constants if isinstance(c, Function))
        assert any("unreachable" in line for line in summary_of(graph_of(inner)))

    def test_a_plain_program_marks_nothing(self):
        lines = summary_of(graph_of(build("print 1;")))
        assert not any("(" in line for line in lines)

    def test_an_empty_graph_lists_nothing(self):
        assert summary_of(build_graph(Program())) == []
