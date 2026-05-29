"""Tests du viewmodel de progression des Visualisations."""

from __future__ import annotations

from datetime import UTC, datetime

from fahmi2.domain.enums import Language, PhaseStatus, RunStatus
from fahmi2.ui.viewmodels.visuals_progress import VisualsProgressViewModel
from fahmi2.ui.visuals_labels import VisualsDeliverable, deliverable_label
from fahmi2.visuals.events import (
    VisualsGenerationFinished,
    VisualsGenerationStarted,
    VisualsLanguageFinished,
    VisualsLanguageStarted,
)

_DELIVERABLES = (VisualsDeliverable.KNOWLEDGE_MAP, VisualsDeliverable.DIAGRAMS)
_LANGS = (Language.FR, Language.EN)


def _ts() -> datetime:
    return datetime(2026, 5, 29, tzinfo=UTC)


def _vm() -> VisualsProgressViewModel:
    vm = VisualsProgressViewModel()
    vm.reset(deliverables=_DELIVERABLES, languages=_LANGS, cost_ceiling_usd=5.0)
    return vm


def test_reset_initialises_pending_grid() -> None:
    vm = _vm()
    matrix = vm.cost_matrix_snapshot()
    assert matrix.row_labels == (
        deliverable_label(VisualsDeliverable.KNOWLEDGE_MAP),
        deliverable_label(VisualsDeliverable.DIAGRAMS),
    )
    assert matrix.column_labels == ("fr", "en")
    assert all(
        cell.status is PhaseStatus.PENDING for row in matrix.cells for cell in row
    )
    stats = vm.stats_snapshot()
    assert stats.languages_total == 2
    assert stats.languages_done == 0
    assert stats.cost_ceiling_usd == 5.0


def test_language_lifecycle_updates_status_and_cost() -> None:
    vm = _vm()
    vm.apply_event(VisualsGenerationStarted(timestamp=_ts()))
    vm.apply_event(VisualsLanguageStarted(timestamp=_ts(), language=Language.FR))
    matrix = vm.cost_matrix_snapshot()
    assert matrix.cells[0][0].status is PhaseStatus.RUNNING
    vm.apply_event(
        VisualsLanguageFinished(
            timestamp=_ts(),
            language=Language.FR,
            status=PhaseStatus.SUCCEEDED,
            cost_usd=0.4,
            error=None,
        )
    )
    matrix = vm.cost_matrix_snapshot()
    # Les deux livrables de la langue partagent le même statut.
    assert matrix.cells[0][0].status is PhaseStatus.SUCCEEDED
    assert matrix.cells[1][0].status is PhaseStatus.SUCCEEDED
    # Le coût n'est pas rattaché aux cellules (porté par les tuiles).
    assert matrix.cells[0][0].cost_usd is None
    stats = vm.stats_snapshot()
    assert stats.languages_done == 1
    assert stats.total_cost_usd == 0.4
    assert stats.overall_status is RunStatus.RUNNING


def test_generation_finished_sets_authoritative_total() -> None:
    vm = _vm()
    vm.apply_event(VisualsGenerationStarted(timestamp=_ts()))
    vm.apply_event(
        VisualsLanguageFinished(
            timestamp=_ts(),
            language=Language.FR,
            status=PhaseStatus.SUCCEEDED,
            cost_usd=0.4,
            error=None,
        )
    )
    # Le total faisant foi (incluant l'extraction de structure) > somme par langue.
    vm.apply_event(
        VisualsGenerationFinished(
            timestamp=_ts(), status=RunStatus.COMPLETED, total_cost_usd=1.2
        )
    )
    stats = vm.stats_snapshot()
    assert stats.total_cost_usd == 1.2
    assert stats.overall_status is RunStatus.COMPLETED
    assert stats.finished_at == _ts()


def test_failed_language_marks_both_deliverables() -> None:
    vm = _vm()
    vm.apply_event(
        VisualsLanguageFinished(
            timestamp=_ts(),
            language=Language.EN,
            status=PhaseStatus.FAILED,
            cost_usd=0.0,
            error=None,
        )
    )
    matrix = vm.cost_matrix_snapshot()
    assert matrix.cells[0][1].status is PhaseStatus.FAILED
    assert matrix.cells[1][1].status is PhaseStatus.FAILED


def test_load_persisted_marks_generated_languages() -> None:
    vm = VisualsProgressViewModel()
    vm.load_persisted(
        deliverables=_DELIVERABLES,
        languages=_LANGS,
        generated_languages=[Language.FR],
        total_cost_usd=0.9,
        cost_ceiling_usd=5.0,
        overall_status=RunStatus.COMPLETED,
        started_at=_ts(),
        finished_at=_ts(),
    )
    matrix = vm.cost_matrix_snapshot()
    assert matrix.cells[0][0].status is PhaseStatus.SUCCEEDED  # fr généré
    assert matrix.cells[0][1].status is PhaseStatus.PENDING  # en non généré
    stats = vm.stats_snapshot()
    assert stats.languages_done == 1
    assert stats.total_cost_usd == 0.9
    assert stats.overall_status is RunStatus.COMPLETED


def test_single_deliverable_has_one_row() -> None:
    vm = VisualsProgressViewModel()
    vm.reset(
        deliverables=(VisualsDeliverable.KNOWLEDGE_MAP,), languages=_LANGS
    )
    matrix = vm.cost_matrix_snapshot()
    assert len(matrix.row_labels) == 1
    assert matrix.row_labels[0] == deliverable_label(
        VisualsDeliverable.KNOWLEDGE_MAP
    )
