"""ViewModel ``StatsStripViewModel`` — bande de stats agrégées d'un Run."""

from __future__ import annotations

from dataclasses import dataclass

from fahmi2.domain.enums import PhaseStatus, RunStatus
from fahmi2.domain.run import Run
from fahmi2.infra.storage.sqlite_state import SqliteState
from fahmi2.pipeline.phase_registry import PhaseRegistry


@dataclass(frozen=True)
class StatsSnapshot:
    """Snapshot des stats agrégées d'un Run.

    Attributes:
        run_status: Statut global du Run.
        videos_total: Nombre total de vidéos.
        videos_completed: Vidéos dont toutes les phases per-video sont
            ``SUCCEEDED``.
        phases_total: Nombre total de phases enregistrées.
        phases_completed: Nombre de phases ayant atteint ``SUCCEEDED``.
        cost_usd_so_far: Coût cumulé en USD.
        cost_ceiling_usd: Plafond éventuel.
    """

    run_status: RunStatus
    videos_total: int
    videos_completed: int
    phases_total: int
    phases_completed: int
    cost_usd_so_far: float
    cost_ceiling_usd: float | None


class StatsStripViewModel:
    """Construit un ``StatsSnapshot`` à partir de l'état SQLite d'un Run."""

    def __init__(self, *, state: SqliteState, registry: PhaseRegistry) -> None:
        """Construit le viewmodel.

        Args:
            state: Accès SQLite.
            registry: Registre des handlers (utilisé pour compter les phases).
        """
        self._state = state
        self._registry = registry

    def snapshot(self, run: Run) -> StatsSnapshot:
        """Construit le snapshot pour un Run.

        Args:
            run: Run.

        Returns:
            ``StatsSnapshot``.
        """
        per_video_phase_ids = [
            h.phase_id for h in self._registry.ordered_handlers() if h.is_per_video
        ]
        videos_total = len(run.videos)
        videos_completed = 0
        for video in run.videos:
            done = all(
                self._state.get_phase_status(
                    run.id, phase_id, video_id=video.video_id
                )
                is PhaseStatus.SUCCEEDED
                for phase_id in per_video_phase_ids
            )
            if done and per_video_phase_ids:
                videos_completed += 1

        executions = self._state.list_phase_executions(run.id)
        phases_total = len(executions)
        phases_completed = sum(
            1 for e in executions if e.status is PhaseStatus.SUCCEEDED
        )
        cost = sum(e.cost_usd for e in executions)

        return StatsSnapshot(
            run_status=run.status,
            videos_total=videos_total,
            videos_completed=videos_completed,
            phases_total=phases_total,
            phases_completed=phases_completed,
            cost_usd_so_far=cost,
            cost_ceiling_usd=run.settings_snapshot.cost_ceiling_usd,
        )
