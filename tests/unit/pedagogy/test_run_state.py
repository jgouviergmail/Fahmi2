"""Tests de la persistance de l'état d'exécution pédagogie (run_state.json)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from fahmi2.domain.enums import RunStatus
from fahmi2.infra.storage.fs_artifacts import FsArtifactStore
from fahmi2.pedagogy.run_state import (
    PedagogyRunState,
    read_run_state,
    write_run_state,
)


def test_read_absent_returns_none(tmp_path: Path) -> None:
    assert read_run_state(tmp_path) is None


def test_write_then_read_roundtrip(tmp_path: Path) -> None:
    state = PedagogyRunState(
        status=RunStatus.COMPLETED,
        started_at=datetime(2026, 5, 21, 10, 0, tzinfo=UTC),
        finished_at=datetime(2026, 5, 21, 10, 3, tzinfo=UTC),
        total_cost_usd=1.5,
    )
    write_run_state(FsArtifactStore(), tmp_path, state)
    assert read_run_state(tmp_path) == state


def test_running_state_has_no_finished_at(tmp_path: Path) -> None:
    state = PedagogyRunState(
        status=RunStatus.RUNNING,
        started_at=datetime(2026, 5, 21, 10, 0, tzinfo=UTC),
        finished_at=None,
        total_cost_usd=0.0,
    )
    write_run_state(FsArtifactStore(), tmp_path, state)
    loaded = read_run_state(tmp_path)
    assert loaded is not None
    assert loaded.status is RunStatus.RUNNING
    assert loaded.finished_at is None


def test_corrupt_file_returns_none(tmp_path: Path) -> None:
    (tmp_path / "run_state.json").write_text("{ pas du json", encoding="utf-8")
    assert read_run_state(tmp_path) is None
