"""Hiérarchie d'exceptions Fahmi2.

Chaque exception porte un *code stable* (ex: ``LLM.RATE_LIMIT``), un *user_message*
en français destiné à l'UI, une *severity*, et des *technical_details* riches
réservés aux logs.
"""

from __future__ import annotations

from typing import Any

from fahmi2.core.errors.severity import Severity


class Fahmi2Error(Exception):
    """Base de toutes les exceptions levées par l'application.

    Attributes:
        code: Identifiant stable de l'erreur (ex: ``LLM.RATE_LIMIT``).
        user_message: Message en français destiné à l'utilisateur final.
        severity: Niveau de gravité.
        technical_details: Métadonnées additionnelles (logs uniquement).
    """

    def __init__(
        self,
        *,
        code: str,
        user_message: str,
        severity: Severity,
        technical_details: dict[str, Any] | None = None,
    ) -> None:
        """Construit une exception Fahmi2.

        Args:
            code: Code stable de l'erreur.
            user_message: Message destiné à l'UI.
            severity: Niveau de gravité.
            technical_details: Métadonnées additionnelles pour les logs.
        """
        super().__init__(f"[{code}] {user_message}")
        self.code = code
        self.user_message = user_message
        self.severity = severity
        self.technical_details: dict[str, Any] = dict(technical_details or {})


class TransientError(Fahmi2Error):
    """Erreur transitoire — éligible à un retry par la RetryPolicy."""


class PermanentError(Fahmi2Error):
    """Erreur permanente — pas de retry, remontée immédiate."""


class BudgetExceededError(Fahmi2Error):
    """Plafond de coût atteint pendant un run — déclenche une pause propre."""


class PausedError(Fahmi2Error):
    """Levée pour signaler une pause utilisateur volontaire."""


class STTError(Fahmi2Error):
    """Erreur du sous-système speech-to-text."""


class LLMError(Fahmi2Error):
    """Erreur du sous-système LLM."""


class FFmpegError(Fahmi2Error):
    """Erreur d'extraction audio via ffmpeg."""


class IngestionError(Fahmi2Error):
    """Erreur survenue pendant l'ingestion d'une source (phase 0)."""


class StorageError(Fahmi2Error):
    """Erreur de stockage (SQLite, FS, secrets)."""


class ConfigError(Fahmi2Error):
    """Configuration invalide ou incohérente."""
