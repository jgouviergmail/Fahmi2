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
from fahmi2.domain.project import Project
from fahmi2.domain.run import Run
from fahmi2.domain.source import SourceExecution
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
        self, ctx: PhaseContext, *, source: SourceExecution | None
    ) -> PhaseExecution:
        del ctx, source
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


def test_create_run_scans_videos(tmp_path: Path, make_generation_settings: Any) -> None:
    orchestrator, _, project_service = _build_orchestrator(tmp_path)
    input_folder = _seed_input_folder(tmp_path)
    settings = make_generation_settings(input_folder=input_folder)
    project = project_service.create_project(
        name="Test", workspace_folder=tmp_path / "ws", generation=settings
    )
    run = orchestrator.create_run(project)
    assert len(run.sources) == 2
    assert run.status is RunStatus.CREATED


def test_create_run_raises_when_no_videos(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    orchestrator, _, project_service = _build_orchestrator(tmp_path)
    empty_folder = tmp_path / "empty"
    empty_folder.mkdir()
    settings = make_generation_settings(input_folder=empty_folder)
    project = project_service.create_project(
        name="Test", workspace_folder=tmp_path / "ws", generation=settings
    )
    with pytest.raises(ConfigError):
        orchestrator.create_run(project)


def test_execute_completes_run_successfully(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    orchestrator, _, project_service = _build_orchestrator(tmp_path)
    input_folder = _seed_input_folder(tmp_path)
    settings = make_generation_settings(input_folder=input_folder)
    project = project_service.create_project(
        name="Test", workspace_folder=tmp_path / "ws", generation=settings
    )
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
    tmp_path: Path, make_generation_settings: Any
) -> None:
    orchestrator, _, project_service = _build_orchestrator(tmp_path)
    input_folder = _seed_input_folder(tmp_path)
    project = project_service.create_project(
        name="Test",
        workspace_folder=tmp_path / "ws",
        generation=make_generation_settings(input_folder=input_folder),
    )
    before = datetime.now(tz=UTC)
    run = orchestrator.create_run(project)
    orchestrator.execute(run=run, ctx=_build_ctx(tmp_path, run))
    reloaded = project_service.get_project(project.id)
    assert reloaded is not None
    assert reloaded.last_run_at is not None
    assert reloaded.last_run_at >= before


# --- resume_or_create_run -----------------------------------------------


def test_resume_or_create_creates_new_when_no_run_exists(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    orchestrator, _, project_service = _build_orchestrator(tmp_path)
    input_folder = _seed_input_folder(tmp_path)
    project = project_service.create_project(
        name="Test",
        workspace_folder=tmp_path / "ws",
        generation=make_generation_settings(input_folder=input_folder),
    )
    run, is_resumed = orchestrator.resume_or_create_run(project)
    assert is_resumed is False
    assert run.status is RunStatus.CREATED


def test_resume_or_create_resumes_failed_run(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    orchestrator, state, project_service = _build_orchestrator(tmp_path)
    input_folder = _seed_input_folder(tmp_path)
    project = project_service.create_project(
        name="Test",
        workspace_folder=tmp_path / "ws",
        generation=make_generation_settings(input_folder=input_folder),
    )
    # Premier passage : crée un Run, le marque FAILED en DB
    failed_run = orchestrator.create_run(project).with_status(RunStatus.FAILED)
    state.upsert_run(failed_run)

    resumed, is_resumed = orchestrator.resume_or_create_run(project)
    assert is_resumed is True
    assert resumed.id == failed_run.id
    assert resumed.status is RunStatus.FAILED


def test_resume_or_create_resumes_paused_run(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    orchestrator, state, project_service = _build_orchestrator(tmp_path)
    input_folder = _seed_input_folder(tmp_path)
    project = project_service.create_project(
        name="Test",
        workspace_folder=tmp_path / "ws",
        generation=make_generation_settings(input_folder=input_folder),
    )
    paused = orchestrator.create_run(project).with_status(RunStatus.PAUSED)
    state.upsert_run(paused)

    resumed, is_resumed = orchestrator.resume_or_create_run(project)
    assert is_resumed is True
    assert resumed.id == paused.id


def test_resume_or_create_resumes_running_orphan(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    """Reg : si l'app a crashé pendant un Run RUNNING, le statut reste à
    RUNNING en DB. Au prochain Lancer on doit reprendre, pas tout refaire."""
    orchestrator, state, project_service = _build_orchestrator(tmp_path)
    input_folder = _seed_input_folder(tmp_path)
    project = project_service.create_project(
        name="Test",
        workspace_folder=tmp_path / "ws",
        generation=make_generation_settings(input_folder=input_folder),
    )
    orphan = orchestrator.create_run(project).with_status(RunStatus.RUNNING)
    state.upsert_run(orphan)

    resumed, is_resumed = orchestrator.resume_or_create_run(project)
    assert is_resumed is True
    assert resumed.id == orphan.id


def test_resume_or_create_does_not_resume_completed(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    orchestrator, state, project_service = _build_orchestrator(tmp_path)
    input_folder = _seed_input_folder(tmp_path)
    project = project_service.create_project(
        name="Test",
        workspace_folder=tmp_path / "ws",
        generation=make_generation_settings(input_folder=input_folder),
    )
    completed = orchestrator.create_run(project).with_status(RunStatus.COMPLETED)
    state.upsert_run(completed)

    new_run, is_resumed = orchestrator.resume_or_create_run(project)
    assert is_resumed is False
    assert new_run.id != completed.id
    assert new_run.status is RunStatus.CREATED


def test_resume_or_create_does_not_resume_cancelled(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    orchestrator, state, project_service = _build_orchestrator(tmp_path)
    input_folder = _seed_input_folder(tmp_path)
    project = project_service.create_project(
        name="Test",
        workspace_folder=tmp_path / "ws",
        generation=make_generation_settings(input_folder=input_folder),
    )
    cancelled = orchestrator.create_run(project).with_status(RunStatus.CANCELLED)
    state.upsert_run(cancelled)

    new_run, is_resumed = orchestrator.resume_or_create_run(project)
    assert is_resumed is False
    assert new_run.id != cancelled.id


def test_execute_can_resume_failed_run_skipping_succeeded_phases(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    """Reg : reprendre un Run FAILED skip les phases SUCCEEDED et
    retente celle qui avait echoue."""
    orchestrator, state, project_service = _build_orchestrator(tmp_path)
    input_folder = _seed_input_folder(tmp_path)
    project = project_service.create_project(
        name="Test",
        workspace_folder=tmp_path / "ws",
        generation=make_generation_settings(input_folder=input_folder),
    )

    # Premier passage : Run cree + persiste comme FAILED apres une phase
    # marquee SUCCEEDED pour la 1ere video et FAILED pour la 2eme.
    run = orchestrator.create_run(project)
    state.upsert_phase_execution(
        run.id,
        PhaseExecution(phase_id=PhaseId.STT, status=PhaseStatus.SUCCEEDED),
        source_id=run.sources[0].source_id,
    )
    state.upsert_phase_execution(
        run.id,
        PhaseExecution(phase_id=PhaseId.STT, status=PhaseStatus.FAILED),
        source_id=run.sources[1].source_id,
    )
    state.upsert_run(run.with_status(RunStatus.FAILED))

    # Reprise : on doit retomber sur le meme Run + il se termine en SUCCESS
    # car _NoOpHandler reussit toujours.
    resumed_run, is_resumed = orchestrator.resume_or_create_run(project)
    assert is_resumed is True
    final = orchestrator.execute(run=resumed_run, ctx=_build_ctx(tmp_path, resumed_run))
    assert final is RunStatus.COMPLETED
    # La phase video[0] doit etre passee a SKIPPED (deja SUCCEEDED) ; la
    # phase video[1] doit etre repassee a SUCCEEDED apres reexecution.
    s0 = state.get_phase_status(
        resumed_run.id, PhaseId.STT, source_id=run.sources[0].source_id
    )
    s1 = state.get_phase_status(
        resumed_run.id, PhaseId.STT, source_id=run.sources[1].source_id
    )
    assert s0 is PhaseStatus.SKIPPED
    assert s1 is PhaseStatus.SUCCEEDED


def test_execute_preserves_pedagogy_settings(
    tmp_path: Path,
    make_generation_settings: Any,
    make_pedagogy_settings: Any,
) -> None:
    """Reg SP2/01 : un run de generation ne doit pas effacer ``Project.pedagogy``."""
    orchestrator, _, project_service = _build_orchestrator(tmp_path)
    input_folder = _seed_input_folder(tmp_path)
    settings = make_generation_settings(input_folder=input_folder)
    project = project_service.create_project(
        name="Test", workspace_folder=tmp_path / "ws", generation=settings
    )
    # On configure la pedagogie apres creation (parite avec l'usage reel).
    project_service.update_project(
        Project(
            id=project.id,
            name=project.name,
            workspace_folder=project.workspace_folder,
            created_at=project.created_at,
            generation=project.generation,
            pedagogy=make_pedagogy_settings(),
        )
    )
    run = orchestrator.create_run(project)
    orchestrator.execute(run=run, ctx=_build_ctx(tmp_path, run))

    reloaded = project_service.get_project(project.id)
    assert reloaded is not None
    assert reloaded.pedagogy is not None
