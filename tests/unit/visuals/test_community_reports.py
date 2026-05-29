"""Tests des rapports de communauté (2.3) et des enchaînements inter-communautés (2.4)."""

from __future__ import annotations

import json
from collections.abc import Mapping

from fahmi2.core.concurrency.pause_token import PauseToken
from fahmi2.core.retry.policy import RetryPolicy
from fahmi2.domain.enums import EdgeType, Language, NodeType
from fahmi2.domain.visuals import (
    GraphEdge,
    GraphNode,
    KnowledgeGraph,
    VisualsSettings,
)
from fahmi2.infra.llm._fakes import FakeLLMProvider
from fahmi2.infra.llm.interface import LLMResponse
from fahmi2.infra.prompts.loader import PromptLoader
from fahmi2.pipeline.event_bus import EventBus
from fahmi2.visuals.community import assemble_graph
from fahmi2.visuals.events import VisualsEvent
from fahmi2.visuals.extractors._base import VisualsContext
from fahmi2.visuals.extractors.community_reporter import generate_community_reports
from fahmi2.visuals.extractors.idea_chains import generate_idea_chains


def _response(payload: Mapping[str, object]) -> LLMResponse:
    return LLMResponse(
        content=json.dumps(payload, ensure_ascii=False),
        thinking_content=None,
        prompt_tokens=10,
        completion_tokens=10,
        cached_prompt_tokens=0,
        cost_usd=0.002,
    )


def _ctx(provider: FakeLLMProvider) -> VisualsContext:
    return VisualsContext(
        settings=VisualsSettings(),
        llm_provider=provider,
        prompts=PromptLoader(),
        event_bus=EventBus[VisualsEvent](),
        pause_token=PauseToken(),
        retry_policy=RetryPolicy(
            max_attempts=3, jitter=False, initial_delay_seconds=0.001
        ),
    )


def _node(node_id: str) -> GraphNode:
    return GraphNode(
        id=node_id,
        label=node_id,
        node_type=NodeType.CONCEPT,
        definition=None,
        excerpts=(),
        chapter_anchor=None,
        community_path=(),
    )


def _two_communities() -> KnowledgeGraph:
    nodes = tuple(_node(n) for n in ("a1", "a2", "a3", "b1", "b2", "b3"))
    edges = (
        GraphEdge("a1", "a2", EdgeType.RELATED, None),
        GraphEdge("a2", "a3", EdgeType.RELATED, None),
        GraphEdge("a1", "a3", EdgeType.RELATED, None),
        GraphEdge("b1", "b2", EdgeType.RELATED, None),
        GraphEdge("b2", "b3", EdgeType.RELATED, None),
        GraphEdge("b1", "b3", EdgeType.RELATED, None),
    )
    return assemble_graph(nodes, edges, language=Language.FR)


def test_community_reports_remplit_label_et_report() -> None:
    provider = FakeLLMProvider(
        default_response=_response({"label": "Comptabilité", "report": "Synthèse."})
    )
    graph, cost = generate_community_reports(
        _ctx(provider), _two_communities(), language=Language.FR
    )
    assert all(
        c.label == "Comptabilité" and c.report == "Synthèse."
        for c in graph.communities
    )
    assert cost == 0.002 * len(graph.communities)
    assert len(provider.calls) == len(graph.communities)


def test_community_reports_graphe_sans_communaute() -> None:
    empty = KnowledgeGraph(nodes=(), edges=(), communities=(), language=Language.FR)
    provider = FakeLLMProvider(default_response=_response({"label": "x", "report": "y"}))
    graph, cost = generate_community_reports(_ctx(provider), empty, language=Language.FR)
    assert graph.communities == ()
    assert cost == 0.0
    assert provider.calls == []


def test_idea_chains_ajoute_une_arete_inter_communautes() -> None:
    base = _two_communities()
    provider = FakeLLMProvider(
        default_response=_response(
            {"relations": [{"source": 0, "target": 1, "type": "leads_to", "label": "mène"}]}
        )
    )
    graph, cost = generate_idea_chains(_ctx(provider), base, language=Language.FR)
    assert len(graph.edges) == len(base.edges) + 1
    new_edge = next(e for e in graph.edges if e.edge_type is EdgeType.LEADS_TO)
    # relie deux nœuds de communautés différentes (représentants).
    path_of = {n.id: n.community_path[0] for n in graph.nodes}
    assert path_of[new_edge.source_id] != path_of[new_edge.target_id]
    assert cost == 0.002


def test_idea_chains_sans_assez_de_communautes() -> None:
    single = assemble_graph((_node("x"),), (), language=Language.FR)
    provider = FakeLLMProvider(default_response=_response({"relations": []}))
    graph, cost = generate_idea_chains(_ctx(provider), single, language=Language.FR)
    assert graph.edges == ()
    assert cost == 0.0
    assert provider.calls == []
