"""Modèle d'événement de log structuré.

Tous les sinks (JSONL, Qt, console) consomment des ``LogEvent``. Les ``LogEvent``
sont immuables et sérialisables en JSON sans transformation supplémentaire.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from fahmi2.core.errors.severity import Severity


@dataclass(frozen=True)
class LogEvent:
    """Événement de log structuré.

    Attributes:
        timestamp: Datetime aware (UTC recommandé).
        severity: Niveau de gravité.
        code: Code stable identifiant le type d'événement.
        message: Texte libre destiné au lecteur.
        run_id: ULID du Run associé, optionnel.
        phase_id: Identifiant de la phase associée, optionnel.
        source_id: ULID de la source associée, optionnel.
        extra: Métadonnées additionnelles (sérialisables JSON).
    """

    timestamp: datetime
    severity: Severity
    code: str
    message: str
    run_id: str | None = None
    phase_id: str | None = None
    source_id: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Sérialise en dict JSON-friendly.

        Returns:
            Dictionnaire encodable JSON.
        """
        return {
            "timestamp": self.timestamp.isoformat(),
            "severity": str(self.severity),
            "code": self.code,
            "message": self.message,
            "run_id": self.run_id,
            "phase_id": self.phase_id,
            "source_id": self.source_id,
            "extra": dict(self.extra),
        }
