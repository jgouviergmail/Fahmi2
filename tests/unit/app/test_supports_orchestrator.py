"""Tests du SupportsOrchestrator (tranche flashcards glossaire)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from fahmi2.app.project_service import ProjectService
from fahmi2.app.supports_orchestrator import SupportsOrchestrator
from fahmi2.core.errors.exceptions import ConfigError, LLMError
from fahmi2.core.errors.severity import Severity
from fahmi2.domain.enums import Language, PhaseStatus, RunStatus, SupportType
from fahmi2.domain.glossary import Term
from fahmi2.domain.ids import ProjectId, RunId
from fahmi2.domain.run import Run
from fahmi2.domain.supports import SupportArtifact
from fahmi2.infra.llm._fakes import FakeLLMProvider
from fahmi2.infra.prompts.loader import PromptLoader
from fahmi2.infra.storage.fs_artifacts import FsArtifactStore
from fahmi2.infra.storage.sqlite_state import SqliteState
from fahmi2.pedagogy.artifact_writer import artifact_json_path, artifact_markdown_path
from fahmi2.pedagogy.chapters import Chapter
from fahmi2.pedagogy.events import (
    PedagogyEvent,
    SupportFinished,
    SupportGenerationFinished,
)
from fahmi2.pedagogy.generators.flashcards_glossary import FlashcardsGlossaryGenerator
from fahmi2.pedagogy.support_generator import SupportContext, SupportGenerator
from fahmi2.pedagogy.support_registry import SupportGeneratorRegistry
from fahmi2.pipeline.event_bus import EventBus
from fahmi2.pipeline.pause_token import PauseToken


def _seed_completed_run_with_glossary(
    state: SqliteState, project_id: ProjectId, settings: Any
) -> None:
    run = Run(
        id=RunId.new(),
        project_id=project_id,
        started_at=datetime.now(tz=UTC),
        status=RunStatus.COMPLETED,
        settings_snapshot=settings,
    )
    state.upsert_run(run)
    state.upsert_glossary_term(
        run.id, Language.FR, Term(term="PIB", definition="Produit intérieur brut")
    )


def _build(
    tmp_path: Path, registry: SupportGeneratorRegistry
) -> tuple[SupportsOrchestrator, SqliteState, ProjectService]:
    state = SqliteState(tmp_path / "t.db")
    project_service = ProjectService(state)
    orchestrator = SupportsOrchestrator(
        state=state,
        project_service=project_service,
        registry=registry,
        artifacts=FsArtifactStore(),
        llm_provider=FakeLLMProvider(),
        prompts=PromptLoader(),
    )
    return orchestrator, state, project_service


def _collect(bus: EventBus[PedagogyEvent]) -> list[PedagogyEvent]:
    events: list[PedagogyEvent] = []
    bus.subscribe(events.append)
    return events


def test_generates_flashcards_artifacts(
    tmp_path: Path, make_generation_settings: Any, make_pedagogy_settings: Any
) -> None:
    registry = SupportGeneratorRegistry([FlashcardsGlossaryGenerator()])
    orchestrator, state, project_service = _build(tmp_path, registry)
    ws = tmp_path / "ws"
    project = project_service.create_project(
        name="P",
        workspace_folder=ws,
        generation=make_generation_settings(),
        pedagogy=make_pedagogy_settings(),
    )
    _seed_completed_run_with_glossary(state, project.id, make_generation_settings())

    bus: EventBus[PedagogyEvent] = EventBus()
    events = _collect(bus)
    status = orchestrator.generate(project, pause_token=PauseToken(), event_bus=bus)

    assert status is RunStatus.COMPLETED
    pedagogy_dir = ws / "pedagogy"
    json_path = artifact_json_path(
        pedagogy_dir, SupportType.FLASHCARDS_GLOSSARY, Language.FR
    )
    md_path = artifact_markdown_path(
        pedagogy_dir, SupportType.FLASHCARDS_GLOSSARY, Language.FR
    )
    assert json_path.exists()
    assert md_path.exists()
    assert (pedagogy_dir / "manifest.json").exists()
    finished = [e for e in events if isinstance(e, SupportFinished)]
    assert finished and finished[0].status is PhaseStatus.SUCCEEDED
    assert isinstance(events[-1], SupportGenerationFinished)


def test_coarse_resume_skips_fresh(
    tmp_path: Path, make_generation_settings: Any, make_pedagogy_settings: Any
) -> None:
    registry = SupportGeneratorRegistry([FlashcardsGlossaryGenerator()])
    orchestrator, state, project_service = _build(tmp_path, registry)
    project = project_service.create_project(
        name="P",
        workspace_folder=tmp_path / "ws",
        generation=make_generation_settings(),
        pedagogy=make_pedagogy_settings(),
    )
    _seed_completed_run_with_glossary(state, project.id, make_generation_settings())

    orchestrator.generate(project, pause_token=PauseToken(), event_bus=EventBus())
    bus: EventBus[PedagogyEvent] = EventBus()
    events = _collect(bus)
    orchestrator.generate(project, pause_token=PauseToken(), event_bus=bus)

    finished = [e for e in events if isinstance(e, SupportFinished)]
    assert finished and finished[0].status is PhaseStatus.SKIPPED


def test_missing_pedagogy_raises(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    registry = SupportGeneratorRegistry([FlashcardsGlossaryGenerator()])
    orchestrator, _, project_service = _build(tmp_path, registry)
    project = project_service.create_project(
        name="P",
        workspace_folder=tmp_path / "ws",
        generation=make_generation_settings(),
    )
    with pytest.raises(ConfigError):
        orchestrator.generate(project, pause_token=PauseToken(), event_bus=EventBus())


class _FailingGen(SupportGenerator):
    @property
    def support_type(self) -> SupportType:
        return SupportType.FLASHCARDS_GLOSSARY

    @property
    def uses_llm(self) -> bool:
        return False

    def generate(
        self,
        ctx: SupportContext,
        *,
        language: Language,
        chapters: tuple[Chapter, ...],
        glossary: tuple[Term, ...],
    ) -> SupportArtifact:
        del ctx, language, chapters, glossary
        raise LLMError(code="LLM.BOOM", user_message="boom", severity=Severity.ERROR)


def test_generator_failure_yields_failed_status(
    tmp_path: Path, make_generation_settings: Any, make_pedagogy_settings: Any
) -> None:
    registry = SupportGeneratorRegistry([_FailingGen()])
    orchestrator, state, project_service = _build(tmp_path, registry)
    project = project_service.create_project(
        name="P",
        workspace_folder=tmp_path / "ws",
        generation=make_generation_settings(),
        pedagogy=make_pedagogy_settings(),
    )
    _seed_completed_run_with_glossary(state, project.id, make_generation_settings())

    bus: EventBus[PedagogyEvent] = EventBus()
    events = _collect(bus)
    status = orchestrator.generate(project, pause_token=PauseToken(), event_bus=bus)

    assert status is RunStatus.FAILED
    failed = [e for e in events if isinstance(e, SupportFinished)]
    assert failed and failed[0].status is PhaseStatus.FAILED
    assert failed[0].error is not None
    assert failed[0].error.code == "LLM.BOOM"


def test_cancellation_returns_cancelled(
    tmp_path: Path, make_generation_settings: Any, make_pedagogy_settings: Any
) -> None:
    registry = SupportGeneratorRegistry([FlashcardsGlossaryGenerator()])
    orchestrator, state, project_service = _build(tmp_path, registry)
    project = project_service.create_project(
        name="P",
        workspace_folder=tmp_path / "ws",
        generation=make_generation_settings(),
        pedagogy=make_pedagogy_settings(),
    )
    _seed_completed_run_with_glossary(state, project.id, make_generation_settings())

    token = PauseToken()
    token.request_cancel()
    bus: EventBus[PedagogyEvent] = EventBus()
    events = _collect(bus)
    status = orchestrator.generate(project, pause_token=token, event_bus=bus)

    assert status is RunStatus.CANCELLED
    assert isinstance(events[-1], SupportGenerationFinished)
    assert events[-1].status is RunStatus.CANCELLED
