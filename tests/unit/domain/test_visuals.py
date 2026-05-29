"""Tests des enums et entités de la fonctionnalité Visualisations."""

from __future__ import annotations

from fahmi2.domain.enums import DiagramType, EdgeType, NodeType


def test_node_types() -> None:
    assert {n.value for n in NodeType} == {
        "concept",
        "glossary_term",
        "example",
        "idea",
    }


def test_edge_types() -> None:
    assert {e.value for e in EdgeType} == {
        "leads_to",
        "prerequisite",
        "illustrates",
        "contrasts_with",
        "part_of",
        "related",
    }


def test_diagram_types() -> None:
    assert {d.value for d in DiagramType} == {
        "flowchart",
        "timeline",
        "comparison",
        "hierarchy",
        "cycle",
        "decision_tree",
    }
