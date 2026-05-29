"""Tests de RunMatrixViewModel (matrice de coût générique)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from types import MappingProxyType
from typing import Any

from fahmi2.domain.enums import PhaseId, PhaseStatus, RunStatus, SourceKind
from fahmi2.domain.ids import ProjectId, RunId, SourceId
from fahmi2.domain.phase import PhaseExecution
from fahmi2.domain.project import Project
from fahmi2.domain.run import Run
from fahmi2.domain.source import InputSource, SourceExecution
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
    tmp_path: Path, make_generation_settings: Any
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
        SourceExecution(
            source_id=SourceId.new(),
            source=InputSource(kind=SourceKind.VIDEO, location=str(tmp_path / f"v{i}.mp4")),
        )
        for i in range(2)
    )
    run = Run(
        id=RunId.new(),
        project_id=project.id,
        started_at=datetime.now(tz=UTC),
        status=RunStatus.RUNNING,
        settings_snapshot=settings,
        sources=videos,
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


def test_snapshot_row_per_video_and_phase_columns(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    state, run, registry = _setup(tmp_path, make_generation_settings)
    vm = RunMatrixViewModel(state=state, registry=registry)
    snap = vm.cost_matrix_snapshot(run)
    assert len(snap.row_labels) == 2  # 2 vidéos
    assert snap.column_labels == ("Ingestion", "Termes", "Glossaire")
    assert snap.row_labels[0] == run.sources[0].source.as_path.name


def test_per_video_cost_in_cell_and_row_total(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    state, run, registry = _setup(tmp_path, make_generation_settings)
    state.upsert_phase_execution(
        run.id,
        PhaseExecution(
            phase_id=PhaseId.STT, status=PhaseStatus.SUCCEEDED, cost_usd=0.05
        ),
        source_id=run.sources[0].source_id,
    )
    vm = RunMatrixViewModel(state=state, registry=registry)
    snap = vm.cost_matrix_snapshot(run)
    assert snap.cells[0][0].status is PhaseStatus.SUCCEEDED
    assert snap.cells[0][0].cost_usd == 0.05
    assert snap.row_totals[0] == 0.05  # somme des phases par-vidéo de la vidéo 0


def test_batch_phase_cost_visible_on_first_row_only(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    """Le coût d'une phase batch est rendu visible sur la **1ʳᵉ cellule**
    de sa colonne (sinon l'utilisateur ne voit qu'un tiret dans toute la
    colonne et conclut à un coût manquant). Les autres cellules de la
    même colonne restent à ``None`` pour éviter qu'un lecteur ne calcule
    « coût × N lignes » par erreur — le total de colonne reste la
    valeur batch unique, autorité.
    """
    state, run, registry = _setup(tmp_path, make_generation_settings)
    state.upsert_phase_execution(
        run.id,
        PhaseExecution(
            phase_id=PhaseId.GLOSSARY_RECONCILIATION,
            status=PhaseStatus.SUCCEEDED,
            cost_usd=0.20,
        ),
        source_id=None,
    )
    vm = RunMatrixViewModel(state=state, registry=registry)
    snap = vm.cost_matrix_snapshot(run)
    # colonne 2 = Glossaire (batch).
    # 1ʳᵉ ligne : statut + coût visible.
    assert snap.cells[0][2].status is PhaseStatus.SUCCEEDED
    assert snap.cells[0][2].cost_usd == 0.20
    # Ligne suivante : statut conservé, coût `None` pour éviter la
    # confusion d'addition mentale verticale.
    assert snap.cells[1][2].status is PhaseStatus.SUCCEEDED
    assert snap.cells[1][2].cost_usd is None
    # Total colonne = coût batch unique (pas une somme).
    assert snap.column_totals[2] == 0.20
    # Grand total : batch compté une seule fois, jamais N×.
    assert snap.grand_total == 0.20
    # Row totals des 2 lignes : aucune ne doit inclure le coût batch.
    assert snap.row_totals[0] == 0.0
    assert snap.row_totals[1] == 0.0


def test_batch_phase_with_per_source_attribution_renders_per_cell(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    """Phase batch mixte (phase 5/6) avec ``per_source_costs`` : chaque cellule
    affiche le coût attribué à sa source. Les cellules de sources non
    attribuées (cas où le ``per_source_costs`` est partiel) restent à
    ``None``.

    Comportement clé : le total de colonne reste le coût batch unique (peut
    être supérieur à la somme des cellules visibles → résidu non
    attribuable). Les row_totals incluent les attributions per-source.
    """
    state, run, registry = _setup(tmp_path, make_generation_settings)
    # On simule une attribution sur la 1ʳᵉ source (typique : ledger pour
    # source 0 a coûté 0.07, total batch = 0.20 dont 0.13 non attribuable).
    state.upsert_phase_execution(
        run.id,
        PhaseExecution(
            phase_id=PhaseId.GLOSSARY_RECONCILIATION,
            status=PhaseStatus.SUCCEEDED,
            cost_usd=0.20,
            per_source_costs=MappingProxyType({run.sources[0].source_id: 0.07}),
        ),
        source_id=None,
    )
    vm = RunMatrixViewModel(state=state, registry=registry)
    snap = vm.cost_matrix_snapshot(run)
    # Source 0 : cellule porte la part attribuée.
    assert snap.cells[0][2].cost_usd == 0.07
    # Source 1 : pas d'attribution → None.
    assert snap.cells[1][2].cost_usd is None
    # Total colonne : coût batch entier (autorité, inclut résidu non attribué).
    assert snap.column_totals[2] == 0.20
    # row_totals : source 0 voit sa part, source 1 ne voit rien.
    assert snap.row_totals[0] == 0.07
    assert snap.row_totals[1] == 0.0
    # grand_total = somme row_totals + batch (qui inclut tout) ;
    # le résidu non attribué (0.20 - 0.07 = 0.13) n'est pas perdu.
    assert snap.grand_total == 0.07 + 0.20


def test_pending_batch_phase_shows_no_cost_anywhere(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    """Une phase batch non encore exécutée (pas de ``PhaseExecution`` en
    base) reste ``—`` partout, y compris sur la 1ʳᵉ ligne."""
    state, run, registry = _setup(tmp_path, make_generation_settings)
    # Aucun upsert pour la phase batch glossaire.
    vm = RunMatrixViewModel(state=state, registry=registry)
    snap = vm.cost_matrix_snapshot(run)
    assert snap.cells[0][2].status is PhaseStatus.PENDING
    assert snap.cells[0][2].cost_usd is None
    assert snap.column_totals[2] == 0.0


def test_preview_all_pending(tmp_path: Path, make_generation_settings: Any) -> None:
    state, run, registry = _setup(tmp_path, make_generation_settings)
    vm = RunMatrixViewModel(state=state, registry=registry)
    snap = vm.preview_cost_matrix(run.sources)
    assert len(snap.row_labels) == 2
    assert all(
        cell.status is PhaseStatus.PENDING for row in snap.cells for cell in row
    )
    assert snap.grand_total == 0.0
