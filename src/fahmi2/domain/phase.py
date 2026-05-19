"""Entités ``PhaseConfig`` (paramètres) et ``PhaseExecution`` (état d'exécution)."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

from fahmi2.core.errors.error_info import ErrorInfo
from fahmi2.domain.enums import PhaseId, PhaseStatus

_TEMPERATURE_MIN = 0.0
_TEMPERATURE_MAX = 2.0
_DEFAULT_TEMPERATURE = 0.3
_DEFAULT_MAX_RETRIES = 5


@dataclass(frozen=True)
class PhaseConfig:
    """Paramètres LLM d'une phase (configurable par projet).

    Attributes:
        enabled_thinking: Active ou non le mode raisonnement DeepSeek.
        temperature: Température LLM dans ``[0.0, 2.0]``.
        max_retries: Nombre maximal de tentatives (>= 0).
    """

    enabled_thinking: bool = False
    temperature: float = _DEFAULT_TEMPERATURE
    max_retries: int = _DEFAULT_MAX_RETRIES

    def __post_init__(self) -> None:
        if not _TEMPERATURE_MIN <= self.temperature <= _TEMPERATURE_MAX:
            raise ValueError(
                f"temperature must be in [{_TEMPERATURE_MIN}, {_TEMPERATURE_MAX}], "
                f"got {self.temperature}"
            )
        if self.max_retries < 0:
            raise ValueError(f"max_retries must be >= 0, got {self.max_retries}")


@dataclass(frozen=True)
class PhaseExecution:
    """État d'exécution d'une phase (pour une vidéo ou pour le batch).

    Attributes:
        phase_id: Identifiant de la phase.
        status: État courant.
        started_at: Timestamp de début (None si pas encore commencée).
        finished_at: Timestamp de fin (None si non terminée).
        artifact_path: Chemin de l'artefact produit (None si non produit).
        retry_count: Nombre de tentatives échouées avant la tentative courante.
        cost_usd: Coût cumulé en USD pour cette phase.
        error: ``ErrorInfo`` si la phase a échoué, sinon ``None``.
    """

    phase_id: PhaseId
    status: PhaseStatus
    started_at: datetime | None = None
    finished_at: datetime | None = None
    artifact_path: Path | None = None
    retry_count: int = 0
    cost_usd: float = 0.0
    error: ErrorInfo | None = None

    def with_status(self, status: PhaseStatus) -> PhaseExecution:
        """Retourne une copie avec un nouveau ``status``.

        Args:
            status: Nouvel état.

        Returns:
            Une nouvelle ``PhaseExecution`` immuable.
        """
        return replace(self, status=status)
