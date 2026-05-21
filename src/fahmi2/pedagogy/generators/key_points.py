"""Générateur « Points clés » : 3–5 idées clés par chapitre (LLM)."""

from __future__ import annotations

from typing import Any

from fahmi2.domain.enums import Language, SupportType
from fahmi2.domain.supports import KeyPoints
from fahmi2.pedagogy.chapters import Chapter
from fahmi2.pedagogy.generators._base import (
    _PerChapterLlmGenerator,
    require_mapping,
    require_str_list,
)

_TEMPLATE_NAME = "pedagogy_key_points"
_HEADING = "Points clés"


class KeyPointsGenerator(_PerChapterLlmGenerator[KeyPoints]):
    """Produit un bloc de points clés par chapitre."""

    @property
    def support_type(self) -> SupportType:
        """Type de support."""
        return SupportType.KEY_POINTS

    @property
    def _template_name(self) -> str:
        """Template de prompt."""
        return _TEMPLATE_NAME

    def _parse_items(
        self, payload: Any, *, chapter: Chapter  # noqa: ANN401
    ) -> tuple[KeyPoints, ...]:
        """Parse ``{"points": [...]}`` en un ``KeyPoints``.

        Args:
            payload: Réponse JSON décodée.
            chapter: Chapitre courant.

        Returns:
            Un unique ``KeyPoints`` pour le chapitre.
        """
        label = f"{self.support_type.value}:{chapter.index}"
        mapping = require_mapping(payload, context_label=label)
        points = require_str_list(mapping, "points", context_label=label)
        return (
            KeyPoints(
                chapter_title=chapter.title, points=points, source_ref=chapter.anchor
            ),
        )

    def _render_content(
        self, items: tuple[KeyPoints, ...], *, language: Language
    ) -> str:
        """Rend les points clés groupés par chapitre.

        Args:
            items: Points clés par chapitre.
            language: Langue (titre).

        Returns:
            Le Markdown rendu.
        """
        parts = [f"# {_HEADING} ({language.value})", ""]
        for item in items:
            parts.append(f"## {item.chapter_title}")
            parts.append("")
            parts.extend(f"- {point}" for point in item.points)
            parts.append("")
        return "\n".join(parts).rstrip() + "\n"
