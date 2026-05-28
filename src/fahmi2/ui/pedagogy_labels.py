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

from fahmi2.domain.enums import ExportFormat, PhaseStatus, SupportType

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
