"""Tests de StatsStripViewModel."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fahmi2.domain.enums import PhaseId, PhaseStatus, RunStatus
from fahmi2.domain.ids import ProjectId, RunId, VideoId
from fahmi2.domain.phase import PhaseExecution
from fahmi2.domain.project import Project
from fahmi2.domain.run import Run
from fahmi2.domain.video import VideoExecution
from fahmi2.infra.storage.sqlite_state import SqliteState
from fahmi2.pipeline.handlers.phase_0_stt import Phase0SttHandler
from fahmi2.pipeline.handlers.phase_1_term_extraction import (
    Phase1TermExtractionHandler,
)
from fahmi2.pipeline.handlers.phase_2_glossary_reconciliation import (
    Phase2GlossaryReconciliationHandler,
)
from fahmi2.pipeline.phase_registry import PhaseRegistry
from fahmi2.ui.viewmodels.stats_strip import StatsStripViewModel


def _setup(
    tmp_path: Path, make_generation_settings: Any, *, n_videos: int = 2
) -> tuple[SqliteState, Run, PhaseRegistry]:
    state = SqliteState(tmp_path / "t.db")
    settings = make_generation_settings()
    project = Project(
        id=ProjectId.new(),
        name="Test",
        workspace_folder=tmp_path / "ws",
        created_at=datetime.now(tz=UTC),
        generation=settings,
    )
    state.upsert_project(project)
    videos = tuple(
        VideoExecution(video_id=VideoId.new(), source_path=tmp_path / f"v{i}.mp4")
        for i in range(n_videos)
    )
    run = Run(
        id=RunId.new(),
        project_id=project.id,
        started_at=datetime.now(tz=UTC),
        status=RunStatus.RUNNING,
        settings_snapshot=settings,
        videos=videos,
    )
    state.upsert_run(run)
    registry = PhaseRegistry(
        [
            Phase0SttHandler(),
            Phase1TermExtractionHandler(),
            Phase2GlossaryReconciliationHandler(),
        ]
    )
    return state, run, registry


def test_snapshot_zero_when_run_starts(tmp_path: Path, make_generation_settings: Any) -> None:
    state, run, registry = _setup(tmp_path, make_generation_settings)
    vm = StatsStripViewModel(state=state, registry=registry)
    snap = vm.snapshot(run)
    assert snap.videos_total == 2
    assert snap.videos_completed == 0
    assert snap.cost_usd_so_far == 0.0


def test_snapshot_counts_completed_videos(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    state, run, registry = _setup(tmp_path, make_generation_settings)
    # Marquer toutes les phases per-video succeeded pour video[0]
    per_video_phase_ids = [
        h.phase_id for h in registry.ordered_handlers() if h.is_per_video
    ]
    for pid in per_video_phase_ids:
        state.upsert_phase_execution(
            run.id,
            PhaseExecution(phase_id=pid, status=PhaseStatus.SUCCEEDED),
            video_id=run.videos[0].video_id,
        )
    vm = StatsStripViewModel(state=state, registry=registry)
    snap = vm.snapshot(run)
    assert snap.videos_completed == 1


def test_snapshot_accumulates_cost(tmp_path: Path, make_generation_settings: Any) -> None:
    state, run, registry = _setup(tmp_path, make_generation_settings)
    state.upsert_phase_execution(
        run.id,
        PhaseExecution(
            phase_id=PhaseId.STT,
            status=PhaseStatus.SUCCEEDED,
            cost_usd=0.5,
        ),
        video_id=run.videos[0].video_id,
    )
    state.upsert_phase_execution(
        run.id,
        PhaseExecution(
            phase_id=PhaseId.STT,
            status=PhaseStatus.SUCCEEDED,
            cost_usd=0.3,
        ),
        video_id=run.videos[1].video_id,
    )
    vm = StatsStripViewModel(state=state, registry=registry)
    snap = vm.snapshot(run)
    assert snap.cost_usd_so_far == 0.8


def test_snapshot_reports_run_status(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    state, run, registry = _setup(tmp_path, make_generation_settings)
    vm = StatsStripViewModel(state=state, registry=registry)
    snap = vm.snapshot(run)
    assert snap.run_status is RunStatus.RUNNING
