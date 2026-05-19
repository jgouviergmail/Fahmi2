"""ViewModel ``RunMatrixViewModel`` — alimente la matrice vidéos × phases.

Convertit un ``Run`` + ses ``PhaseExecution`` SQLite-loadées en une grille
2D ``(rows=videos, columns=phases)`` directement consommable par un
``QAbstractTableModel`` Qt sans aucune logique métier dans la couche Qt.
"""

from __future__ import annotations

from dataclasses import dataclass

from fahmi2.domain.enums import PhaseId, PhaseStatus
from fahmi2.domain.ids import RunId, VideoId
from fahmi2.domain.run import Run
from fahmi2.infra.storage.sqlite_state import SqliteState
from fahmi2.pipeline.phase_registry import PhaseRegistry


@dataclass(frozen=True)
class MatrixCell:
    """Cellule de la matrice : statut + métadonnées d'affichage.

    Attributes:
        phase_id: Phase associée.
        status: Statut courant.
        cost_usd: Coût accumulé sur cette cellule (0 si non démarrée).
        retry_count: Nombre de retries observés.
        is_batch: ``True`` si la phase n'est pas par-vidéo.
    """

    phase_id: PhaseId
    status: PhaseStatus
    cost_usd: float
    retry_count: int
    is_batch: bool


@dataclass(frozen=True)
class MatrixRow:
    """Ligne de matrice : une vidéo et ses cellules par phase.

    Attributes:
        video_id: ID de la vidéo (None pour la ligne batch).
        video_label: Libellé d'affichage (nom de fichier).
        cells: Cellules indexées par ``PhaseId``.
    """

    video_id: VideoId | None
    video_label: str
    cells: dict[PhaseId, MatrixCell]


@dataclass(frozen=True)
class MatrixSnapshot:
    """Snapshot complet de la matrice à un instant ``t``.

    Attributes:
        run_id: ID du Run.
        phases_in_order: Phases dans l'ordre des colonnes.
        rows: Lignes (une par vidéo + une éventuelle ligne batch agrégée).
    """

    run_id: RunId
    phases_in_order: tuple[PhaseId, ...]
    rows: tuple[MatrixRow, ...]


class RunMatrixViewModel:
    """Construit un ``MatrixSnapshot`` à partir de l'état SQLite d'un Run."""

    def __init__(self, *, state: SqliteState, registry: PhaseRegistry) -> None:
        """Construit le viewmodel.

        Args:
            state: Accès SQLite.
            registry: Registre des handlers de phase (ordre des colonnes).
        """
        self._state = state
        self._registry = registry

    def snapshot(self, run: Run) -> MatrixSnapshot:
        """Construit un snapshot du run courant.

        Args:
            run: Run en cours d'exécution ou terminé.

        Returns:
            ``MatrixSnapshot`` immuable.
        """
        phases = tuple(h.phase_id for h in self._registry.ordered_handlers())
        per_video_phases = {
            h.phase_id for h in self._registry.ordered_handlers() if h.is_per_video
        }

        executions = self._state.list_phase_executions(run.id)
        # On agrège les phases batch par phase_id pour calculer un statut et un
        # coût globaux affichables dans chaque ligne.
        executions_by_phase: dict[PhaseId, list[tuple[PhaseStatus, float, int]]] = {}
        for pe in executions:
            executions_by_phase.setdefault(pe.phase_id, []).append(
                (pe.status, pe.cost_usd, pe.retry_count)
            )

        # Construction des lignes par-vidéo
        rows: list[MatrixRow] = []
        for video in run.videos:
            cells: dict[PhaseId, MatrixCell] = {}
            for phase_id in phases:
                if phase_id in per_video_phases:
                    status = self._state.get_phase_status(
                        run.id, phase_id, video_id=video.video_id
                    ) or PhaseStatus.PENDING
                    cells[phase_id] = MatrixCell(
                        phase_id=phase_id,
                        status=status,
                        cost_usd=0.0,
                        retry_count=0,
                        is_batch=False,
                    )
                else:
                    cells[phase_id] = MatrixCell(
                        phase_id=phase_id,
                        status=_aggregate_status(
                            executions_by_phase.get(phase_id, [])
                        ),
                        cost_usd=sum(
                            t[1] for t in executions_by_phase.get(phase_id, [])
                        ),
                        retry_count=0,
                        is_batch=True,
                    )
            rows.append(
                MatrixRow(
                    video_id=video.video_id,
                    video_label=video.source_path.name,
                    cells=cells,
                )
            )

        return MatrixSnapshot(
            run_id=run.id,
            phases_in_order=phases,
            rows=tuple(rows),
        )

    @property
    def batch_phase_ids(self) -> set[PhaseId]:
        """Identifie les phases batch du registre courant.

        Returns:
            Set des ``PhaseId`` non per-video.
        """
        return {
            h.phase_id for h in self._registry.ordered_handlers() if not h.is_per_video
        }


def _aggregate_status(
    rows: list[tuple[PhaseStatus, float, int]],
) -> PhaseStatus:
    """Calcule un statut agrégé pour une phase batch.

    Règle : si au moins une ligne en RUNNING/FAILED, on remonte ce statut.
    Sinon SUCCEEDED si au moins une SUCCEEDED, sinon PENDING.

    Args:
        rows: Liste de tuples ``(status, cost, retry_count)``.

    Returns:
        Statut agrégé.
    """
    if not rows:
        return PhaseStatus.PENDING
    statuses = [r[0] for r in rows]
    if PhaseStatus.RUNNING in statuses:
        return PhaseStatus.RUNNING
    if PhaseStatus.FAILED in statuses:
        return PhaseStatus.FAILED
    if PhaseStatus.SUCCEEDED in statuses:
        return PhaseStatus.SUCCEEDED
    return statuses[0]
