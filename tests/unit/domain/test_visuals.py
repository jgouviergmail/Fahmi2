"""Tests des enums et entités de la fonctionnalité Visualisations."""

from __future__ import annotations

import pytest

from fahmi2.domain.enums import (
    DiagramType,
    EdgeType,
    Language,
    NodeType,
    SupportDensity,
)
from fahmi2.domain.visuals import (
    ComparisonTable,
    Diagram,
    GraphEdge,
    GraphNode,
    KnowledgeGraph,
    TimelineEvent,
    VisualsSettings,
)


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


def test_graph_node_minimal() -> None:
    node = GraphNode(
        id="concept:bilan",
        label="Bilan",
        node_type=NodeType.CONCEPT,
        definition=None,
        excerpts=(),
        chapter_anchor=None,
        community_path=(),
    )
    assert node.id == "concept:bilan"


def test_knowledge_graph_rejette_arete_vers_noeud_inconnu() -> None:
    node = GraphNode(
        id="concept:a",
        label="A",
        node_type=NodeType.CONCEPT,
        definition=None,
        excerpts=(),
        chapter_anchor=None,
        community_path=(),
    )
    edge = GraphEdge(
        source_id="concept:a",
        target_id="concept:inconnu",
        edge_type=EdgeType.RELATED,
        label=None,
    )
    with pytest.raises(ValueError):
        KnowledgeGraph(
            nodes=(node,), edges=(edge,), communities=(), language=Language.FR
        )


def test_knowledge_graph_rejette_ids_dupliques() -> None:
    node = GraphNode(
        id="concept:a",
        label="A",
        node_type=NodeType.CONCEPT,
        definition=None,
        excerpts=(),
        chapter_anchor=None,
        community_path=(),
    )
    with pytest.raises(ValueError):
        KnowledgeGraph(
            nodes=(node, node), edges=(), communities=(), language=Language.FR
        )


def test_diagram_flowchart_exige_nodes() -> None:
    with pytest.raises(ValueError):
        Diagram(
            id="d1",
            title="T",
            diagram_type=DiagramType.FLOWCHART,
            nodes=(),
            links=(),
            events=(),
            comparison=None,
            caption="c",
            chapter_anchor="2-x",
            excerpts=(),
        )


def test_diagram_timeline_exige_events() -> None:
    diagram = Diagram(
        id="d2",
        title="Chute d'Enron",
        diagram_type=DiagramType.TIMELINE,
        nodes=(),
        links=(),
        events=(TimelineEvent(date_label="2001", title="Faillite", detail=None),),
        comparison=None,
        caption="c",
        chapter_anchor="2-x",
        excerpts=(),
    )
    assert diagram.events[0].date_label == "2001"


def test_comparison_table_rejette_ligne_de_mauvaise_largeur() -> None:
    with pytest.raises(ValueError):
        ComparisonTable(columns=("A", "B"), rows=(("x",),))


def test_visuals_settings_defaults() -> None:
    settings = VisualsSettings()
    assert settings.produce_knowledge_map is True
    assert settings.produce_diagrams is True
    assert settings.density is SupportDensity.STANDARD
    assert settings.diagram_types == frozenset(DiagramType)
    assert settings.llm_workers == 16
    assert settings.cost_ceiling_usd is None


def test_visuals_settings_rejette_workers_invalides() -> None:
    with pytest.raises(ValueError):
        VisualsSettings(llm_workers=0)


def test_visuals_settings_rejette_cout_negatif() -> None:
    with pytest.raises(ValueError):
        VisualsSettings(cost_ceiling_usd=-1.0)
