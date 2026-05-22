"""Tests du PipelineEngine."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fahmi2.core.errors.exceptions import (
    BudgetExceededError,
    Fahmi2Error,
    PermanentError,
    TransientError,
)
from fahmi2.core.errors.severity import Severity
from fahmi2.core.retrieval.interface import PassthroughRetriever
from fahmi2.core.retry.policy import RetryPolicy
from fahmi2.domain.enums import PhaseId, PhaseStatus, RunStatus, SourceKind
from fahmi2.domain.ids import ProjectId, RunId, SourceId
from fahmi2.domain.phase import PhaseExecution
from fahmi2.domain.project import Project
from fahmi2.domain.run import Run
from fahmi2.domain.source import InputSource, SourceExecution
from fahmi2.infra.audio.ffmpeg_extractor import FFmpegExtractor
from fahmi2.infra.ingestion.dispatcher import build_default_ingestion_dispatcher
from fahmi2.infra.llm._fakes import FakeLLMProvider
from fahmi2.infra.prompts.loader import PromptLoader
from fahmi2.infra.storage.fs_artifacts import FsArtifactStore
from fahmi2.infra.storage.sqlite_state import SqliteState
from fahmi2.infra.stt._fakes import FakeSTTProvider
from fahmi2.pipeline.engine import PipelineEngine
from fahmi2.pipeline.event_bus import EventBus
from fahmi2.pipeline.events import (
    PhaseFinished,
    PhaseStarted,
    PipelineEvent,
    RetryAttempt,
    RunFinished,
    RunStarted,
)
from fahmi2.pipeline.pause_token import PauseToken
from fahmi2.pipeline.phase_handler import PhaseContext, PhaseHandler
from fahmi2.pipeline.phase_registry import PhaseRegistry


class _CountingHandler(PhaseHandler):
    """Handler factice qui compte ses appels et peut être configuré pour échouer."""

    def __init__(
        self,
        phase_id: PhaseId,
        *,
        is_per_source: bool = True,
        fail_until_attempt: int = 0,
        permanent_failure: bool = False,
        raise_on_call: Fahmi2Error | None = None,
        cost_per_call: float = 0.0,
        parallel_workers: int = 1,
    ) -> None:
        self._phase_id = phase_id
        self._per_source = is_per_source
        self.calls: list[SourceId | None] = []
        self._fail_until_attempt = fail_until_attempt
        self._permanent_failure = permanent_failure
        self._raise_on_call = raise_on_call
        self._cost_per_call = cost_per_call
        self._parallel_workers = parallel_workers
        self._attempts: dict[str, int] = {}

    @property
    def phase_id(self) -> PhaseId:
        return self._phase_id

    @property
    def is_per_source(self) -> bool:
        return self._per_source

    def max_parallel_workers(self, ctx: PhaseContext) -> int:
        del ctx
        return self._parallel_workers

    def execute(
        self, ctx: PhaseContext, *, source: SourceExecution | None
    ) -> PhaseExecution:
        del ctx
        key = source.source_id.value if source else "_batch"
        self._attempts[key] = self._attempts.get(key, 0) + 1
        self.calls.append(source.source_id if source else None)

        if self._raise_on_call is not None:
            raise self._raise_on_call
        if self._permanent_failure:
            raise PermanentError(
                code="TEST.PERMANENT",
                user_message="boom",
                severity=Severity.ERROR,
            )
        if self._attempts[key] <= self._fail_until_attempt:
            raise TransientError(
                code="TEST.TRANSIENT",
                user_message="retry me",
                severity=Severity.WARNING,
            )
        return PhaseExecution(
            phase_id=self._phase_id,
            status=PhaseStatus.SUCCEEDED,
            cost_usd=self._cost_per_call,
        )


def _make_ctx(
    tmp_path: Path,
    make_generation_settings: Any,
    *,
    n_videos: int = 2,
) -> PhaseContext:
    settings = make_generation_settings()
    state = SqliteState(tmp_path / "state.db")
    project_id = ProjectId.new()
    project = Project(
        id=project_id,
        name="Test",
        workspace_folder=tmp_path / "workspace",
        created_at=datetime.now(tz=UTC),
        generation=settings,
    )
    state.upsert_project(project)
    videos = tuple(
        SourceExecution(
            source_id=SourceId.new(),
            source=InputSource(kind=SourceKind.VIDEO, location=str(tmp_path / f"v{i}.mp4")),
        )
        for i in range(n_videos)
    )
    run = Run(
        id=RunId.new(),
        project_id=project_id,
        started_at=datetime.now(tz=UTC),
        status=RunStatus.RUNNING,
        settings_snapshot=settings,
        sources=videos,
    )
    state.upsert_run(run)
    return PhaseContext(
        run=run,
        settings=settings,
        workspace=tmp_path / "workspace",
        output_dir=tmp_path / "output",
        state=state,
        artifacts=FsArtifactStore(),
        stt_provider=FakeSTTProvider(),
        llm_provider=FakeLLMProvider(),
        ffmpeg=FFmpegExtractor(),
        ingestion=build_default_ingestion_dispatcher(),
        retriever=PassthroughRetriever(),
        prompts=PromptLoader(),
        pause_token=PauseToken(),
        event_bus=EventBus(),
    )


def _make_engine(*handlers: PhaseHandler) -> PipelineEngine:
    registry = PhaseRegistry(handlers)
    return PipelineEngine(
        registry=registry,
        retry_policy=RetryPolicy(
            max_attempts=3, initial_delay_seconds=0.001, jitter=False
        ),
    )


# --- engine main flow --------------------------------------------------------


def test_default_max_parallel_workers_is_one(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    ctx = _make_ctx(tmp_path, make_generation_settings, n_videos=1)
    handler = _CountingHandler(PhaseId.STT, is_per_source=True)
    assert handler.max_parallel_workers(ctx) == 1


def test_engine_runs_phase_per_video(tmp_path: Path, make_generation_settings: Any) -> None:
    ctx = _make_ctx(tmp_path, make_generation_settings, n_videos=3)
    handler = _CountingHandler(PhaseId.STT, is_per_source=True)
    engine = _make_engine(handler)
    final = engine.execute(ctx)
    assert final is RunStatus.COMPLETED
    assert len(handler.calls) == 3


def test_engine_runs_batch_phase_once(tmp_path: Path, make_generation_settings: Any) -> None:
    ctx = _make_ctx(tmp_path, make_generation_settings, n_videos=5)
    handler = _CountingHandler(PhaseId.GLOSSARY_RECONCILIATION, is_per_source=False)
    engine = _make_engine(handler)
    engine.execute(ctx)
    assert handler.calls == [None]


def test_engine_skips_already_succeeded(tmp_path: Path, make_generation_settings: Any) -> None:
    ctx = _make_ctx(tmp_path, make_generation_settings, n_videos=2)
    # Pré-marquer la 1re vidéo comme SUCCEEDED
    pe = PhaseExecution(phase_id=PhaseId.STT, status=PhaseStatus.SUCCEEDED)
    ctx.state.upsert_phase_execution(
        ctx.run.id, pe, source_id=ctx.run.sources[0].source_id
    )
    handler = _CountingHandler(PhaseId.STT, is_per_source=True)
    engine = _make_engine(handler)
    engine.execute(ctx)
    assert len(handler.calls) == 1  # juste la 2e vidéo


def test_engine_retries_transient_errors(tmp_path: Path, make_generation_settings: Any) -> None:
    ctx = _make_ctx(tmp_path, make_generation_settings, n_videos=1)
    handler = _CountingHandler(
        PhaseId.STT, is_per_source=True, fail_until_attempt=1
    )
    engine = _make_engine(handler)
    final = engine.execute(ctx)
    assert final is RunStatus.COMPLETED
    assert len(handler.calls) == 2  # 1 échec + 1 succès


def test_engine_fails_on_permanent_error(tmp_path: Path, make_generation_settings: Any) -> None:
    ctx = _make_ctx(tmp_path, make_generation_settings, n_videos=1)
    handler = _CountingHandler(
        PhaseId.STT, is_per_source=True, permanent_failure=True
    )
    engine = _make_engine(handler)
    final = engine.execute(ctx)
    assert final is RunStatus.FAILED


def test_engine_emits_run_started_and_finished(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    ctx = _make_ctx(tmp_path, make_generation_settings, n_videos=1)
    events: list[PipelineEvent] = []
    ctx.event_bus.subscribe(events.append)
    handler = _CountingHandler(PhaseId.STT, is_per_source=True)
    engine = _make_engine(handler)
    engine.execute(ctx)
    assert isinstance(events[0], RunStarted)
    assert isinstance(events[-1], RunFinished)
    assert events[-1].final_status is RunStatus.COMPLETED


def test_engine_emits_phase_started_and_finished(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    ctx = _make_ctx(tmp_path, make_generation_settings, n_videos=1)
    events: list[PipelineEvent] = []
    ctx.event_bus.subscribe(events.append)
    handler = _CountingHandler(PhaseId.STT, is_per_source=True)
    engine = _make_engine(handler)
    engine.execute(ctx)
    starts = [e for e in events if isinstance(e, PhaseStarted)]
    finishes = [e for e in events if isinstance(e, PhaseFinished)]
    assert len(starts) == 1
    assert len(finishes) == 1


def test_engine_emits_retry_attempt(tmp_path: Path, make_generation_settings: Any) -> None:
    ctx = _make_ctx(tmp_path, make_generation_settings, n_videos=1)
    events: list[PipelineEvent] = []
    ctx.event_bus.subscribe(events.append)
    handler = _CountingHandler(
        PhaseId.STT, is_per_source=True, fail_until_attempt=1
    )
    engine = _make_engine(handler)
    engine.execute(ctx)
    retries = [e for e in events if isinstance(e, RetryAttempt)]
    assert len(retries) == 1


def test_engine_respects_budget_exceeded(tmp_path: Path, make_generation_settings: Any) -> None:
    ctx = _make_ctx(tmp_path, make_generation_settings, n_videos=1)
    handler = _CountingHandler(
        PhaseId.STT,
        is_per_source=True,
        raise_on_call=BudgetExceededError(
            code="BUDGET.EXCEEDED",
            user_message="x",
            severity=Severity.WARNING,
        ),
    )
    engine = _make_engine(handler)
    final = engine.execute(ctx)
    assert final is RunStatus.PAUSED


def test_engine_respects_cancel(tmp_path: Path, make_generation_settings: Any) -> None:
    ctx = _make_ctx(tmp_path, make_generation_settings, n_videos=2)
    handler = _CountingHandler(PhaseId.STT, is_per_source=True)

    # On cancel le token avant exécution
    ctx.pause_token.request_cancel()
    engine = _make_engine(handler)
    final = engine.execute(ctx)
    assert final is RunStatus.CANCELLED
    assert handler.calls == []  # aucune vidéo traitée


def test_engine_persists_phase_status_succeeded(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    ctx = _make_ctx(tmp_path, make_generation_settings, n_videos=1)
    handler = _CountingHandler(PhaseId.STT, is_per_source=True)
    engine = _make_engine(handler)
    engine.execute(ctx)
    source_id = ctx.run.sources[0].source_id
    status = ctx.state.get_phase_status(ctx.run.id, PhaseId.STT, source_id=source_id)
    assert status is PhaseStatus.SUCCEEDED


def test_engine_persists_phase_status_failed(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    ctx = _make_ctx(tmp_path, make_generation_settings, n_videos=1)
    handler = _CountingHandler(PhaseId.STT, is_per_source=True, permanent_failure=True)
    engine = _make_engine(handler)
    engine.execute(ctx)
    source_id = ctx.run.sources[0].source_id
    status = ctx.state.get_phase_status(ctx.run.id, PhaseId.STT, source_id=source_id)
    assert status is PhaseStatus.FAILED


def test_engine_parallel_per_video_processes_all_videos(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    ctx = _make_ctx(tmp_path, make_generation_settings, n_videos=6)
    handler = _CountingHandler(PhaseId.STT, is_per_source=True, parallel_workers=4)
    engine = _make_engine(handler)
    final = engine.execute(ctx)
    assert final is RunStatus.COMPLETED
    assert len(handler.calls) == 6
    assert set(handler.calls) == {v.source_id for v in ctx.run.sources}
    for video in ctx.run.sources:
        assert (
            ctx.state.get_phase_status(ctx.run.id, PhaseId.STT, source_id=video.source_id)
            is PhaseStatus.SUCCEEDED
        )
