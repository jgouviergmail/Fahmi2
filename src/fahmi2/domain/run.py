"""Entité ``Run`` — exécution complète d'un Project à un instant t."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime

from fahmi2.domain.enums import PhaseId, RunStatus
from fahmi2.domain.ids import ProjectId, RunId
from fahmi2.domain.phase import PhaseExecution
from fahmi2.domain.project import ProjectSettings
from fahmi2.domain.video import VideoExecution


@dataclass(frozen=True)
class Run:
    """Représente une exécution complète d'un Project.

    Les ``videos`` et ``phase_executions`` sont mis à jour par le pipeline. Le
    ``settings_snapshot`` est une copie immuable des ``ProjectSettings`` au
    moment du démarrage du run : modifier le ``Project`` après lancement
    n'affecte pas le ``Run`` en cours.

    Attributes:
        id: Identifiant stable du run.
        project_id: Référence vers le ``Project`` parent.
        started_at: Date de démarrage.
        status: État global.
        settings_snapshot: Copie immuable des paramètres à t0.
        finished_at: Date de fin (None si non terminé).
        cost_usd: Coût cumulé en USD.
        videos: Tuple immuable des ``VideoExecution``.
        phase_executions: Phases batch (2, 5) au niveau Run.
    """

    id: RunId
    project_id: ProjectId
    started_at: datetime
    status: RunStatus
    settings_snapshot: ProjectSettings
    finished_at: datetime | None = None
    cost_usd: float = 0.0
    videos: tuple[VideoExecution, ...] = ()
    phase_executions: dict[PhaseId, PhaseExecution] = field(default_factory=dict)

    def with_status(self, status: RunStatus) -> Run:
        """Retourne une copie avec un nouveau ``status``.

        Args:
            status: Nouvel état.

        Returns:
            Nouvelle instance immuable.
        """
        return replace(self, status=status)

    def with_added_cost(self, amount: float) -> Run:
        """Retourne une copie avec ``amount`` ajouté à ``cost_usd``.

        Args:
            amount: Montant en USD à ajouter (positif).

        Returns:
            Nouvelle instance immuable.
        """
        return replace(self, cost_usd=self.cost_usd + amount)

    def with_finished_at(self, ts: datetime) -> Run:
        """Retourne une copie avec ``finished_at = ts``.

        Args:
            ts: Date de fin.

        Returns:
            Nouvelle instance immuable.
        """
        return replace(self, finished_at=ts)
