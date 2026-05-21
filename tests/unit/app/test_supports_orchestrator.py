"""Tests du SupportsOrchestrator (génération des supports pédagogiques)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from fahmi2.app.project_service import ProjectService
from fahmi2.app.supports_orchestrator import SupportsOrchestrator
from fahmi2.core.errors.exceptions import ConfigError, LLMError
from fahmi2.core.errors.severity import Severity
from fahmi2.core.retry.policy import RetryPolicy
from fahmi2.domain.enums import Language, PhaseStatus, RunStatus, SupportType
from fahmi2.domain.generation import (
    GENERATION_OUTPUT_SUBDIR,
    GENERATION_WORKSPACE_SUBDIR,
    consolidated_doc_filename,
)
from fahmi2.domain.glossary import Term
from fahmi2.domain.ids import RunId
from fahmi2.domain.project import Project
from fahmi2.domain.run import Run
from fahmi2.domain.supports import SupportArtifact
from fahmi2.infra.llm._fakes import FakeLLMProvider
from fahmi2.infra.llm.interface import LLMResponse
from fahmi2.infra.prompts.loader import PromptLoader
from fahmi2.infra.storage.fs_artifacts import FsArtifactStore
from fahmi2.infra.storage.sqlite_state import SqliteState
from fahmi2.pedagogy.artifact_writer import (
    artifact_correction_markdown_path,
    artifact_json_path,
    artifact_markdown_path,
)
from fahmi2.pedagogy.chapters import Chapter
from fahmi2.pedagogy.events import (
    PedagogyEvent,
    SupportFinished,
    SupportGenerationFinished,
)
from fahmi2.pedagogy.generators.qcm import QcmGenerator
from fahmi2.pedagogy.support_generator import SupportContext, SupportGenerator
from fahmi2.pedagogy.support_registry import SupportGeneratorRegistry
from fahmi2.pipeline.event_bus import EventBus
from fahmi2.pipeline.pause_token import PauseToken


def _seed_completed_run_with_glossary(
    state: SqliteState, project: Project, settings: Any
) -> None:
    state.upsert_run(
        Run(
            id=RunId.new(),
            project_id=project.id,
            started_at=datetime.now(tz=UTC),
            status=RunStatus.COMPLETED,
            settings_snapshot=settings,
        )
    )
    FsArtifactStore().write_json_atomic(
        project.workspace_folder / GENERATION_WORKSPACE_SUBDIR / "glossary_master.json",
        {"terms": [{"term": "PIB", "definition": "Produit intérieur brut"}]},
    )


def _build(
    tmp_path: Path,
    registry: SupportGeneratorRegistry,
    *,
    llm_provider: Any | None = None,
) -> tuple[SupportsOrchestrator, SqliteState, ProjectService]:
    state = SqliteState(tmp_path / "t.db")
    project_service = ProjectService(state)
    orchestrator = SupportsOrchestrator(
        registry=registry,
        artifacts=FsArtifactStore(),
        llm_provider=llm_provider if llm_provider is not None else FakeLLMProvider(),
        prompts=PromptLoader(),
        retry_policy=RetryPolicy(
            max_attempts=2, jitter=False, initial_delay_seconds=0.001
        ),
    )
    return orchestrator, state, project_service


def _collect(bus: EventBus[PedagogyEvent]) -> list[PedagogyEvent]:
    events: list[PedagogyEvent] = []
    bus.subscribe(events.append)
    return events


def test_generates_flashcards_artifacts(
    tmp_path: Path, make_generation_settings: Any, make_pedagogy_settings: Any
) -> None:
    registry = SupportGeneratorRegistry([_StubGen(SupportType.FLASHCARDS_CONCEPTS)])
    orchestrator, state, project_service = _build(tmp_path, registry)
    ws = tmp_path / "ws"
    project = project_service.create_project(
        name="P",
        workspace_folder=ws,
        generation=make_generation_settings(),
        pedagogy=make_pedagogy_settings(),
    )
    _seed_completed_run_with_glossary(state, project, make_generation_settings())

    bus: EventBus[PedagogyEvent] = EventBus()
    events = _collect(bus)
    status = orchestrator.generate(project, pause_token=PauseToken(), event_bus=bus)

    assert status is RunStatus.COMPLETED
    pedagogy_dir = ws / "pedagogy"
    json_path = artifact_json_path(
        pedagogy_dir, SupportType.FLASHCARDS_CONCEPTS, Language.FR
    )
    md_path = artifact_markdown_path(
        pedagogy_dir, SupportType.FLASHCARDS_CONCEPTS, Language.FR
    )
    assert json_path.exists()
    assert md_path.exists()
    assert (pedagogy_dir / "manifest.json").exists()
    finished = [e for e in events if isinstance(e, SupportFinished)]
    assert finished and finished[0].status is PhaseStatus.SUCCEEDED
    assert isinstance(events[-1], SupportGenerationFinished)


def test_complete_set_is_regenerated(
    tmp_path: Path, make_generation_settings: Any, make_pedagogy_settings: Any
) -> None:
    # Ensemble complet (tout présent + frais) : relancer régénère (comme un nouveau
    # run en génération), au lieu de skipper.
    registry = SupportGeneratorRegistry([_StubGen(SupportType.FLASHCARDS_CONCEPTS)])
    orchestrator, state, project_service = _build(tmp_path, registry)
    project = project_service.create_project(
        name="P",
        workspace_folder=tmp_path / "ws",
        generation=make_generation_settings(),
        pedagogy=make_pedagogy_settings(languages=(Language.FR,)),
    )
    _seed_completed_run_with_glossary(state, project, make_generation_settings())

    orchestrator.generate(project, pause_token=PauseToken(), event_bus=EventBus())
    bus: EventBus[PedagogyEvent] = EventBus()
    events = _collect(bus)
    orchestrator.generate(project, pause_token=PauseToken(), event_bus=bus)

    finished = [e for e in events if isinstance(e, SupportFinished)]
    assert finished and finished[0].status is PhaseStatus.SUCCEEDED


def test_incomplete_set_resumes_skipping_fresh(
    tmp_path: Path, make_generation_settings: Any, make_pedagogy_settings: Any
) -> None:
    # Ensemble incomplet (un support manque, ex. plafond atteint) : reprise — le
    # support frais déjà présent est skippé, le manquant est généré.
    registry = SupportGeneratorRegistry(
        [
            _CostlyGen(SupportType.FLASHCARDS_CONCEPTS, cost_usd=10.0),
            _StubGen(SupportType.QCM),
        ]
    )
    orchestrator, state, project_service = _build(tmp_path, registry)
    project = project_service.create_project(
        name="P",
        workspace_folder=tmp_path / "ws",
        generation=make_generation_settings(),
        pedagogy=make_pedagogy_settings(
            selected_supports=frozenset(
                {SupportType.FLASHCARDS_CONCEPTS, SupportType.QCM}
            ),
            separate_correction=frozenset(),
            languages=(Language.FR,),
            cost_ceiling_usd=1.0,
            llm_workers=1,  # plafond déterministe (séquentiel strict)
        ),
    )
    _seed_completed_run_with_glossary(state, project, make_generation_settings())

    # 1re génération : flashcards (coûteux) passe, plafond atteint avant le QCM.
    status1 = orchestrator.generate(
        project, pause_token=PauseToken(), event_bus=EventBus()
    )
    assert status1 is RunStatus.PAUSED

    # 2e génération : ensemble incomplet -> reprise (flashcards frais skippé, QCM généré).
    bus: EventBus[PedagogyEvent] = EventBus()
    events = _collect(bus)
    orchestrator.generate(project, pause_token=PauseToken(), event_bus=bus)
    by_support = {
        e.support_type: e.status
        for e in events
        if isinstance(e, SupportFinished)
    }
    assert by_support[SupportType.FLASHCARDS_CONCEPTS] is PhaseStatus.SKIPPED
    assert by_support[SupportType.QCM] is PhaseStatus.SUCCEEDED


def test_missing_pedagogy_raises(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    registry = SupportGeneratorRegistry([_StubGen(SupportType.FLASHCARDS_CONCEPTS)])
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
        return SupportType.FLASHCARDS_CONCEPTS

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


class _StubGen(SupportGenerator):
    """Générateur déterministe sans LLM (artefact trivial) pour les tests."""

    def __init__(self, support_type: SupportType) -> None:
        self._support_type = support_type

    @property
    def support_type(self) -> SupportType:
        return self._support_type

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
        del ctx, chapters, glossary
        return SupportArtifact(
            support_type=self._support_type,
            language=language,
            items=(),
            rendered_markdown="# Stub\n",
            cost_usd=0.0,
        )


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
    _seed_completed_run_with_glossary(state, project, make_generation_settings())

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
    registry = SupportGeneratorRegistry([_StubGen(SupportType.FLASHCARDS_CONCEPTS)])
    orchestrator, state, project_service = _build(tmp_path, registry)
    project = project_service.create_project(
        name="P",
        workspace_folder=tmp_path / "ws",
        generation=make_generation_settings(),
        pedagogy=make_pedagogy_settings(),
    )
    _seed_completed_run_with_glossary(state, project, make_generation_settings())

    token = PauseToken()
    token.request_cancel()
    bus: EventBus[PedagogyEvent] = EventBus()
    events = _collect(bus)
    status = orchestrator.generate(project, pause_token=token, event_bus=bus)

    assert status is RunStatus.CANCELLED
    assert isinstance(events[-1], SupportGenerationFinished)
    assert events[-1].status is RunStatus.CANCELLED


_QCM_JSON = (
    '{"questions": [{"question": "Q?", "choices": ["a", "b", "c", "d"], '
    '"correct_index": 1, "justification": "car b"}]}'
)


def test_llm_support_writes_subject_and_correction(
    tmp_path: Path, make_generation_settings: Any, make_pedagogy_settings: Any
) -> None:
    """Bout-en-bout : un support évaluatif à corrigé séparé écrit 3 fichiers."""
    provider = FakeLLMProvider(
        default_response=LLMResponse(
            content=_QCM_JSON,
            thinking_content=None,
            prompt_tokens=1,
            completion_tokens=1,
            cached_prompt_tokens=0,
            cost_usd=0.0,
        )
    )
    registry = SupportGeneratorRegistry([QcmGenerator()])
    orchestrator, state, project_service = _build(
        tmp_path, registry, llm_provider=provider
    )
    ws = tmp_path / "ws"
    project = project_service.create_project(
        name="P",
        workspace_folder=ws,
        generation=make_generation_settings(),
        pedagogy=make_pedagogy_settings(
            selected_supports=frozenset({SupportType.QCM}),
            separate_correction=frozenset({SupportType.QCM}),
        ),
    )
    _seed_completed_run_with_glossary(state, project, make_generation_settings())
    # Document consolidé source (un chapitre) pour la langue FR.
    doc = (
        ws
        / GENERATION_WORKSPACE_SUBDIR
        / GENERATION_OUTPUT_SUBDIR
        / consolidated_doc_filename(Language.FR)
    )
    FsArtifactStore().write_text_atomic(
        doc, "# Cours\n\n# 1. Bases\n\nContenu du chapitre.\n"
    )

    status = orchestrator.generate(
        project, pause_token=PauseToken(), event_bus=EventBus()
    )

    assert status is RunStatus.COMPLETED
    pedagogy_dir = ws / "pedagogy"
    assert artifact_json_path(pedagogy_dir, SupportType.QCM, Language.FR).exists()
    assert artifact_markdown_path(pedagogy_dir, SupportType.QCM, Language.FR).exists()
    assert artifact_correction_markdown_path(
        pedagogy_dir, SupportType.QCM, Language.FR
    ).exists()


class _CostlyGen(SupportGenerator):
    """Générateur factice (sans LLM) renvoyant un coût fixe élevé."""

    def __init__(self, support_type: SupportType, *, cost_usd: float) -> None:
        self._support_type = support_type
        self._cost_usd = cost_usd

    @property
    def support_type(self) -> SupportType:
        return self._support_type

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
        del ctx, chapters, glossary
        return SupportArtifact(
            support_type=self._support_type,
            language=language,
            items=(),
            rendered_markdown="x",
            cost_usd=self._cost_usd,
        )


class _CapturingGen(SupportGenerator):
    """Générateur de test (sans LLM) capturant la langue cible + chapitres reçus."""

    def __init__(self, support_type: SupportType) -> None:
        self._support_type = support_type
        self.seen_language: Language | None = None
        self.seen_chapters: tuple[Chapter, ...] = ()

    @property
    def support_type(self) -> SupportType:
        return self._support_type

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
        del ctx, glossary
        self.seen_language = language
        self.seen_chapters = chapters
        return SupportArtifact(
            support_type=self._support_type,
            language=language,
            items=(),
            rendered_markdown="# Stub\n",
            cost_usd=0.0,
        )


def test_target_language_without_doc_uses_fallback_content(
    tmp_path: Path, make_generation_settings: Any, make_pedagogy_settings: Any
) -> None:
    gen = _CapturingGen(SupportType.FLASHCARDS_CONCEPTS)
    registry = SupportGeneratorRegistry([gen])
    orchestrator, _, project_service = _build(tmp_path, registry)
    ws = tmp_path / "ws"
    project = project_service.create_project(
        name="P",
        workspace_folder=ws,
        generation=make_generation_settings(source_language=Language.FR),
        pedagogy=make_pedagogy_settings(
            selected_supports=frozenset({SupportType.FLASHCARDS_CONCEPTS}),
            languages=(Language.EN,),
        ),
    )
    # Seul le doc FR (source) existe ; la cible EN l'utilise comme contenu.
    FsArtifactStore().write_text_atomic(
        ws
        / GENERATION_WORKSPACE_SUBDIR
        / GENERATION_OUTPUT_SUBDIR
        / consolidated_doc_filename(Language.FR),
        "# Cours\n\n# 1. Bases\n\nContenu.\n",
    )
    status = orchestrator.generate(
        project, pause_token=PauseToken(), event_bus=EventBus()
    )
    assert status is RunStatus.COMPLETED
    # Le générateur reçoit la langue cible EN, mais le contenu (chapitres) provient
    # du doc FR de repli (seul présent) : découplage contenu/cible vérifié.
    assert gen.seen_language is Language.EN
    assert gen.seen_chapters
    # Artefact écrit sous la langue cible EN.
    assert artifact_json_path(
        ws / "pedagogy", SupportType.FLASHCARDS_CONCEPTS, Language.EN
    ).exists()


def test_cost_ceiling_stops_generation(
    tmp_path: Path, make_generation_settings: Any, make_pedagogy_settings: Any
) -> None:
    registry = SupportGeneratorRegistry(
        [
            _CostlyGen(SupportType.FLASHCARDS_CONCEPTS, cost_usd=10.0),
            _CostlyGen(SupportType.QCM, cost_usd=10.0),
        ]
    )
    orchestrator, state, project_service = _build(tmp_path, registry)
    project = project_service.create_project(
        name="P",
        workspace_folder=tmp_path / "ws",
        generation=make_generation_settings(),
        pedagogy=make_pedagogy_settings(
            selected_supports=frozenset(
                {SupportType.FLASHCARDS_CONCEPTS, SupportType.QCM}
            ),
            separate_correction=frozenset(),
            cost_ceiling_usd=1.0,
            llm_workers=1,  # plafond déterministe (séquentiel strict)
        ),
    )
    _seed_completed_run_with_glossary(state, project, make_generation_settings())

    bus: EventBus[PedagogyEvent] = EventBus()
    events = _collect(bus)
    status = orchestrator.generate(project, pause_token=PauseToken(), event_bus=bus)

    assert status is RunStatus.PAUSED
    succeeded = [
        e
        for e in events
        if isinstance(e, SupportFinished) and e.status is PhaseStatus.SUCCEEDED
    ]
    # Le 1er support (flashcards concepts, ordre canonique) est généré ; le plafond
    # stoppe avant le 2e (QCM).
    assert len(succeeded) == 1
    assert succeeded[0].support_type is SupportType.FLASHCARDS_CONCEPTS
    assert isinstance(events[-1], SupportGenerationFinished)
    assert events[-1].status is RunStatus.PAUSED


def test_parallel_generation_two_languages(
    tmp_path: Path, make_generation_settings: Any, make_pedagogy_settings: Any
) -> None:
    registry = SupportGeneratorRegistry([_StubGen(SupportType.FLASHCARDS_CONCEPTS)])
    orchestrator, state, project_service = _build(tmp_path, registry)
    ws = tmp_path / "ws"
    project = project_service.create_project(
        name="P",
        workspace_folder=ws,
        generation=make_generation_settings(
            output_languages=(Language.FR, Language.EN)
        ),
        pedagogy=make_pedagogy_settings(
            languages=(Language.FR, Language.EN), llm_workers=4
        ),
    )
    _seed_completed_run_with_glossary(
        state,
        project,
        make_generation_settings(output_languages=(Language.FR, Language.EN)),
    )
    for lang in (Language.FR, Language.EN):
        FsArtifactStore().write_text_atomic(
            ws
            / GENERATION_WORKSPACE_SUBDIR
            / GENERATION_OUTPUT_SUBDIR
            / consolidated_doc_filename(lang),
            "# Titre\n\n## 1. Chapitre\n\nContenu.\n",
        )

    bus: EventBus[PedagogyEvent] = EventBus()
    status = orchestrator.generate(project, pause_token=PauseToken(), event_bus=bus)

    assert status is RunStatus.COMPLETED
    pedagogy_dir = ws / "pedagogy"
    for lang in (Language.FR, Language.EN):
        assert artifact_json_path(
            pedagogy_dir, SupportType.FLASHCARDS_CONCEPTS, lang
        ).exists()
