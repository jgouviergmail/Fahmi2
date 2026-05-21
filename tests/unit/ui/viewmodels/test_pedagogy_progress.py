"""Tests du viewmodel de progression pédagogie (accumulation d'events)."""

from __future__ import annotations

from datetime import UTC, datetime

from fahmi2.domain.enums import Language, PhaseStatus, RunStatus, SupportType
from fahmi2.pedagogy.events import (
    SupportFinished,
    SupportGenerationFinished,
    SupportGenerationStarted,
    SupportStarted,
)
from fahmi2.ui.pedagogy_labels import support_label
from fahmi2.ui.viewmodels.pedagogy_progress import PedagogyProgressViewModel


def _now() -> datetime:
    return datetime.now(tz=UTC)


def test_reset_populates_pending_cells() -> None:
    vm = PedagogyProgressViewModel()
    vm.reset(
        supports=(SupportType.QCM, SupportType.KEY_POINTS),
        languages=(Language.FR,),
    )
    stats = vm.stats_snapshot()
    assert stats.tasks_total == 2
    assert stats.tasks_done == 0
    assert stats.overall_status is None
    snap = vm.cost_matrix_snapshot()
    assert all(
        cell.status is PhaseStatus.PENDING for row in snap.cells for cell in row
    )


def test_started_then_finished_updates_cell() -> None:
    vm = PedagogyProgressViewModel()
    vm.reset(supports=(SupportType.QCM,), languages=(Language.FR,))
    vm.apply_event(
        SupportStarted(
            timestamp=_now(), support_type=SupportType.QCM, language=Language.FR
        )
    )
    running = vm.cost_matrix_snapshot().cells[0][0]
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
    cell = vm.cost_matrix_snapshot().cells[0][0]
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
    assert vm.stats_snapshot().overall_status is RunStatus.COMPLETED


def test_generation_started_sets_running_and_started_at() -> None:
    vm = PedagogyProgressViewModel()
    vm.reset(supports=(SupportType.QCM,), languages=(Language.FR,))
    started = _now()
    vm.apply_event(SupportGenerationStarted(timestamp=started))
    stats = vm.stats_snapshot()
    assert stats.overall_status is RunStatus.RUNNING
    assert stats.started_at == started
    assert stats.finished_at is None


def test_generation_finished_sets_finished_at() -> None:
    vm = PedagogyProgressViewModel()
    vm.reset(supports=(SupportType.QCM,), languages=(Language.FR,))
    vm.apply_event(SupportGenerationStarted(timestamp=_now()))
    finished = _now()
    vm.apply_event(
        SupportGenerationFinished(
            timestamp=finished, status=RunStatus.COMPLETED, total_cost_usd=0.0
        )
    )
    assert vm.stats_snapshot().finished_at == finished


def test_load_persisted_restores_status_and_timestamps() -> None:
    vm = PedagogyProgressViewModel()
    started = _now()
    finished = _now()
    vm.load_persisted(
        supports=(SupportType.QCM,),
        languages=(Language.FR,),
        generated_costs={},
        overall_status=RunStatus.COMPLETED,
        started_at=started,
        finished_at=finished,
    )
    stats = vm.stats_snapshot()
    assert stats.overall_status is RunStatus.COMPLETED
    assert stats.started_at == started
    assert stats.finished_at == finished


def test_cells_follow_canonical_order() -> None:
    vm = PedagogyProgressViewModel()
    # Fournis dans le désordre -> rangés selon l'ordre canonique des supports.
    vm.reset(
        supports=(SupportType.KEY_POINTS, SupportType.QCM),
        languages=(Language.FR,),
    )
    labels = vm.cost_matrix_snapshot().row_labels
    assert labels.index(support_label(SupportType.QCM)) < labels.index(
        support_label(SupportType.KEY_POINTS)
    )


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


def test_stats_snapshot_reflects_cost_ceiling() -> None:
    vm = PedagogyProgressViewModel()
    vm.reset(
        supports=(SupportType.QCM,),
        languages=(Language.FR,),
        cost_ceiling_usd=5.0,
    )
    assert vm.stats_snapshot().cost_ceiling_usd == 5.0


def test_stats_snapshot_default_has_no_ceiling() -> None:
    vm = PedagogyProgressViewModel()
    vm.reset(supports=(SupportType.QCM,), languages=(Language.FR,))
    assert vm.stats_snapshot().cost_ceiling_usd is None


def test_load_persisted_marks_generated_succeeded_with_cost() -> None:
    vm = PedagogyProgressViewModel()
    vm.load_persisted(
        supports=(SupportType.QCM, SupportType.KEY_POINTS),
        languages=(Language.FR,),
        generated_costs={(SupportType.QCM, Language.FR): 0.12},
        cost_ceiling_usd=3.0,
    )
    snap = vm.cost_matrix_snapshot()
    # QCM/FR généré -> terminé + coût ; KEY_POINTS/FR encore en attente.
    assert snap.cells[0][0].status is PhaseStatus.SUCCEEDED
    assert snap.cells[0][0].cost_usd == 0.12
    assert snap.cells[1][0].status is PhaseStatus.PENDING
    stats = vm.stats_snapshot()
    assert stats.tasks_done == 1
    assert stats.tasks_total == 2
    assert stats.total_cost_usd == 0.12
    assert stats.cost_ceiling_usd == 3.0


def test_load_persisted_ignores_unknown_cells() -> None:
    # Un coût pour un (support, langue) hors sélection est ignoré (pas de cellule).
    vm = PedagogyProgressViewModel()
    vm.load_persisted(
        supports=(SupportType.QCM,),
        languages=(Language.FR,),
        generated_costs={(SupportType.KEY_POINTS, Language.EN): 9.9},
    )
    stats = vm.stats_snapshot()
    assert stats.tasks_done == 0
    assert stats.total_cost_usd == 0.0
