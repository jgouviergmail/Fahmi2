"""Libellés UI de la fonctionnalité Visualisations (livrables, diagrammes, statuts).

Tables de présentation propres à l'UI (le domaine n'a pas à connaître les libellés
affichés). Partagées par le dialogue de réglages et la vue de progression.

i18n : les libellés sont exposés par des **fonctions** retournant des valeurs traduites
à l'usage (pattern Qt ``QCoreApplication.translate`` avec sources marquées par
``QT_TRANSLATE_NOOP`` pour extraction par ``pyside6-lupdate``).
"""

from __future__ import annotations

from enum import StrEnum
from typing import cast

from PySide6.QtCore import QT_TRANSLATE_NOOP, QCoreApplication

from fahmi2.domain.enums import DiagramType, PhaseStatus


class VisualsDeliverable(StrEnum):
    """Livrable HTML autonome produit par la fonctionnalité Visualisations.

    Correspond aux deux drapeaux de ``VisualsSettings`` (``produce_knowledge_map`` /
    ``produce_diagrams``) ; sert de **ligne** de la matrice de progression.
    """

    KNOWLEDGE_MAP = "knowledge_map"
    DIAGRAMS = "diagrams"


_DELIVERABLE_SOURCES: dict[VisualsDeliverable, str] = {
    VisualsDeliverable.KNOWLEDGE_MAP: cast(
        str, QT_TRANSLATE_NOOP("VisualsLabels", "Carte des connaissances")
    ),
    VisualsDeliverable.DIAGRAMS: cast(
        str, QT_TRANSLATE_NOOP("VisualsLabels", "Diagrammes")
    ),
}

_DIAGRAM_TYPE_SOURCES: dict[DiagramType, str] = {
    DiagramType.FLOWCHART: cast(
        str, QT_TRANSLATE_NOOP("VisualsLabels", "Organigramme")
    ),
    DiagramType.TIMELINE: cast(
        str, QT_TRANSLATE_NOOP("VisualsLabels", "Chronologie")
    ),
    DiagramType.COMPARISON: cast(
        str, QT_TRANSLATE_NOOP("VisualsLabels", "Comparaison")
    ),
    DiagramType.HIERARCHY: cast(
        str, QT_TRANSLATE_NOOP("VisualsLabels", "Hiérarchie")
    ),
    DiagramType.CYCLE: cast(str, QT_TRANSLATE_NOOP("VisualsLabels", "Cycle")),
    DiagramType.DECISION_TREE: cast(
        str, QT_TRANSLATE_NOOP("VisualsLabels", "Arbre de décision")
    ),
}

_STATUS_SOURCES: dict[PhaseStatus, str] = {
    PhaseStatus.PENDING: cast(
        str, QT_TRANSLATE_NOOP("VisualsLabels", "En attente")
    ),
    PhaseStatus.RUNNING: cast(str, QT_TRANSLATE_NOOP("VisualsLabels", "En cours")),
    PhaseStatus.SUCCEEDED: cast(str, QT_TRANSLATE_NOOP("VisualsLabels", "Généré")),
    PhaseStatus.SKIPPED: cast(str, QT_TRANSLATE_NOOP("VisualsLabels", "À jour")),
    PhaseStatus.FAILED: cast(str, QT_TRANSLATE_NOOP("VisualsLabels", "Échec")),
}


def _tr(source: str) -> str:
    """Traduit ``source`` dans la langue active via le contexte ``VisualsLabels``."""
    return QCoreApplication.translate("VisualsLabels", source)


def deliverable_label(deliverable: VisualsDeliverable) -> str:
    """Libellé d'affichage traduit d'un livrable.

    Args:
        deliverable: Livrable.

    Returns:
        Le libellé traduit.
    """
    return _tr(_DELIVERABLE_SOURCES[deliverable])


def deliverable_labels() -> dict[VisualsDeliverable, str]:
    """Libellés traduits de tous les livrables."""
    return {kind: _tr(source) for kind, source in _DELIVERABLE_SOURCES.items()}


def diagram_type_label(diagram_type: DiagramType) -> str:
    """Libellé d'affichage traduit d'un type de diagramme.

    Args:
        diagram_type: Type de diagramme.

    Returns:
        Le libellé traduit.
    """
    return _tr(_DIAGRAM_TYPE_SOURCES[diagram_type])


def diagram_type_labels() -> dict[DiagramType, str]:
    """Libellés traduits de tous les types de diagramme."""
    return {kind: _tr(source) for kind, source in _DIAGRAM_TYPE_SOURCES.items()}


def status_label(status: PhaseStatus | None) -> str:
    """Libellé d'affichage traduit d'un statut (``None`` = en attente).

    Args:
        status: Statut, ou ``None``.

    Returns:
        Le libellé traduit.
    """
    if status is None:
        return _tr(_STATUS_SOURCES[PhaseStatus.PENDING])
    return _tr(_STATUS_SOURCES[status])
