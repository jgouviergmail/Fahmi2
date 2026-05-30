"""Tests du viewmodel de progression des Visualisations."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from fahmi2.domain.enums import Language, PhaseStatus, RunStatus
from fahmi2.ui.viewmodels.visuals_progress import VisualsProgressViewModel
from fahmi2.ui.visuals_labels import VisualsDeliverable, deliverable_label
from fahmi2.visuals.events import (
    VisualsGenerationFinished,
    VisualsGenerationStarted,
    VisualsLanguageFinished,
    VisualsLanguageStarted,
    VisualsStructureFinished,
    VisualsStructureProgress,
    VisualsStructureStarted,
    VisualsStructureStep,
)

_DELIVERABLES = (VisualsDeliverable.KNOWLEDGE_MAP, VisualsDeliverable.DIAGRAMS)
_LANGS = (Language.FR, Language.EN)
# Colonnes : [Structure, fr, en] → langues décalées d'une position.
_COL_STRUCTURE = 0
_COL_FR = 1
_COL_EN = 2


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
    # La colonne « Structure » précède les colonnes de langues.
    assert matrix.column_labels == ("Structure", "fr", "en")
    assert all(
        cell.status is PhaseStatus.PENDING for row in matrix.cells for cell in row
    )
    stats = vm.stats_snapshot()
    assert stats.languages_total == 2
    assert stats.languages_done == 0
    assert stats.cost_ceiling_usd == 5.0


def test_structure_progress_updates_structure_column() -> None:
    vm = _vm()
    vm.apply_event(VisualsGenerationStarted(timestamp=_ts()))
    vm.apply_event(VisualsStructureStarted(timestamp=_ts()))
    matrix = vm.cost_matrix_snapshot()
    # Les deux cellules « Structure » passent en cours.
    assert matrix.cells[0][_COL_STRUCTURE].status is PhaseStatus.RUNNING
    assert matrix.cells[1][_COL_STRUCTURE].status is PhaseStatus.RUNNING
    # Une progression « graphe » alimente la cellule Structure de la Carte.
    vm.apply_event(
        VisualsStructureProgress(
            timestamp=_ts(), step=VisualsStructureStep.GRAPH, completed=12, total=32
        )
    )
    matrix = vm.cost_matrix_snapshot()
    assert "12/32" in matrix.cells[0][_COL_STRUCTURE].tooltip
    # Les langues restent en attente tant que la structure n'est pas finie.
    assert matrix.cells[0][_COL_FR].status is PhaseStatus.PENDING


def test_structure_finished_marks_structure_succeeded() -> None:
    vm = _vm()
    vm.apply_event(VisualsStructureStarted(timestamp=_ts()))
    vm.apply_event(VisualsStructureFinished(timestamp=_ts()))
    matrix = vm.cost_matrix_snapshot()
    assert matrix.cells[0][_COL_STRUCTURE].status is PhaseStatus.SUCCEEDED
    assert matrix.cells[1][_COL_STRUCTURE].status is PhaseStatus.SUCCEEDED


def test_structure_running_reconciled_to_failed_on_failure() -> None:
    vm = _vm()
    vm.apply_event(VisualsStructureStarted(timestamp=_ts()))
    # Échec pendant l'extraction de structure : pas de VisualsStructureFinished.
    vm.apply_event(
        VisualsGenerationFinished(
            timestamp=_ts(), status=RunStatus.FAILED, total_cost_usd=0.1
        )
    )
    matrix = vm.cost_matrix_snapshot()
    # Les cellules Structure ne restent pas « en cours » : figées en échec.
    assert matrix.cells[0][_COL_STRUCTURE].status is PhaseStatus.FAILED
    assert matrix.cells[1][_COL_STRUCTURE].status is PhaseStatus.FAILED


def test_language_lifecycle_updates_status_and_cost() -> None:
    vm = _vm()
    vm.apply_event(VisualsGenerationStarted(timestamp=_ts()))
    vm.apply_event(VisualsLanguageStarted(timestamp=_ts(), language=Language.FR))
    matrix = vm.cost_matrix_snapshot()
    assert matrix.cells[0][_COL_FR].status is PhaseStatus.RUNNING
    vm.apply_event(
        VisualsLanguageFinished(
            timestamp=_ts(),
            language=Language.FR,
            status=PhaseStatus.SUCCEEDED,
            cost_usd=0.4,
            error=None,
            map_cost_usd=0.3,
            diagrams_cost_usd=0.1,
        )
    )
    matrix = vm.cost_matrix_snapshot()
    # Les deux livrables de la langue partagent le même statut.
    assert matrix.cells[0][_COL_FR].status is PhaseStatus.SUCCEEDED
    assert matrix.cells[1][_COL_FR].status is PhaseStatus.SUCCEEDED
    # Le coût est ventilé par livrable sur les cellules.
    assert matrix.cells[0][_COL_FR].cost_usd == 0.3  # Carte
    assert matrix.cells[1][_COL_FR].cost_usd == 0.1  # Diagrammes
    stats = vm.stats_snapshot()
    assert stats.languages_done == 1
    assert stats.total_cost_usd == 0.4
    assert stats.overall_status is RunStatus.RUNNING


def test_costs_populate_cells_structure_and_total() -> None:
    vm = _vm()
    vm.apply_event(VisualsGenerationStarted(timestamp=_ts()))
    vm.apply_event(VisualsStructureStarted(timestamp=_ts()))
    vm.apply_event(
        VisualsStructureFinished(
            timestamp=_ts(), map_cost_usd=0.10, diagrams_cost_usd=0.02
        )
    )
    vm.apply_event(VisualsLanguageStarted(timestamp=_ts(), language=Language.FR))
    vm.apply_event(
        VisualsLanguageFinished(
            timestamp=_ts(),
            language=Language.FR,
            status=PhaseStatus.SUCCEEDED,
            cost_usd=0.03,
            error=None,
            map_cost_usd=0.02,
            diagrams_cost_usd=0.01,
        )
    )
    matrix = vm.cost_matrix_snapshot()
    # Colonne Structure : coût par livrable.
    assert matrix.cells[0][_COL_STRUCTURE].cost_usd == pytest.approx(0.10)
    assert matrix.cells[1][_COL_STRUCTURE].cost_usd == pytest.approx(0.02)
    # Colonne fr : coût de localisation par livrable.
    assert matrix.cells[0][_COL_FR].cost_usd == pytest.approx(0.02)
    assert matrix.cells[1][_COL_FR].cost_usd == pytest.approx(0.01)
    # Total de la matrice = structure + langue ; concorde avec la tuile.
    assert matrix.grand_total == pytest.approx(0.15)
    assert vm.stats_snapshot().total_cost_usd == pytest.approx(0.15)


def test_load_persisted_peuple_les_couts_par_cellule() -> None:
    vm = _vm()
    vm.load_persisted(
        deliverables=_DELIVERABLES,
        languages=_LANGS,
        generated_languages=[Language.FR],
        total_cost_usd=0.12,
        structure_costs=(0.08, 0.01),
        language_costs={Language.FR: (0.02, 0.01)},
    )
    matrix = vm.cost_matrix_snapshot()
    # Colonne Structure (carte / diagrammes).
    assert matrix.cells[0][_COL_STRUCTURE].cost_usd == pytest.approx(0.08)
    assert matrix.cells[1][_COL_STRUCTURE].cost_usd == pytest.approx(0.01)
    # Colonne fr (carte / diagrammes).
    assert matrix.cells[0][_COL_FR].cost_usd == pytest.approx(0.02)
    assert matrix.cells[1][_COL_FR].cost_usd == pytest.approx(0.01)
    # EN non produit → coût non rattaché.
    assert matrix.cells[0][_COL_EN].cost_usd is None
    assert vm.stats_snapshot().total_cost_usd == pytest.approx(0.12)


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
    assert matrix.cells[0][_COL_EN].status is PhaseStatus.FAILED
    assert matrix.cells[1][_COL_EN].status is PhaseStatus.FAILED


def test_load_persisted_marks_generated_languages_and_structure() -> None:
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
    # Des livrables présents → structure à jour.
    assert matrix.cells[0][_COL_STRUCTURE].status is PhaseStatus.SUCCEEDED
    assert matrix.cells[0][_COL_FR].status is PhaseStatus.SUCCEEDED  # fr généré
    assert matrix.cells[0][_COL_EN].status is PhaseStatus.PENDING  # en non généré
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
