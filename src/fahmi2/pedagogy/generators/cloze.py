"""Générateur « Texte à trous » (cloze) : phrases lacunaires + réponses (LLM)."""

from __future__ import annotations

from typing import Any

from fahmi2.domain.enums import Language, SupportType
from fahmi2.domain.supports import ClozeItem
from fahmi2.pedagogy.chapters import Chapter
from fahmi2.pedagogy.generators._base import (
    _EvaluativePerChapterLlmGenerator,
    require_list,
    require_mapping,
    require_str,
    require_str_list,
    schema_error,
)

_TEMPLATE_NAME = "pedagogy_cloze"
_HEADING = "Textes à trous"
_ANSWERS_PREFIX = "Réponses"
_ANSWER_SEPARATOR = ", "


class ClozeGenerator(_EvaluativePerChapterLlmGenerator[ClozeItem]):
    """Produit des phrases à trous par chapitre."""

    @property
    def support_type(self) -> SupportType:
        """Type de support."""
        return SupportType.CLOZE

    @property
    def _template_name(self) -> str:
        """Template de prompt."""
        return _TEMPLATE_NAME

    def _parse_items(
        self, payload: Any, *, chapter: Chapter  # noqa: ANN401
    ) -> tuple[ClozeItem, ...]:
        """Parse ``{"items": [{"text","answers":[...]}]}``.

        Args:
            payload: Réponse JSON décodée.
            chapter: Chapitre courant.

        Returns:
            Les ``ClozeItem``.
        """
        label = f"{self.support_type.value}:{chapter.index}"
        mapping = require_mapping(payload, context_label=label)
        items: list[ClozeItem] = []
        for raw in require_list(mapping, "items", context_label=label):
            entry = require_mapping(raw, context_label=label)
            try:
                items.append(
                    ClozeItem(
                        text=require_str(entry, "text", context_label=label),
                        answers=require_str_list(
                            entry, "answers", context_label=label
                        ),
                        source_ref=chapter.anchor,
                    )
                )
            except ValueError as exc:
                raise schema_error(label, str(exc)) from exc
        return tuple(items)

    def _render_content(
        self, items: tuple[ClozeItem, ...], *, language: Language
    ) -> str:
        """Rendu combiné (texte + réponses)."""
        parts = [f"# {_HEADING} ({language.value})", ""]
        for number, item in enumerate(items, start=1):
            parts.append(f"{number}. {item.text}")
            parts.append(
                f"   *{_ANSWERS_PREFIX} : {_ANSWER_SEPARATOR.join(item.answers)}*"
            )
            parts.append("")
        return "\n".join(parts).rstrip() + "\n"

    def _render_subject(
        self, items: tuple[ClozeItem, ...], *, language: Language
    ) -> str:
        """Rendu sujet (textes lacunaires seuls)."""
        parts = [f"# {_HEADING} ({language.value})", ""]
        for number, item in enumerate(items, start=1):
            parts.append(f"{number}. {item.text}")
        parts.append("")
        return "\n".join(parts).rstrip() + "\n"

    def _render_correction(
        self, items: tuple[ClozeItem, ...], *, language: Language
    ) -> str:
        """Rendu corrigé (réponses des trous)."""
        parts = [f"# {_HEADING} — Corrigé ({language.value})", ""]
        for number, item in enumerate(items, start=1):
            parts.append(f"{number}. {_ANSWER_SEPARATOR.join(item.answers)}")
        parts.append("")
        return "\n".join(parts).rstrip() + "\n"
