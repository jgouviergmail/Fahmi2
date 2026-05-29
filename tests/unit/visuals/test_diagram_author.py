"""Tests de la génération de diagrammes (types, robustesse, cap densité)."""

from __future__ import annotations

import json
from collections.abc import Mapping

from fahmi2.core.concurrency.pause_token import PauseToken
from fahmi2.core.retry.policy import RetryPolicy
from fahmi2.domain.enums import DiagramType, Language, SupportDensity
from fahmi2.domain.visuals import VisualsSettings
from fahmi2.infra.llm._fakes import FakeLLMProvider
from fahmi2.infra.llm.interface import LLMResponse
from fahmi2.infra.prompts.loader import PromptLoader
from fahmi2.pipeline.event_bus import EventBus
from fahmi2.visuals.events import VisualsEvent
from fahmi2.visuals.extractors._base import VisualsContext
from fahmi2.visuals.extractors.diagram_author import extract_diagrams
from fahmi2.visuals.sources import TextUnit

_FLOWCHART = {
    "type": "flowchart", "title": "Processus", "caption": "c",
    "nodes": [{"id": "a", "label": "Étape 1", "role": "début"},
              {"id": "b", "label": "Étape 2", "role": None}],
    "links": [{"from": "a", "to": "b", "label": None}],
}
_TIMELINE = {
    "type": "timeline", "title": "Chronologie",
    "events": [{"date": "2001", "title": "Faillite", "detail": None}],
}
_COMPARISON = {
    "type": "comparison", "title": "Comparaison",
    "columns": ["Critère", "A", "B"], "rows": [["Liquidité", "haute", "basse"]],
}
_INVALID_GRAPH = {"type": "hierarchy", "title": "Vide", "nodes": [], "links": []}


def _response(payload: Mapping[str, object]) -> LLMResponse:
    return LLMResponse(
        content=json.dumps(payload, ensure_ascii=False),
        thinking_content=None,
        prompt_tokens=10,
        completion_tokens=10,
        cached_prompt_tokens=0,
        cost_usd=0.001,
    )


def _ctx(provider: FakeLLMProvider, *, settings: VisualsSettings) -> VisualsContext:
    return VisualsContext(
        settings=settings,
        llm_provider=provider,
        prompts=PromptLoader(),
        event_bus=EventBus[VisualsEvent](),
        pause_token=PauseToken(),
        retry_policy=RetryPolicy(
            max_attempts=3, jitter=False, initial_delay_seconds=0.001
        ),
    )


def _unit() -> TextUnit:
    return TextUnit(
        section_path=(2, 1),
        title="Le bilan",
        anchor="21-le-bilan",
        text="Contenu de la section sur le bilan et ses étapes.",
        part=0,
    )


def test_extract_diagrams_types_et_skip_invalide() -> None:
    provider = FakeLLMProvider(
        default_response=_response(
            {"diagrams": [_FLOWCHART, _TIMELINE, _COMPARISON, _INVALID_GRAPH]}
        )
    )
    ctx = _ctx(provider, settings=VisualsSettings(density=SupportDensity.DENSE))
    result = extract_diagrams(ctx, language=Language.FR, units=(_unit(),))

    by_type = {d.diagram_type: d for d in result.diagrams}
    assert set(by_type) == {
        DiagramType.FLOWCHART, DiagramType.TIMELINE, DiagramType.COMPARISON
    }  # le diagramme « hierarchy » sans nœud est ignoré
    flow = by_type[DiagramType.FLOWCHART]
    assert len(flow.nodes) == 2
    assert len(flow.links) == 1
    assert flow.excerpts and flow.excerpts[0].section_path == (2, 1)
    assert flow.chapter_anchor == "21-le-bilan"
    assert by_type[DiagramType.TIMELINE].events[0].date_label == "2001"
    comparison = by_type[DiagramType.COMPARISON].comparison
    assert comparison is not None and len(comparison.columns) == 3
    assert result.total_cost_usd == 0.001


def test_extract_diagrams_filtre_types_non_autorises() -> None:
    provider = FakeLLMProvider(
        default_response=_response({"diagrams": [_FLOWCHART, _TIMELINE]})
    )
    ctx = _ctx(
        provider,
        settings=VisualsSettings(diagram_types=frozenset({DiagramType.FLOWCHART})),
    )
    result = extract_diagrams(ctx, language=Language.FR, units=(_unit(),))
    assert [d.diagram_type for d in result.diagrams] == [DiagramType.FLOWCHART]


def test_extract_diagrams_cap_densite() -> None:
    provider = FakeLLMProvider(
        default_response=_response(
            {"diagrams": [_FLOWCHART, _TIMELINE, _COMPARISON]}
        )
    )
    ctx = _ctx(provider, settings=VisualsSettings(density=SupportDensity.LIGHT))
    result = extract_diagrams(ctx, language=Language.FR, units=(_unit(),))
    assert len(result.diagrams) == 1  # densité LIGHT → 1 diagramme/unité


def test_extract_diagrams_aucun_type_autorise() -> None:
    # diagram_types vide n'est valide que si les diagrammes sont désactivés
    # (invariant domaine) ; extract_diagrams court-circuite alors sans appel LLM.
    provider = FakeLLMProvider(default_response=_response({"diagrams": [_FLOWCHART]}))
    ctx = _ctx(
        provider,
        settings=VisualsSettings(produce_diagrams=False, diagram_types=frozenset()),
    )
    result = extract_diagrams(ctx, language=Language.FR, units=(_unit(),))
    assert result.diagrams == ()
    assert provider.calls == []
