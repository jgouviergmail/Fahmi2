"""Libellés UI des supports pédagogiques (noms d'affichage, formats, statuts).

Tables de présentation propres à l'UI (le domaine n'a pas à connaître les
libellés affichés). Partagées par le dialogue de réglages et la vue de
progression.

i18n : les libellés sont exposés par des **fonctions** retournant des dicts
traduits à l'usage (pattern Qt ``QCoreApplication.translate`` avec sources
marquées par ``QT_TRANSLATE_NOOP`` pour extraction par ``pyside6-lupdate``).
"""

from __future__ import annotations

from typing import cast

from PySide6.QtCore import QT_TRANSLATE_NOOP, QCoreApplication

from fahmi2.domain.enums import (
    BloomObjective,
    ExportFormat,
    PhaseStatus,
    SupportDensity,
    SupportType,
    TargetAudience,
)

_SUPPORT_SOURCES: dict[SupportType, str] = {
    SupportType.FLASHCARDS_CONCEPTS: cast(
        str, QT_TRANSLATE_NOOP("PedagogyLabels", "Flashcards — Concepts")
    ),
    SupportType.QCM: cast(str, QT_TRANSLATE_NOOP("PedagogyLabels", "QCM")),
    SupportType.TRUE_FALSE: cast(
        str, QT_TRANSLATE_NOOP("PedagogyLabels", "Vrai / Faux")
    ),
    SupportType.CLOZE: cast(
        str, QT_TRANSLATE_NOOP("PedagogyLabels", "Textes à trous")
    ),
    SupportType.OPEN_QUESTIONS: cast(
        str, QT_TRANSLATE_NOOP("PedagogyLabels", "Questions ouvertes")
    ),
    SupportType.REVISION_SHEET: cast(
        str, QT_TRANSLATE_NOOP("PedagogyLabels", "Fiche de révision")
    ),
    SupportType.KEY_POINTS: cast(
        str, QT_TRANSLATE_NOOP("PedagogyLabels", "Points clés")
    ),
    SupportType.MOCK_EXAM: cast(
        str, QT_TRANSLATE_NOOP("PedagogyLabels", "Examen blanc")
    ),
}

_EXPORT_SOURCES: dict[ExportFormat, str] = {
    ExportFormat.APKG: cast(str, QT_TRANSLATE_NOOP("PedagogyLabels", "Anki (.apkg)")),
    ExportFormat.MARKDOWN: cast(str, QT_TRANSLATE_NOOP("PedagogyLabels", "Markdown")),
    ExportFormat.PDF: cast(str, QT_TRANSLATE_NOOP("PedagogyLabels", "PDF")),
    ExportFormat.HTML: cast(str, QT_TRANSLATE_NOOP("PedagogyLabels", "HTML")),
    ExportFormat.DOCX: cast(str, QT_TRANSLATE_NOOP("PedagogyLabels", "Word (.docx)")),
}

_AUDIENCE_SOURCES: dict[TargetAudience, str] = {
    TargetAudience.DISCOVERY: cast(
        str, QT_TRANSLATE_NOOP("PedagogyLabels", "grand public (découverte)")
    ),
    TargetAudience.HIGH_SCHOOL: cast(
        str, QT_TRANSLATE_NOOP("PedagogyLabels", "lycée")
    ),
    TargetAudience.LICENCE: cast(
        str,
        QT_TRANSLATE_NOOP(
            "PedagogyLabels", "licence (premier cycle universitaire)"
        ),
    ),
    TargetAudience.MASTER_EXPERT: cast(
        str, QT_TRANSLATE_NOOP("PedagogyLabels", "master / expert")
    ),
}

_BLOOM_SOURCES: dict[BloomObjective, str] = {
    BloomObjective.AUTO: cast(
        str,
        QT_TRANSLATE_NOOP("PedagogyLabels", "automatique (adapté au public cible)"),
    ),
    BloomObjective.RESTITUTE: cast(
        str,
        QT_TRANSLATE_NOOP("PedagogyLabels", "restituer (mémorisation, définitions)"),
    ),
    BloomObjective.UNDERSTAND_APPLY: cast(
        str, QT_TRANSLATE_NOOP("PedagogyLabels", "comprendre et appliquer")
    ),
    BloomObjective.ANALYZE_BEYOND: cast(
        str,
        QT_TRANSLATE_NOOP(
            "PedagogyLabels", "analyser et au-delà (synthèse, évaluation)"
        ),
    ),
}

_DENSITY_SOURCES: dict[SupportDensity, str] = {
    SupportDensity.LIGHT: cast(str, QT_TRANSLATE_NOOP("PedagogyLabels", "légère")),
    SupportDensity.STANDARD: cast(
        str, QT_TRANSLATE_NOOP("PedagogyLabels", "standard")
    ),
    SupportDensity.DENSE: cast(str, QT_TRANSLATE_NOOP("PedagogyLabels", "dense")),
}

_SUPPORT_STATUS_SOURCES: dict[PhaseStatus, str] = {
    PhaseStatus.PENDING: cast(
        str, QT_TRANSLATE_NOOP("PedagogyLabels", "En attente")
    ),
    PhaseStatus.RUNNING: cast(
        str, QT_TRANSLATE_NOOP("PedagogyLabels", "En cours")
    ),
    PhaseStatus.SUCCEEDED: cast(
        str, QT_TRANSLATE_NOOP("PedagogyLabels", "Généré")
    ),
    PhaseStatus.SKIPPED: cast(
        str, QT_TRANSLATE_NOOP("PedagogyLabels", "À jour")
    ),
    PhaseStatus.FAILED: cast(str, QT_TRANSLATE_NOOP("PedagogyLabels", "Échec")),
}


def _tr(source: str) -> str:
    """Traduit ``source`` dans la langue active via le contexte ``PedagogyLabels``."""
    return QCoreApplication.translate("PedagogyLabels", source)


def support_labels() -> dict[SupportType, str]:
    """Libellés traduits des types de support."""
    return {kind: _tr(source) for kind, source in _SUPPORT_SOURCES.items()}


def export_labels() -> dict[ExportFormat, str]:
    """Libellés traduits des formats d'export."""
    return {fmt: _tr(source) for fmt, source in _EXPORT_SOURCES.items()}


def support_status_labels() -> dict[PhaseStatus, str]:
    """Libellés traduits des statuts de support."""
    return {status: _tr(source) for status, source in _SUPPORT_STATUS_SOURCES.items()}


def support_label(support_type: SupportType) -> str:
    """Libellé d'affichage traduit d'un type de support."""
    return _tr(_SUPPORT_SOURCES[support_type])


def status_label(status: PhaseStatus | None) -> str:
    """Libellé d'affichage traduit d'un statut (``None`` = en attente)."""
    if status is None:
        return _tr(_SUPPORT_STATUS_SOURCES[PhaseStatus.PENDING])
    return _tr(_SUPPORT_STATUS_SOURCES[status])


def audience_display_label(audience: TargetAudience) -> str:
    """Libellé UI traduit d'un public cible (≠ libellé prompt en FR figé)."""
    return _tr(_AUDIENCE_SOURCES[audience])


def bloom_display_label(bloom: BloomObjective) -> str:
    """Libellé UI traduit d'un objectif Bloom (≠ libellé prompt en FR figé)."""
    return _tr(_BLOOM_SOURCES[bloom])


def density_display_label(density: SupportDensity) -> str:
    """Libellé UI traduit d'une densité (≠ libellé prompt en FR figé)."""
    return _tr(_DENSITY_SOURCES[density])
