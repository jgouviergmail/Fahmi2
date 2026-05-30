"""Tests d'intégration de ``VisualsOrchestrator`` (pipeline complet sur disque)."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from fahmi2.app.visuals_orchestrator import VisualsOrchestrator
from fahmi2.core.concurrency.pause_token import PauseToken
from fahmi2.core.errors.exceptions import ConfigError
from fahmi2.core.retry.policy import RetryPolicy
from fahmi2.domain.enums import RunStatus
from fahmi2.domain.visuals import VisualsSettings
from fahmi2.infra.embeddings._fakes import FakeEmbeddingProvider
from fahmi2.infra.llm.interface import LLMResponse, LLMStreamChunk, Message
from fahmi2.infra.prompts.loader import PromptLoader
from fahmi2.infra.storage.feature_run_state import read_run_state
from fahmi2.infra.storage.fs_artifacts import FsArtifactStore
from fahmi2.pipeline.event_bus import EventBus
from fahmi2.visuals.events import (
    VisualsEvent,
    VisualsGenerationFinished,
    VisualsLanguageFinished,
)
from fahmi2.visuals.manifest import read_manifest

_CONSOLIDATED = """# Analyse financière

## Résumé

Document de référence sur l'analyse financière et ses outils fondamentaux.

# 1. Les documents comptables

## 1.1 Le bilan

Le bilan photographie le patrimoine de l'entreprise à une date donnée et oppose
l'actif au passif ; sa lecture est essentielle au diagnostic financier.

# 2. La fiabilité de l'information

## 2.1 La fraude comptable

Le cas Enron illustre les conséquences dramatiques d'une fraude comptable massive
sur la confiance des marchés et la pérennité de l'entreprise.
"""

_GLOSSARY = {"terms": [{"term": "Bilan", "definition": "Photo du patrimoine.",
                        "aliases": [], "sources": []}]}


class _StageLLM:
    """Provider factice **conscient de l'étape** (détection par mots-clés du prompt)."""

    def __init__(self) -> None:
        self.calls = 0

    def chat(self, *, messages: list[Message], **_kw: Any) -> LLMResponse:
        self.calls += 1
        prompt = messages[-1].content
        if "carte de connaissances" in prompt:
            content: dict[str, Any] = {
                "entities": [
                    {"label": "Bilan", "type": "concept", "definition": "Patrimoine."},
                    {"label": "Cas Enron", "type": "example"},
                ],
                "relations": [
                    {"source": "Cas Enron", "target": "Bilan", "type": "illustrates"}
                ],
            }
        elif "regroupement thématique" in prompt:
            content = {"label": "Comptabilité", "report": "Synthèse du thème."}
        elif "grands thèmes" in prompt:
            content = {"relations": []}
        elif "schémas pédagogiques" in prompt:
            content = {
                "diagrams": [
                    {"type": "flowchart", "title": "Processus",
                     "nodes": [{"id": "a", "label": "Lire"}, {"id": "b", "label": "Diagnostiquer"}],
                     "links": [{"from": "a", "to": "b"}]}
                ]
            }
        else:
            content = {}
        return LLMResponse(
            content=json.dumps(content, ensure_ascii=False), thinking_content=None,
            prompt_tokens=10, completion_tokens=10, cached_prompt_tokens=0, cost_usd=0.001,
        )

    def chat_stream(self, **_kw: Any) -> Iterator[LLMStreamChunk]:
        raise NotImplementedError

    def estimate_cost(self, **_kw: Any) -> float:
        return 0.0


def _setup_generation(workspace: Path) -> None:
    output = workspace / "generation" / "output"
    output.mkdir(parents=True, exist_ok=True)
    (output / "consolidated.fr.md").write_text(_CONSOLIDATED, encoding="utf-8")
    (workspace / "generation" / "glossary_master.json").write_text(
        json.dumps(_GLOSSARY), encoding="utf-8"
    )


def _orchestrator(provider: _StageLLM) -> VisualsOrchestrator:
    return VisualsOrchestrator(
        artifacts=FsArtifactStore(),
        llm_provider=provider,
        prompts=PromptLoader(),
        retry_policy=RetryPolicy(max_attempts=2, jitter=False, initial_delay_seconds=0.001),
        embedding_provider=FakeEmbeddingProvider(),
    )


def _run(orchestrator: VisualsOrchestrator, project: Any) -> tuple[RunStatus, list[VisualsEvent]]:
    bus: EventBus[VisualsEvent] = EventBus()
    events: list[VisualsEvent] = []
    bus.subscribe(events.append)
    status = orchestrator.generate(project, pause_token=PauseToken(), event_bus=bus)
    return status, events


def test_genere_les_deux_html_et_etat(make_project: Any, tmp_path: Path) -> None:
    _setup_generation(tmp_path)
    project = make_project(
        workspace_folder=tmp_path, generation=None, visuals=VisualsSettings()
    )
    provider = _StageLLM()
    status, events = _run(_orchestrator(provider), project)

    assert status is RunStatus.COMPLETED
    out = tmp_path / "visuals" / "output"
    assert (out / "knowledge_map.fr.html").exists()
    assert (out / "diagrams.fr.html").exists()
    # contenu attendu dans les livrables.
    km = (out / "knowledge_map.fr.html").read_text(encoding="utf-8")
    assert "Bilan" in km and "Cas Enron" in km
    diagrams = (out / "diagrams.fr.html").read_text(encoding="utf-8")
    assert "Processus" in diagrams
    # état persisté + événement de fin.
    state = read_run_state(tmp_path / "visuals")
    assert state is not None and state.status is RunStatus.COMPLETED
    assert any(
        isinstance(e, VisualsGenerationFinished) and e.status is RunStatus.COMPLETED
        for e in events
    )
    # Invariant de ventilation : le coût total d'une langue = carte + diagrammes.
    finished = [e for e in events if isinstance(e, VisualsLanguageFinished)]
    assert finished
    for finished_event in finished:
        assert finished_event.cost_usd == (
            finished_event.map_cost_usd + finished_event.diagrams_cost_usd
        )
    # Les coûts par livrable sont persistés dans le manifeste (vue persistée).
    manifest = read_manifest(tmp_path / "visuals")
    structure_costs = manifest.structure_costs()
    assert structure_costs is not None
    struct_map, struct_diagrams = structure_costs
    assert struct_map > 0
    assert struct_diagrams > 0
    assert manifest.language_costs()


def test_non_configure_leve_config_error(make_project: Any, tmp_path: Path) -> None:
    project = make_project(workspace_folder=tmp_path, generation=None, visuals=None)
    with pytest.raises(ConfigError):
        _run(_orchestrator(_StageLLM()), project)


def test_aucune_langue_source_completed(make_project: Any, tmp_path: Path) -> None:
    # Pas de consolidated.{lang}.md → aucune langue exploitable → COMPLETED, rien produit.
    project = make_project(
        workspace_folder=tmp_path, generation=None, visuals=VisualsSettings()
    )
    status, _ = _run(_orchestrator(_StageLLM()), project)
    assert status is RunStatus.COMPLETED
    assert not (tmp_path / "visuals" / "output").exists()


def test_seulement_carte_si_diagrammes_desactives(
    make_project: Any, tmp_path: Path
) -> None:
    _setup_generation(tmp_path)
    project = make_project(
        workspace_folder=tmp_path, generation=None,
        visuals=VisualsSettings(produce_diagrams=False),
    )
    status, _ = _run(_orchestrator(_StageLLM()), project)
    assert status is RunStatus.COMPLETED
    out = tmp_path / "visuals" / "output"
    assert (out / "knowledge_map.fr.html").exists()
    assert not (out / "diagrams.fr.html").exists()
