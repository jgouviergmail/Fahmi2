"""ViewModel ``RunMatrixViewModel`` — alimente la matrice générique de coût.

Convertit un ``Run`` + ses ``PhaseExecution`` SQLite en ``CostMatrixSnapshot``
(lignes = vidéos, colonnes = phases). Les phases **batch** (non per-vidéo) affichent
leur statut sur chaque ligne mais leur **coût n'est porté que par le total de
colonne** (coût au niveau du run, ``—`` en cellule) ; le total de ligne ne somme que
les phases par-vidéo. Sans logique Qt.
"""

from __future__ import annotations

from fahmi2.domain.enums import PhaseId, PhaseStatus
from fahmi2.domain.ids import VideoId
from fahmi2.domain.run import Run
from fahmi2.domain.video import VideoExecution
from fahmi2.infra.storage.sqlite_state import PhaseCell, SqliteState
from fahmi2.pipeline.phase_registry import PhaseRegistry
from fahmi2.ui.viewmodels.cost_matrix import CostMatrixCell, CostMatrixSnapshot

_ROW_HEADER = "Vidéo"

_PHASE_SHORT_LABELS: dict[PhaseId, str] = {
    PhaseId.STT: "STT",
    PhaseId.TERM_EXTRACTION: "Termes",
    PhaseId.GLOSSARY_RECONCILIATION: "Glossaire",
    PhaseId.REFORMULATION: "Reformul.",
    PhaseId.STRUCTURATION: "Structur.",
    PhaseId.CONSOLIDATION: "Consolid.",
    PhaseId.TRANSLATION: "Traduction",
    PhaseId.COHERENCE: "Cohérence",
}

_STATUS_LABEL: dict[PhaseStatus, str] = {
    PhaseStatus.PENDING: "en attente",
    PhaseStatus.RUNNING: "en cours",
    PhaseStatus.SUCCEEDED: "terminé",
    PhaseStatus.FAILED: "échec",
    PhaseStatus.SKIPPED: "déjà fait",
}


class RunMatrixViewModel:
    """Construit un ``CostMatrixSnapshot`` à partir de l'état SQLite d'un Run."""

    def __init__(self, *, state: SqliteState, registry: PhaseRegistry) -> None:
        """Construit le viewmodel.

        Args:
            state: Accès SQLite.
            registry: Registre des handlers (ordre des colonnes + per-video).
        """
        self._state = state
        self._registry = registry

    def _phases(self) -> tuple[tuple[PhaseId, bool], ...]:
        """Phases dans l'ordre canonique + drapeau per-vidéo.

        Returns:
            Tuple de ``(phase_id, is_per_video)``.
        """
        return tuple(
            (h.phase_id, h.is_per_video) for h in self._registry.ordered_handlers()
        )

    def cost_matrix_snapshot(self, run: Run) -> CostMatrixSnapshot:
        """Construit la matrice vidéos × phases (statut + coût + totaux).

        Args:
            run: Run en cours ou terminé.

        Returns:
            ``CostMatrixSnapshot`` (coût batch porté par les totaux de colonne).
        """
        cells_by_key: dict[tuple[PhaseId, VideoId | None], PhaseCell] = {
            (c.phase_id, c.video_id): c for c in self._state.list_phase_cells(run.id)
        }
        return self._build(run.videos, self._phases(), cells_by_key)

    def preview_cost_matrix(
        self, videos: tuple[VideoExecution, ...]
    ) -> CostMatrixSnapshot:
        """Matrice de prévisualisation (toutes phases ``PENDING``, coût 0).

        Args:
            videos: Vidéos détectées.

        Returns:
            ``CostMatrixSnapshot`` sans coût.
        """
        return self._build(videos, self._phases(), {})

    def _build(
        self,
        videos: tuple[VideoExecution, ...],
        phases: tuple[tuple[PhaseId, bool], ...],
        cells_by_key: dict[tuple[PhaseId, VideoId | None], PhaseCell],
    ) -> CostMatrixSnapshot:
        """Assemble le snapshot (cellules + totaux, gestion batch).

        Args:
            videos: Vidéos (lignes).
            phases: Phases + drapeau per-vidéo (colonnes).
            cells_by_key: Statut/coût par ``(phase, vidéo|None)``.

        Returns:
            Le ``CostMatrixSnapshot`` complet.
        """
        column_labels = tuple(_PHASE_SHORT_LABELS.get(p, p.value) for p, _ in phases)
        grid: list[tuple[CostMatrixCell, ...]] = []
        row_totals: list[float] = []
        for video in videos:
            row: list[CostMatrixCell] = []
            row_total = 0.0
            for phase_id, per_video in phases:
                key = (phase_id, video.video_id if per_video else None)
                pc = cells_by_key.get(key)
                status = pc.status if pc is not None else PhaseStatus.PENDING
                cost = pc.cost_usd if pc is not None else 0.0
                if per_video:
                    row_total += cost
                    cell_cost = cost if pc is not None else None
                else:
                    cell_cost = None  # batch : coût au niveau du run (cf. total)
                row.append(
                    CostMatrixCell(
                        status=status,
                        cost_usd=cell_cost,
                        tooltip=_tooltip(phase_id, status, cost, batch=not per_video),
                    )
                )
            grid.append(tuple(row))
            row_totals.append(row_total)

        column_totals: list[float] = []
        grand_total = sum(row_totals)
        for phase_id, per_video in phases:
            if per_video:
                column_totals.append(
                    sum(
                        pc.cost_usd
                        for v in videos
                        if (pc := cells_by_key.get((phase_id, v.video_id))) is not None
                    )
                )
            else:
                batch = cells_by_key.get((phase_id, None))
                batch_cost = batch.cost_usd if batch is not None else 0.0
                column_totals.append(batch_cost)
                grand_total += batch_cost

        return CostMatrixSnapshot(
            row_header=_ROW_HEADER,
            column_labels=column_labels,
            row_labels=tuple(v.source_path.name for v in videos),
            cells=tuple(grid),
            row_totals=tuple(row_totals),
            column_totals=tuple(column_totals),
            grand_total=grand_total,
        )


def _tooltip(
    phase_id: PhaseId, status: PhaseStatus, cost: float, *, batch: bool = False
) -> str:
    """Construit l'infobulle d'une cellule.

    Args:
        phase_id: Phase.
        status: Statut.
        cost: Coût.
        batch: ``True`` si phase batch (coût au niveau du run).

    Returns:
        Texte d'infobulle.
    """
    label = _STATUS_LABEL.get(status, status.value)
    suffix = " (coût au niveau du run)" if batch else ""
    return f"{phase_id.value} — {label} — coût: ${cost:.4f}{suffix}"
