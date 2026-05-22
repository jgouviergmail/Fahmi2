"""Événements émis par le ``PipelineEngine`` lors de l'exécution d'un Run.

Chaque événement est immuable et porteur d'informations contextuelles (run,
phase, source concernée). Les ``EventBus`` (in-memory ou Qt-bridgé) les
distribuent aux abonnés.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from fahmi2.core.errors.error_info import ErrorInfo
from fahmi2.domain.enums import PhaseId, PhaseStatus, RunStatus
from fahmi2.domain.ids import RunId, SourceId


@dataclass(frozen=True)
class RunStarted:
    """Signale le démarrage effectif d'un Run.

    Attributes:
        timestamp: Horodatage de l'événement.
        run_id: Identifiant du Run.
    """

    timestamp: datetime
    run_id: RunId


@dataclass(frozen=True)
class RunFinished:
    """Signale la fin d'un Run (succès, annulation, ou échec irrécupérable).

    Attributes:
        timestamp: Horodatage de l'événement.
        run_id: Identifiant du Run.
        final_status: Statut final.
    """

    timestamp: datetime
    run_id: RunId
    final_status: RunStatus


@dataclass(frozen=True)
class PhaseStarted:
    """Signale le démarrage d'une phase pour un Run.

    Attributes:
        timestamp: Horodatage.
        run_id: Run propriétaire.
        phase_id: Phase qui démarre.
        source_id: Source associée (``None`` pour les phases batch).
    """

    timestamp: datetime
    run_id: RunId
    phase_id: PhaseId
    source_id: SourceId | None


@dataclass(frozen=True)
class PhaseProgress:
    """Mise à jour de progression d'une phase en cours.

    Attributes:
        timestamp: Horodatage.
        run_id: Run propriétaire.
        phase_id: Phase concernée.
        source_id: Source associée (``None`` pour batch).
        progress: Valeur dans ``[0.0, 1.0]``.
    """

    timestamp: datetime
    run_id: RunId
    phase_id: PhaseId
    source_id: SourceId | None
    progress: float


@dataclass(frozen=True)
class PhaseFinished:
    """Signale la fin d'une phase pour un Run.

    Attributes:
        timestamp: Horodatage.
        run_id: Run.
        phase_id: Phase.
        source_id: Source associée (None pour batch).
        final_status: ``SUCCEEDED``, ``FAILED``, ``SKIPPED``.
        cost_usd: Coût cumulé sur cette phase.
        error: ``ErrorInfo`` si échec, ``None`` sinon.
    """

    timestamp: datetime
    run_id: RunId
    phase_id: PhaseId
    source_id: SourceId | None
    final_status: PhaseStatus
    cost_usd: float
    error: ErrorInfo | None


@dataclass(frozen=True)
class RetryAttempt:
    """Signale une tentative de retry pour une phase.

    Attributes:
        timestamp: Horodatage.
        run_id: Run.
        phase_id: Phase.
        source_id: Source associée (None pour batch).
        attempt: Numéro de tentative (1-indexed).
        delay_seconds: Délai d'attente avant la prochaine tentative.
        error: ``ErrorInfo`` de l'échec qui a déclenché le retry.
    """

    timestamp: datetime
    run_id: RunId
    phase_id: PhaseId
    source_id: SourceId | None
    attempt: int
    delay_seconds: float
    error: ErrorInfo


PipelineEvent = (
    RunStarted
    | RunFinished
    | PhaseStarted
    | PhaseProgress
    | PhaseFinished
    | RetryAttempt
)
