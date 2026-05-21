"""Événements émis par le ``SupportsOrchestrator`` lors d'une génération.

Immuables, bridgés à l'UI via ``EventBus[PedagogyEvent]`` (et un ``QtEventBus``
côté UI, SP2/04). Réutilisent les statuts domaine ``PhaseStatus`` (unité de
travail) et ``RunStatus`` (génération globale) — pas de nouvel enum.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from fahmi2.core.errors.error_info import ErrorInfo
from fahmi2.domain.enums import Language, PhaseStatus, RunStatus, SupportType


@dataclass(frozen=True)
class SupportGenerationStarted:
    """Démarrage d'une génération de supports.

    Attributes:
        timestamp: Horodatage.
    """

    timestamp: datetime


@dataclass(frozen=True)
class SupportStarted:
    """Démarrage de la génération d'un support pour une langue.

    Attributes:
        timestamp: Horodatage.
        support_type: Type de support.
        language: Langue.
    """

    timestamp: datetime
    support_type: SupportType
    language: Language


@dataclass(frozen=True)
class SupportFinished:
    """Fin de la génération d'un support pour une langue.

    Attributes:
        timestamp: Horodatage.
        support_type: Type de support.
        language: Langue.
        status: ``SUCCEEDED``, ``SKIPPED`` (artefact frais) ou ``FAILED``.
        cost_usd: Coût LLM de ce support (0.0 si sans LLM ou skippé).
        error: ``ErrorInfo`` si échec, sinon ``None``.
    """

    timestamp: datetime
    support_type: SupportType
    language: Language
    status: PhaseStatus
    cost_usd: float
    error: ErrorInfo | None


@dataclass(frozen=True)
class SupportRetryAttempt:
    """Tentative de retry d'un appel LLM pour un support.

    Attributes:
        timestamp: Horodatage.
        support_type: Type de support.
        language: Langue.
        attempt: Numéro de tentative (1-indexed).
        delay_seconds: Délai avant la prochaine tentative.
        error: ``ErrorInfo`` de l'échec déclencheur.
    """

    timestamp: datetime
    support_type: SupportType
    language: Language
    attempt: int
    delay_seconds: float
    error: ErrorInfo


@dataclass(frozen=True)
class SupportGenerationFinished:
    """Fin d'une génération de supports.

    Attributes:
        timestamp: Horodatage.
        status: ``COMPLETED``, ``FAILED`` (≥1 support échoué), ``CANCELLED``
            (annulé) ou ``PAUSED`` (plafond de coût atteint).
        total_cost_usd: Coût LLM cumulé.
    """

    timestamp: datetime
    status: RunStatus
    total_cost_usd: float


PedagogyEvent = (
    SupportGenerationStarted
    | SupportStarted
    | SupportRetryAttempt
    | SupportFinished
    | SupportGenerationFinished
)
