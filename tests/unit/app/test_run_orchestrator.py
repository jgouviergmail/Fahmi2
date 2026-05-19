"""Tests de RunOrchestrator (lifecycle + delegation au moteur)."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from fahmi2.app.project_service import ProjectService
from fahmi2.app.run_orchestrator import RunOrchestrator
from fahmi2.core.errors.exceptions import ConfigError
from fahmi2.core.retrieval.interface import PassthroughRetriever
from fahmi2.core.retry.policy import RetryPolicy
from fahmi2.domain.enums import PhaseId, PhaseStatus, RunStatus
from fahmi2.domain.phase import PhaseExecution
from fahmi2.domain.run import Run
from fahmi2.domain.video import VideoExecution
from fahmi2.infra.audio.ffmpeg_extractor import FFmpegExtractor
from fahmi2.infra.llm._fakes import FakeLLMProvider
from fahmi2.infra.prompts.loader import PromptLoader
from fahmi2.infra.storage.fs_artifacts import FsArtifactStore
from fahmi2.infra.storage.sqlite_state import SqliteState
from fahmi2.infra.stt._fakes import FakeSTTProvider
from fahmi2.pipeline.engine import PipelineEngine
from fahmi2.pipeline.event_bus import EventBus
from fahmi2.pipeline.pause_token import PauseToken
from fahmi2.pipeline.phase_handler import PhaseContext, PhaseHandler
from fahmi2.pipeline.phase_registry import PhaseRegistry


class _NoOpHandler(PhaseHandler):
    """Handler factice qui réussit immédiatement, sans I/O."""

    @property
    def phase_id(self) -> PhaseId:
        return PhaseId.STT

    @property
    def is_per_video(self) -> bool:
        return True

    def execute(
        self, ctx: PhaseContext, *, video: VideoExecution | None
    ) -> PhaseExecution:
        del ctx, video
        return PhaseExecution(phase_id=PhaseId.STT, status=PhaseStatus.SUCCEEDED)


def _build_orchestrator(
    tmp_path: Path,
) -> tuple[RunOrchestrator, SqliteState, ProjectService]:
    state = SqliteState(tmp_path / "t.db")
    registry = PhaseRegistry([_NoOpHandler()])
    engine = PipelineEngine(
        registry=registry,
        retry_policy=RetryPolicy(jitter=False, initial_delay_seconds=0.001),
    )
    project_service = ProjectService(state)
    orchestrator = RunOrchestrator(
        state=state, engine=engine, project_service=project_service
    )
    return orchestrator, state, project_service


def _build_ctx(tmp_path: Path, run: Run) -> PhaseContext:
    return PhaseContext(
        run=run,
        settings=run.settings_snapshot,
        workspace=tmp_path / "workspace",
        output_dir=tmp_path / "output",
        state=SqliteState(tmp_path / "t.db"),
        artifacts=FsArtifactStore(),
        stt_provider=FakeSTTProvider(),
        llm_provider=FakeLLMProvider(),
        ffmpeg=FFmpegExtractor(),
        retriever=PassthroughRetriever(),
        prompts=PromptLoader(),
        pause_token=PauseToken(),
        event_bus=EventBus(),
    )


def _seed_input_folder(tmp_path: Path) -> Path:
    folder = tmp_path / "input"
    folder.mkdir()
    (folder / "lesson_01.mp4").write_bytes(b"x")
    (folder / "lesson_02.mp4").write_bytes(b"x")
    return folder


def test_create_run_scans_videos(tmp_path: Path, make_settings: Any) -> None:
    orchestrator, _, project_service = _build_orchestrator(tmp_path)
    input_folder = _seed_input_folder(tmp_path)
    settings = make_settings(input_folder=input_folder)
    project = project_service.create_project(settings)
    run = orchestrator.create_run(project)
    assert len(run.videos) == 2
    assert run.status is RunStatus.CREATED


def test_create_run_raises_when_no_videos(
    tmp_path: Path, make_settings: Any
) -> None:
    orchestrator, _, project_service = _build_orchestrator(tmp_path)
    empty_folder = tmp_path / "empty"
    empty_folder.mkdir()
    settings = make_settings(input_folder=empty_folder)
    project = project_service.create_project(settings)
    with pytest.raises(ConfigError):
        orchestrator.create_run(project)


def test_execute_completes_run_successfully(
    tmp_path: Path, make_settings: Any
) -> None:
    orchestrator, _, project_service = _build_orchestrator(tmp_path)
    input_folder = _seed_input_folder(tmp_path)
    settings = make_settings(input_folder=input_folder)
    project = project_service.create_project(settings)
    run = orchestrator.create_run(project)

    final = orchestrator.execute(run=run, ctx=_build_ctx(tmp_path, run))
    assert final is RunStatus.COMPLETED

    loaded_run = orchestrator.get_run(run.id)
    assert loaded_run is not None
    assert loaded_run.status is RunStatus.COMPLETED
    assert loaded_run.finished_at is not None


def test_request_pause_and_resume(tmp_path: Path) -> None:
    orchestrator, _, _ = _build_orchestrator(tmp_path)
    token = PauseToken()
    orchestrator.request_pause(token)
    assert token.is_paused()
    orchestrator.resume(token)
    assert not token.is_paused()


def test_request_cancel_sets_cancelled(tmp_path: Path) -> None:
    orchestrator, _, _ = _build_orchestrator(tmp_path)
    token = PauseToken()
    orchestrator.request_cancel(token)
    assert token.is_cancelled()


def test_execute_updates_project_last_run_at(
    tmp_path: Path, make_settings: Any
) -> None:
    orchestrator, _, project_service = _build_orchestrator(tmp_path)
    input_folder = _seed_input_folder(tmp_path)
    project = project_service.create_project(make_settings(input_folder=input_folder))
    before = datetime.now(tz=UTC)
    run = orchestrator.create_run(project)
    orchestrator.execute(run=run, ctx=_build_ctx(tmp_path, run))
    reloaded = project_service.get_project(project.id)
    assert reloaded is not None
    assert reloaded.last_run_at is not None
    assert reloaded.last_run_at >= before
