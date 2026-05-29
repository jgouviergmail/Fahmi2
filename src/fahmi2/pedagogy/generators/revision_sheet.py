"""Générateur « Fiche de révision » : synthèse Markdown par chapitre (LLM)."""

from __future__ import annotations

from typing import Any

from fahmi2.core.corpus import Chapter
from fahmi2.domain.enums import Language, SupportType
from fahmi2.domain.supports import RevisionSheet
from fahmi2.pedagogy.generators._base import (
    _PerChapterLlmGenerator,
    require_mapping,
    require_str,
)

_TEMPLATE_NAME = "pedagogy_revision_sheet"
_HEADING = "Fiche de révision"


class RevisionSheetGenerator(_PerChapterLlmGenerator[RevisionSheet]):
    """Produit une synthèse de révision par chapitre."""

    @property
    def support_type(self) -> SupportType:
        """Type de support."""
        return SupportType.REVISION_SHEET

    @property
    def _template_name(self) -> str:
        """Template de prompt."""
        return _TEMPLATE_NAME

    def _parse_items(
        self, payload: Any, *, chapter: Chapter  # noqa: ANN401
    ) -> tuple[RevisionSheet, ...]:
        """Parse ``{"summary_markdown": "..."}`` en une fiche de chapitre.

        Args:
            payload: Réponse JSON décodée.
            chapter: Chapitre courant.

        Returns:
            Une unique ``RevisionSheet`` pour le chapitre.
        """
        label = f"{self.support_type.value}:{chapter.index}"
        mapping = require_mapping(payload, context_label=label)
        summary = require_str(mapping, "summary_markdown", context_label=label)
        return (
            RevisionSheet(
                chapter_title=chapter.title,
                summary_markdown=summary,
                source_ref=chapter.anchor,
            ),
        )

    def _render_content(
        self, items: tuple[RevisionSheet, ...], *, language: Language
    ) -> str:
        """Rend les fiches groupées par chapitre.

        Args:
            items: Fiches par chapitre.
            language: Langue (titre).

        Returns:
            Le Markdown rendu.
        """
        parts = [f"# {_HEADING} ({language.value})", ""]
        for item in items:
            parts.append(f"## {item.chapter_title}")
            parts.append("")
            parts.append(item.summary_markdown.strip())
            parts.append("")
        return "\n".join(parts).rstrip() + "\n"
