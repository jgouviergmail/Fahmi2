"""Événements de la fonctionnalité Visualisations (publiés sur un ``EventBus``).

Hiérarchie minimale : une base ``VisualsEvent`` (horodatage) et les événements
concrets émis pendant la construction (tentatives de retry LLM ; les événements de
progression seront ajoutés avec l'orchestrateur). Le bus est générique
(``EventBus[VisualsEvent]``), à l'image de la Pédagogie.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from fahmi2.core.errors.error_info import ErrorInfo
from fahmi2.domain.enums import Language


@dataclass(frozen=True)
class VisualsEvent:
    """Base des événements Visualisations.

    Attributes:
        timestamp: Horodatage UTC de l'événement.
    """

    timestamp: datetime


@dataclass(frozen=True)
class VisualsRetryAttempt(VisualsEvent):
    """Nouvelle tentative d'un appel LLM après une erreur retryable.

    Attributes:
        stage: Étape du pipeline (ex. ``"graph_extraction"``).
        language: Langue concernée par l'appel.
        attempt: Numéro de la tentative (1 = première).
        delay_seconds: Délai (s) avant la prochaine tentative.
        error: Erreur typée ayant déclenché la nouvelle tentative.
    """

    stage: str
    language: Language
    attempt: int
    delay_seconds: float
    error: ErrorInfo
