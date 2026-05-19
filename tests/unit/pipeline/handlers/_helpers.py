"""Helpers communs aux tests de handlers (Phase 1+)."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fahmi2.core.retrieval.interface import PassthroughRetriever
from fahmi2.domain.enums import RunStatus
from fahmi2.domain.ids import ProjectId, RunId
from fahmi2.domain.project import Project
from fahmi2.domain.run import Run
from fahmi2.infra.audio.ffmpeg_extractor import FFmpegExtractor
from fahmi2.infra.llm._fakes import FakeLLMProvider
from fahmi2.infra.llm.interface import LLMResponse
from fahmi2.infra.prompts.loader import PromptLoader
from fahmi2.infra.storage.fs_artifacts import FsArtifactStore
from fahmi2.infra.storage.sqlite_state import SqliteState
from fahmi2.infra.stt._fakes import FakeSTTProvider
from fahmi2.pipeline.event_bus import EventBus
from fahmi2.pipeline.pause_token import PauseToken
from fahmi2.pipeline.phase_handler import PhaseContext


def write_transcription_fixture(
    workspace: Path, video_id: str, *, text: str = "contenu de test"
) -> Path:
    """Écrit un fichier transcription JSON minimal pour les tests.

    Args:
        workspace: Dossier de travail.
        video_id: ULID de la vidéo.
        text: Texte du segment.

    Returns:
        Chemin du fichier écrit.
    """
    path = workspace / "transcripts" / f"{video_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "detected_language": "fr",
        "duration_seconds": 5.0,
        "segments": [{"start_seconds": 0.0, "end_seconds": 5.0, "text": text}],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def build_phase_context(
    tmp_path: Path,
    make_settings: Any,
    *,
    llm_response: LLMResponse | None = None,
    videos: tuple[Any, ...] = (),
    settings_overrides: dict[str, Any] | None = None,
) -> tuple[PhaseContext, Run]:
    """Construit un ``PhaseContext`` prêt à l'usage pour les tests handlers.

    Args:
        tmp_path: Dossier temporaire de test.
        make_settings: Factory de ``ProjectSettings``.
        llm_response: Réponse fixe à retourner pour tous les appels LLM.
        videos: Tuple de ``VideoExecution`` à attacher au Run.
        settings_overrides: Overrides additionnels pour ``ProjectSettings``.

    Returns:
        Tuple ``(ctx, run)`` avec le projet/run déjà persistés.
    """
    overrides = {
        "workspace_folder": tmp_path / "workspace",
        **(settings_overrides or {}),
    }
    settings = make_settings(**overrides)
    state = SqliteState(tmp_path / "state.db")
    project = Project(
        id=ProjectId.new(),
        settings=settings,
        created_at=datetime.now(tz=UTC),
    )
    state.upsert_project(project)
    run = Run(
        id=RunId.new(),
        project_id=project.id,
        started_at=datetime.now(tz=UTC),
        status=RunStatus.RUNNING,
        settings_snapshot=settings,
        videos=videos,
    )
    state.upsert_run(run)
    fake_llm = FakeLLMProvider(
        default_response=llm_response or _default_llm_response(),
    )
    ctx = PhaseContext(
        run=run,
        settings=settings,
        workspace=tmp_path / "workspace",
        output_dir=tmp_path / "output",
        state=state,
        artifacts=FsArtifactStore(),
        stt_provider=FakeSTTProvider(),
        llm_provider=fake_llm,
        ffmpeg=FFmpegExtractor(),
        retriever=PassthroughRetriever(),
        prompts=PromptLoader(),
        pause_token=PauseToken(),
        event_bus=EventBus(),
    )
    return ctx, run


def _default_llm_response() -> LLMResponse:
    return LLMResponse(
        content="{}",
        thinking_content=None,
        prompt_tokens=10,
        completion_tokens=5,
        cached_prompt_tokens=0,
        cost_usd=0.001,
    )
