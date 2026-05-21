"""Tests du viewmodel de progression pédagogie (accumulation d'events)."""

from __future__ import annotations

from datetime import UTC, datetime

from fahmi2.domain.enums import Language, PhaseStatus, RunStatus, SupportType
from fahmi2.pedagogy.events import (
    SupportFinished,
    SupportGenerationFinished,
    SupportStarted,
)
from fahmi2.ui.viewmodels.pedagogy_progress import PedagogyProgressViewModel


def _now() -> datetime:
    return datetime.now(tz=UTC)


def test_reset_populates_pending_cells() -> None:
    vm = PedagogyProgressViewModel()
    vm.reset(
        supports=(SupportType.QCM, SupportType.KEY_POINTS),
        languages=(Language.FR,),
    )
    snapshot = vm.snapshot()
    assert len(snapshot.cells) == 2
    assert all(cell.status is None for cell in snapshot.cells)
    assert snapshot.overall_status is None


def test_started_then_finished_updates_cell() -> None:
    vm = PedagogyProgressViewModel()
    vm.reset(supports=(SupportType.QCM,), languages=(Language.FR,))
    vm.apply_event(
        SupportStarted(
            timestamp=_now(), support_type=SupportType.QCM, language=Language.FR
        )
    )
    running = vm.snapshot().cells[0]
    assert running.status is PhaseStatus.RUNNING
    vm.apply_event(
        SupportFinished(
            timestamp=_now(),
            support_type=SupportType.QCM,
            language=Language.FR,
            status=PhaseStatus.SUCCEEDED,
            cost_usd=0.1,
            error=None,
        )
    )
    cell = vm.snapshot().cells[0]
    assert cell.status is PhaseStatus.SUCCEEDED
    assert cell.cost_usd == 0.1


def test_generation_finished_sets_overall() -> None:
    vm = PedagogyProgressViewModel()
    vm.reset(supports=(SupportType.QCM,), languages=(Language.FR,))
    vm.apply_event(
        SupportGenerationFinished(
            timestamp=_now(), status=RunStatus.COMPLETED, total_cost_usd=0.42
        )
    )
    snapshot = vm.snapshot()
    assert snapshot.overall_status is RunStatus.COMPLETED
    assert snapshot.total_cost_usd == 0.42


def test_cells_follow_canonical_order() -> None:
    vm = PedagogyProgressViewModel()
    # Fournis dans le désordre -> rangés selon l'ordre canonique des supports.
    vm.reset(
        supports=(SupportType.KEY_POINTS, SupportType.QCM),
        languages=(Language.FR,),
    )
    ordered = [cell.support_type for cell in vm.snapshot().cells]
    assert ordered.index(SupportType.QCM) < ordered.index(SupportType.KEY_POINTS)


def test_cost_matrix_snapshot_grid() -> None:
    vm = PedagogyProgressViewModel()
    vm.reset(
        supports=(SupportType.QCM, SupportType.KEY_POINTS),
        languages=(Language.FR, Language.EN),
    )
    vm.apply_event(
        SupportFinished(
            timestamp=_now(),
            support_type=SupportType.QCM,
            language=Language.FR,
            status=PhaseStatus.SUCCEEDED,
            cost_usd=0.10,
            error=None,
        )
    )
    snap = vm.cost_matrix_snapshot()
    assert snap.row_header == "Support"
    assert snap.column_labels == ("fr", "en")
    assert snap.row_labels[0] == "QCM"  # ordre canonique (QCM avant points clés)
    assert snap.grand_total == 0.10
    assert snap.cells[0][0].status is PhaseStatus.SUCCEEDED
    assert snap.cells[0][1].cost_usd is None  # QCM/EN en attente


def test_stats_snapshot_counts() -> None:
    vm = PedagogyProgressViewModel()
    vm.reset(supports=(SupportType.QCM,), languages=(Language.FR, Language.EN))
    vm.apply_event(
        SupportFinished(
            timestamp=_now(),
            support_type=SupportType.QCM,
            language=Language.FR,
            status=PhaseStatus.SUCCEEDED,
            cost_usd=0.10,
            error=None,
        )
    )
    stats = vm.stats_snapshot()
    assert stats.tasks_total == 2
    assert stats.tasks_done == 1
    assert stats.languages == (Language.FR, Language.EN)
    assert stats.total_cost_usd == 0.10
