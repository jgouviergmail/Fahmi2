"""Événements de la fonctionnalité Visualisations (publiés sur un ``EventBus``).

Hiérarchie minimale : une base ``VisualsEvent`` (horodatage) et les événements
concrets émis pendant la construction (tentatives de retry LLM ; les événements de
progression seront ajoutés avec l'orchestrateur). Le bus est générique
(``EventBus[VisualsEvent]``), à l'image de la Pédagogie.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from fahmi2.core.errors.error_info import ErrorInfo
from fahmi2.domain.enums import Language, PhaseStatus, RunStatus


class VisualsStructureStep(StrEnum):
    """Étape de l'extraction de structure (phase commune, avant les langues).

    Sert à matérialiser l'avancement (logs + matrice) de la phase la plus longue,
    exécutée **une seule fois** en langue de structure.
    """

    GRAPH = "graph"
    COMMUNITY_REPORTS = "community_reports"
    IDEA_CHAINS = "idea_chains"
    DIAGRAMS = "diagrams"


@dataclass(frozen=True)
class VisualsEvent:
    """Base des événements Visualisations.

    Attributes:
        timestamp: Horodatage UTC de l'événement.
    """

    timestamp: datetime


@dataclass(frozen=True)
class VisualsGenerationStarted(VisualsEvent):
    """Début de la génération des visualisations."""


@dataclass(frozen=True)
class VisualsGenerationFinished(VisualsEvent):
    """Fin de la génération des visualisations.

    Attributes:
        status: Statut final (``COMPLETED`` / ``FAILED`` / ``CANCELLED`` / ``PAUSED``).
        total_cost_usd: Coût LLM cumulé de l'exécution.
    """

    status: RunStatus
    total_cost_usd: float


@dataclass(frozen=True)
class VisualsStructureStarted(VisualsEvent):
    """Début de l'extraction de structure (graphe + diagrammes, une seule fois)."""


@dataclass(frozen=True)
class VisualsStructureProgress(VisualsEvent):
    """Avancement d'une étape de l'extraction de structure.

    Attributes:
        step: Étape concernée (graphe / rapports / enchaînements / diagrammes).
        completed: Nombre d'items traités.
        total: Nombre total d'items de l'étape.
    """

    step: VisualsStructureStep
    completed: int
    total: int


@dataclass(frozen=True)
class VisualsStructureFinished(VisualsEvent):
    """Fin de l'extraction de structure (avant la production par langue)."""


@dataclass(frozen=True)
class VisualsLanguageStarted(VisualsEvent):
    """Début de la production des livrables d'une langue.

    Attributes:
        language: Langue concernée.
    """

    language: Language


@dataclass(frozen=True)
class VisualsLanguageFinished(VisualsEvent):
    """Fin de la production des livrables d'une langue.

    Attributes:
        language: Langue concernée.
        status: Statut (``SUCCEEDED`` / ``SKIPPED`` / ``FAILED``).
        cost_usd: Coût LLM de la localisation de cette langue.
        error: ``ErrorInfo`` si échec, sinon ``None``.
    """

    language: Language
    status: PhaseStatus
    cost_usd: float
    error: ErrorInfo | None


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
