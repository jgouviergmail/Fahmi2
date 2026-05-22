"""ViewModel ``StatsStripViewModel`` — bande de stats agrégées d'un Run."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from fahmi2.domain.enums import Language, PhaseStatus, RunStatus
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
            ``SUCCEEDED`` ou ``SKIPPED``.
        phases_total: Nombre total de phases enregistrées.
        phases_completed: Nombre de phases ayant atteint ``SUCCEEDED`` ou
            ``SKIPPED``.
        cost_usd_so_far: Coût cumulé en USD.
        cost_ceiling_usd: Plafond éventuel.
        started_at: Date de démarrage du Run.
        finished_at: Date de fin (``None`` si le Run n'est pas terminé).
        elapsed_seconds: Durée écoulée en secondes (figée à ``finished_at -
            started_at`` si le Run est terminé, sinon ``now - started_at``).
        languages: Langues de sortie de la génération.
    """

    run_status: RunStatus
    videos_total: int
    videos_completed: int
    phases_total: int
    phases_completed: int
    cost_usd_so_far: float
    cost_ceiling_usd: float | None
    started_at: datetime
    finished_at: datetime | None
    elapsed_seconds: float
    languages: tuple[Language, ...]


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
        per_source_phase_ids = [
            h.phase_id for h in self._registry.ordered_handlers() if h.is_per_source
        ]
        videos_total = len(run.sources)
        videos_completed = 0
        # Une phase per-source est considérée comme terminée si elle est
        # SUCCEEDED ou SKIPPED (skip = succès d'un run précédent).
        completed_statuses = {PhaseStatus.SUCCEEDED, PhaseStatus.SKIPPED}
        for source in run.sources:
            done = all(
                self._state.get_phase_status(
                    run.id, phase_id, source_id=source.source_id
                )
                in completed_statuses
                for phase_id in per_source_phase_ids
            )
            if done and per_source_phase_ids:
                videos_completed += 1

        executions = self._state.list_phase_executions(run.id)
        phases_total = len(executions)
        phases_completed = sum(
            1 for e in executions if e.status in completed_statuses
        )
        cost = sum(e.cost_usd for e in executions)

        end_ts = run.finished_at if run.finished_at is not None else datetime.now(tz=UTC)
        elapsed = max(0.0, (end_ts - run.started_at).total_seconds())

        return StatsSnapshot(
            run_status=run.status,
            videos_total=videos_total,
            videos_completed=videos_completed,
            phases_total=phases_total,
            phases_completed=phases_completed,
            cost_usd_so_far=cost,
            cost_ceiling_usd=run.settings_snapshot.cost_ceiling_usd,
            started_at=run.started_at,
            finished_at=run.finished_at,
            elapsed_seconds=elapsed,
            languages=run.settings_snapshot.output_languages,
        )
