"""Tests de l'extraction du graphe brut (squelette glossaire + couche LLM + gleaning)."""

from __future__ import annotations

import json
from collections.abc import Mapping

from fahmi2.core.concurrency.pause_token import PauseToken
from fahmi2.core.retry.policy import RetryPolicy
from fahmi2.domain.enums import EdgeType, Language, NodeType, SupportDensity
from fahmi2.domain.glossary import Term, parse_glossary_master_terms
from fahmi2.domain.visuals import VisualsSettings
from fahmi2.infra.llm._fakes import FakeLLMProvider
from fahmi2.infra.llm.interface import JSON_OBJECT_RESPONSE_FORMAT, LLMResponse
from fahmi2.infra.prompts.loader import PromptLoader
from fahmi2.pipeline.event_bus import EventBus
from fahmi2.visuals.events import VisualsEvent
from fahmi2.visuals.extractors._base import VisualsContext
from fahmi2.visuals.extractors.graph_extractor import (
    build_glossary_skeleton,
    extract_graph,
    node_id,
)
from fahmi2.visuals.sources import TextUnit

_COST = 0.001


def _response(payload: Mapping[str, object]) -> LLMResponse:
    return LLMResponse(
        content=json.dumps(payload, ensure_ascii=False),
        thinking_content=None,
        prompt_tokens=10,
        completion_tokens=10,
        cached_prompt_tokens=0,
        cost_usd=_COST,
    )


def _ctx(provider: FakeLLMProvider, *, density: SupportDensity) -> VisualsContext:
    return VisualsContext(
        settings=VisualsSettings(density=density),
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
                {"term": "Actif", "definition": "Biens.", "aliases": ["emplois"],
                 "sources": []},
                {"term": "Actif", "definition": "Doublon.", "aliases": [],
                 "sources": []},
            ]
        }
    )


def _unit() -> TextUnit:
    return TextUnit(
        section_path=(2, 1),
        title="Le bilan",
        anchor="21-le-bilan",
        text="Le bilan oppose actif et passif. Le cas Enron illustre la fraude.",
        part=0,
    )


def test_build_glossary_skeleton_dedup_et_id() -> None:
    nodes = build_glossary_skeleton(_glossary())
    assert len(nodes) == 1  # doublon « Actif » fusionné par id
    assert nodes[0].id == node_id(NodeType.GLOSSARY_TERM, "Actif")
    assert nodes[0].id == "glossary_term:actif"
    assert nodes[0].node_type is NodeType.GLOSSARY_TERM
    assert nodes[0].definition == "Biens."


def test_extract_graph_squelette_entites_relations_et_cout() -> None:
    payload = {
        "entities": [
            {"label": "Bilan", "type": "concept", "definition": "Photo patrimoine."},
            {"label": "Cas Enron", "type": "example"},
            {"label": "Ignoré", "type": "inconnu"},
        ],
        "relations": [
            {"source": "Cas Enron", "target": "Bilan", "type": "illustrates"},
            {"source": "x", "target": "y", "type": "type_inconnu"},
        ],
    }
    provider = FakeLLMProvider(default_response=_response(payload))
    ctx = _ctx(provider, density=SupportDensity.STANDARD)

    result = extract_graph(
        ctx, language=Language.FR, units=(_unit(),), glossary=_glossary()
    )

    assert len(result.glossary_nodes) == 1
    assert {e.label for e in result.raw_entities} == {"Bilan", "Cas Enron"}
    bilan = next(e for e in result.raw_entities if e.label == "Bilan")
    assert bilan.node_type is NodeType.CONCEPT
    assert bilan.definition == "Photo patrimoine."
    assert bilan.section_path == (2, 1)
    assert bilan.anchor == "21-le-bilan"
    enron = next(e for e in result.raw_entities if e.label == "Cas Enron")
    assert enron.node_type is NodeType.EXAMPLE
    assert enron.definition is None
    # relations : type inconnu écarté, relation valide conservée.
    valid = [r for r in result.raw_relations if r.edge_type is EdgeType.ILLUSTRATES]
    assert valid and valid[0].source_label == "Cas Enron"
    # 1 unité × (initial + 1 gleaning) = 2 appels.
    assert len(provider.calls) == 2
    assert result.total_cost_usd == _COST * 2
    assert provider.calls[0]["response_format"] == JSON_OBJECT_RESPONSE_FORMAT


def test_extract_graph_gleaning_saute_si_cap_atteint() -> None:
    payload = {
        "entities": [
            {"label": f"E{i}", "type": "concept"} for i in range(6)
        ],
        "relations": [],
    }
    provider = FakeLLMProvider(default_response=_response(payload))
    ctx = _ctx(provider, density=SupportDensity.LIGHT)  # cap = 4

    result = extract_graph(
        ctx, language=Language.FR, units=(_unit(),), glossary=()
    )

    assert len(result.raw_entities) == 4  # plafonné à la densité LIGHT
    assert len(provider.calls) == 1  # cap atteint à l'initial → gleaning sauté
