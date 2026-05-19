"""Tests de RunMatrixViewModel."""

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
from fahmi2.ui.viewmodels.run_matrix import RunMatrixViewModel


def _setup(
    tmp_path: Path, make_settings: Any
) -> tuple[SqliteState, Run, PhaseRegistry]:
    state = SqliteState(tmp_path / "t.db")
    settings = make_settings()
    project = Project(
        id=ProjectId.new(), settings=settings, created_at=datetime.now(tz=UTC)
    )
    state.upsert_project(project)
    videos = tuple(
        VideoExecution(video_id=VideoId.new(), source_path=tmp_path / f"v{i}.mp4")
        for i in range(2)
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


def test_snapshot_has_row_per_video(tmp_path: Path, make_settings: Any) -> None:
    state, run, registry = _setup(tmp_path, make_settings)
    viewmodel = RunMatrixViewModel(state=state, registry=registry)
    snap = viewmodel.snapshot(run)
    assert len(snap.rows) == 2


def test_snapshot_columns_match_phases_in_canonical_order(
    tmp_path: Path, make_settings: Any
) -> None:
    state, run, registry = _setup(tmp_path, make_settings)
    viewmodel = RunMatrixViewModel(state=state, registry=registry)
    snap = viewmodel.snapshot(run)
    assert snap.phases_in_order == (
        PhaseId.STT,
        PhaseId.TERM_EXTRACTION,
        PhaseId.GLOSSARY_RECONCILIATION,
    )


def test_cell_status_reflects_state(tmp_path: Path, make_settings: Any) -> None:
    state, run, registry = _setup(tmp_path, make_settings)
    first_video = run.videos[0]
    pe = PhaseExecution(phase_id=PhaseId.STT, status=PhaseStatus.SUCCEEDED)
    state.upsert_phase_execution(run.id, pe, video_id=first_video.video_id)

    viewmodel = RunMatrixViewModel(state=state, registry=registry)
    snap = viewmodel.snapshot(run)
    cell = snap.rows[0].cells[PhaseId.STT]
    assert cell.status is PhaseStatus.SUCCEEDED
    assert cell.is_batch is False


def test_batch_phase_marked_as_batch(tmp_path: Path, make_settings: Any) -> None:
    state, run, registry = _setup(tmp_path, make_settings)
    viewmodel = RunMatrixViewModel(state=state, registry=registry)
    snap = viewmodel.snapshot(run)
    batch_cell = snap.rows[0].cells[PhaseId.GLOSSARY_RECONCILIATION]
    assert batch_cell.is_batch is True
    assert batch_cell.status is PhaseStatus.PENDING


def test_batch_phase_status_after_succeeded(
    tmp_path: Path, make_settings: Any
) -> None:
    state, run, registry = _setup(tmp_path, make_settings)
    pe = PhaseExecution(
        phase_id=PhaseId.GLOSSARY_RECONCILIATION, status=PhaseStatus.SUCCEEDED
    )
    state.upsert_phase_execution(run.id, pe, video_id=None)
    viewmodel = RunMatrixViewModel(state=state, registry=registry)
    snap = viewmodel.snapshot(run)
    cell = snap.rows[0].cells[PhaseId.GLOSSARY_RECONCILIATION]
    assert cell.status is PhaseStatus.SUCCEEDED


def test_video_label_is_filename(tmp_path: Path, make_settings: Any) -> None:
    state, run, registry = _setup(tmp_path, make_settings)
    viewmodel = RunMatrixViewModel(state=state, registry=registry)
    snap = viewmodel.snapshot(run)
    assert snap.rows[0].video_label == run.videos[0].source_path.name
