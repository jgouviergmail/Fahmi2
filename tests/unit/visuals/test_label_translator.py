"""Tests de la localisation par langue (graphe + diagrammes)."""

from __future__ import annotations

import json
from collections.abc import Mapping

from fahmi2.core.concurrency.pause_token import PauseToken
from fahmi2.core.retry.policy import RetryPolicy
from fahmi2.domain.enums import DiagramType, EdgeType, Language, NodeType
from fahmi2.domain.glossary import Term, parse_glossary_master_terms
from fahmi2.domain.visuals import (
    Community,
    Diagram,
    DiagramBoard,
    DiagramLink,
    DiagramNode,
    GraphEdge,
    GraphNode,
    KnowledgeGraph,
    SourceExcerpt,
    VisualsSettings,
)
from fahmi2.infra.llm._fakes import FakeLLMProvider
from fahmi2.infra.llm.interface import LLMResponse
from fahmi2.infra.prompts.loader import PromptLoader
from fahmi2.pipeline.event_bus import EventBus
from fahmi2.visuals.events import VisualsEvent
from fahmi2.visuals.extractors._base import VisualsContext
from fahmi2.visuals.extractors.label_translator import localize_board, localize_graph
from fahmi2.visuals.sources import TextUnit

_SRC_PATH = (1, 1)


def _response(payload: Mapping[str, object]) -> LLMResponse:
    return LLMResponse(
        content=json.dumps(payload, ensure_ascii=False),
        thinking_content=None,
        prompt_tokens=10,
        completion_tokens=10,
        cached_prompt_tokens=0,
        cost_usd=0.003,
    )


def _provider(strings: set[str]) -> FakeLLMProvider:
    """Provider dont la traduction de chaque chaîne est ``EN[<source>]`` (pairée par ordre)."""
    translations = [f"EN[{source}]" for source in sorted(strings)]
    return FakeLLMProvider(default_response=_response({"translations": translations}))


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


def _glossary() -> tuple[Term, ...]:
    return parse_glossary_master_terms(
        {
            "terms": [
                {
                    "term": "Actif",
                    "definition": "Biens.",
                    "aliases": [],
                    "sources": [],
                    "cross_lang": {"en": {"term": "Asset", "definition": "Owned goods."}},
                }
            ]
        }
    )


def _src_excerpt() -> SourceExcerpt:
    return SourceExcerpt(
        text="Texte source sur le bilan.",
        section_path=_SRC_PATH,
        chapter_title="Le bilan",
        anchor="11-le-bilan",
    )


def _target_units() -> tuple[TextUnit, ...]:
    return (
        TextUnit(
            section_path=_SRC_PATH,
            title="The balance sheet",
            anchor="11-the-balance-sheet",
            text="English passage about the balance sheet.",
            part=0,
        ),
    )


def _source_graph() -> KnowledgeGraph:
    nodes = (
        GraphNode(
            id="glossary_term:actif", label="Actif", node_type=NodeType.GLOSSARY_TERM,
            definition="Biens.", excerpts=(_src_excerpt(),),
            chapter_anchor="11-le-bilan", community_path=(0,),
        ),
        GraphNode(
            id="concept:bilan", label="Bilan", node_type=NodeType.CONCEPT,
            definition="Doc.", excerpts=(_src_excerpt(),),
            chapter_anchor="11-le-bilan", community_path=(0,),
        ),
    )
    edges = (GraphEdge("concept:bilan", "glossary_term:actif", EdgeType.PART_OF, "compose"),)
    communities = (
        Community(id=0, label="Comptabilité", report="Synthèse.", level=0,
                  member_ids=("concept:bilan", "glossary_term:actif"), parent_id=None),
    )
    return KnowledgeGraph(nodes=nodes, edges=edges, communities=communities, language=Language.FR)


def test_localize_graph_glossaire_libelles_et_extraits() -> None:
    strings = {"Bilan", "Doc.", "compose", "Comptabilité", "Synthèse."}
    provider = _provider(strings)
    graph, cost = localize_graph(
        _ctx(provider),
        _source_graph(),
        target_language=Language.EN,
        glossary=_glossary(),
        target_units=_target_units(),
    )
    by_id = {n.id: n for n in graph.nodes}
    # glossaire : terme + définition via cross_lang (pas via la table).
    assert by_id["glossary_term:actif"].label == "Asset"
    assert by_id["glossary_term:actif"].definition == "Owned goods."
    # concept : libellé + définition traduits.
    assert by_id["concept:bilan"].label == "EN[Bilan]"
    assert by_id["concept:bilan"].definition == "EN[Doc.]"
    # relation + communauté traduites.
    assert graph.edges[0].label == "EN[compose]"
    assert graph.communities[0].label == "EN[Comptabilité]"
    assert graph.communities[0].report == "EN[Synthèse.]"
    # extraits re-dérivés dans la langue cible (par section_path).
    excerpt = by_id["concept:bilan"].excerpts[0]
    assert excerpt.text == "English passage about the balance sheet."
    assert excerpt.anchor == "11-the-balance-sheet"
    assert by_id["concept:bilan"].chapter_anchor == "11-the-balance-sheet"
    assert graph.language is Language.EN
    assert cost == 0.003
    assert len(provider.calls) == 1  # un seul appel de traduction par lot


def test_localize_board_traduit_et_re_extrait() -> None:
    diagram = Diagram(
        id="diagram:1-1:0", title="Processus", diagram_type=DiagramType.FLOWCHART,
        nodes=(DiagramNode(id="a", label="Étape 1", role="début"),),
        links=(DiagramLink(from_id="a", to_id="a", label="oui"),),
        events=(), comparison=None, caption="Légende",
        chapter_anchor="11-le-bilan", excerpts=(_src_excerpt(),),
    )
    board = DiagramBoard(diagrams=(diagram,), language=Language.FR)
    strings = {"Processus", "Légende", "Étape 1", "début", "oui"}
    provider = _provider(strings)
    localized, cost = localize_board(
        _ctx(provider), board, target_language=Language.EN, target_units=_target_units()
    )
    result = localized.diagrams[0]
    assert result.title == "EN[Processus]"
    assert result.caption == "EN[Légende]"
    assert result.nodes[0].label == "EN[Étape 1]"
    assert result.nodes[0].role == "EN[début]"
    assert result.links[0].label == "EN[oui]"
    assert result.excerpts[0].anchor == "11-the-balance-sheet"
    assert localized.language is Language.EN
    assert cost == 0.003
