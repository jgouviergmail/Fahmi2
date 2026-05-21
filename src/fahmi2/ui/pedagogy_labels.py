"""Libellés UI des supports pédagogiques (noms d'affichage, formats, statuts).

Tables de présentation propres à l'UI (le domaine n'a pas à connaître les
libellés affichés). Partagées par le dialogue de réglages et la vue de
progression.
"""

from __future__ import annotations

from fahmi2.domain.enums import ExportFormat, PhaseStatus, SupportType

SUPPORT_LABELS: dict[SupportType, str] = {
    SupportType.FLASHCARDS_CONCEPTS: "Flashcards — Concepts",
    SupportType.QCM: "QCM",
    SupportType.TRUE_FALSE: "Vrai / Faux",
    SupportType.CLOZE: "Textes à trous",
    SupportType.OPEN_QUESTIONS: "Questions ouvertes",
    SupportType.REVISION_SHEET: "Fiche de révision",
    SupportType.KEY_POINTS: "Points clés",
    SupportType.MOCK_EXAM: "Examen blanc",
}

EXPORT_LABELS: dict[ExportFormat, str] = {
    ExportFormat.APKG: "Anki (.apkg)",
    ExportFormat.MARKDOWN: "Markdown",
    ExportFormat.PDF: "PDF",
}

#: Libellés FR des statuts d'un support dans la table de progression.
SUPPORT_STATUS_LABELS: dict[PhaseStatus, str] = {
    PhaseStatus.PENDING: "En attente",
    PhaseStatus.RUNNING: "En cours",
    PhaseStatus.SUCCEEDED: "Généré",
    PhaseStatus.SKIPPED: "À jour",
    PhaseStatus.FAILED: "Échec",
}

#: Libellé affiché pour une cellule non encore démarrée (statut ``None``).
SUPPORT_STATUS_WAITING = "En attente"


def support_label(support_type: SupportType) -> str:
    """Libellé d'affichage d'un type de support.

    Args:
        support_type: Type de support.

    Returns:
        Le libellé FR.
    """
    return SUPPORT_LABELS[support_type]


def status_label(status: PhaseStatus | None) -> str:
    """Libellé d'affichage d'un statut de support (``None`` = en attente).

    Args:
        status: Statut, ou ``None``.

    Returns:
        Le libellé FR.
    """
    if status is None:
        return SUPPORT_STATUS_WAITING
    return SUPPORT_STATUS_LABELS[status]
