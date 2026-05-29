"""Abstraction LogSink + redaction globale des secrets.

Tout sink concret hérite de ``LogSink``, applique un filtrage par sévérité
minimale puis une passe de redaction des secrets enregistrés via
``register_secret`` avant de déléguer l'écriture effective à ``_write``.
"""

from __future__ import annotations

import threading
from abc import ABC, abstractmethod
from dataclasses import replace
from typing import Any

from fahmi2.core.errors.severity import Severity
from fahmi2.core.logging.event import LogEvent

_REDACTION_PLACEHOLDER = "***"
#: Longueur minimale d'une valeur **avant** son enregistrement pour redaction.
#: Évite de remplacer des fragments anodins (ex. ``"a"`` qui matcherait toute la
#: prose). Constante publique partagée avec ``SecretsService`` qui s'en sert pour
#: pré-filtrer les valeurs chargées depuis le store DPAPI.
MIN_SECRET_LENGTH = 4

_secret_lock = threading.Lock()
_secrets: set[str] = set()


def register_secret(value: str) -> None:
    """Enregistre une valeur sensible à masquer dans tous les logs futurs.

    Args:
        value: Valeur secrète (clé API, token, etc.).

    Raises:
        ValueError: Si la valeur fait moins de ``MIN_SECRET_LENGTH`` caractères
            (pour éviter de matcher des fragments anodins).
    """
    if not value or len(value) < MIN_SECRET_LENGTH:
        raise ValueError(
            f"Secret value must be at least {MIN_SECRET_LENGTH} characters"
        )
    with _secret_lock:
        _secrets.add(value)


def unregister_secret(value: str) -> None:
    """Désenregistre une valeur (utile pour les tests).

    Args:
        value: Valeur précédemment enregistrée.
    """
    with _secret_lock:
        _secrets.discard(value)


class SecretRedactor:
    """Remplace toutes les occurrences des secrets enregistrés par ``***``."""

    def redact(self, text: str) -> str:
        """Remplace dans une chaîne tous les secrets enregistrés.

        Args:
            text: Chaîne à nettoyer.

        Returns:
            Chaîne avec les secrets remplacés par ``***``.
        """
        with _secret_lock:
            secrets = tuple(_secrets)
        for secret in secrets:
            text = text.replace(secret, _REDACTION_PLACEHOLDER)
        return text

    def redact_value(self, value: Any) -> Any:  # noqa: ANN401 — JSON-like récursif
        """Applique la redaction récursivement sur une structure JSON-like.

        Args:
            value: Valeur potentiellement composite (str, dict, list, …).

        Returns:
            La même structure avec les secrets remplacés.
        """
        if isinstance(value, str):
            return self.redact(value)
        if isinstance(value, dict):
            return {k: self.redact_value(v) for k, v in value.items()}
        if isinstance(value, list):
            return [self.redact_value(v) for v in value]
        return value


class MinSeverityFilter:
    """Garde uniquement les événements de sévérité supérieure ou égale au seuil."""

    def __init__(self, min_severity: Severity) -> None:
        self.min_severity = min_severity

    def allow(self, event: LogEvent) -> bool:
        """Indique si l'événement doit être émis.

        Args:
            event: Événement de log candidat.

        Returns:
            ``True`` si ``event.severity >= min_severity``.
        """
        return event.severity >= self.min_severity


class LogSink(ABC):
    """Abstraction d'un sink de logs.

    Les sous-classes implémentent ``_write`` pour persister/afficher l'événement.
    ``emit`` est le point d'entrée standard : filtrage par sévérité puis redaction
    des secrets, avant délégation à ``_write``.
    """

    def __init__(self, *, min_severity: Severity = Severity.INFO) -> None:
        """Initialise le sink avec un seuil minimal de sévérité.

        Args:
            min_severity: Sévérité plancher acceptée.
        """
        self._filter = MinSeverityFilter(min_severity)
        self._redactor = SecretRedactor()

    def emit(self, event: LogEvent) -> None:
        """Filtre, redacte et délègue à ``_write``.

        Args:
            event: Événement à émettre.
        """
        if not self._filter.allow(event):
            return
        redacted = replace(
            event,
            message=self._redactor.redact(event.message),
            extra=self._redactor.redact_value(event.extra),
        )
        self._write(redacted)

    @abstractmethod
    def _write(self, event: LogEvent) -> None:
        """Méthode à implémenter par les sous-classes pour persister/afficher.

        Args:
            event: Événement déjà filtré et nettoyé.
        """
