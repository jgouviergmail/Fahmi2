"""Générateur « Vrai/Faux » : affirmations justifiées (LLM)."""

from __future__ import annotations

from typing import Any

from fahmi2.core.corpus import Chapter
from fahmi2.domain.enums import Language, SupportType
from fahmi2.domain.supports import TrueFalseItem
from fahmi2.pedagogy.generators._base import (
    _EvaluativePerChapterLlmGenerator,
    require_bool,
    require_list,
    require_mapping,
    require_str,
)

_TEMPLATE_NAME = "pedagogy_true_false"
_HEADING = "Vrai / Faux"
_TRUE_LABEL = "Vrai"
_FALSE_LABEL = "Faux"
_PROMPT_SUFFIX = "(Vrai / Faux ?)"


def _label(is_true: bool) -> str:
    """Libellé de réponse pour un booléen."""
    return _TRUE_LABEL if is_true else _FALSE_LABEL


class TrueFalseGenerator(_EvaluativePerChapterLlmGenerator[TrueFalseItem]):
    """Produit des affirmations vrai/faux justifiées par chapitre."""

    @property
    def support_type(self) -> SupportType:
        """Type de support."""
        return SupportType.TRUE_FALSE

    @property
    def _template_name(self) -> str:
        """Template de prompt."""
        return _TEMPLATE_NAME

    def _parse_items(
        self, payload: Any, *, chapter: Chapter  # noqa: ANN401
    ) -> tuple[TrueFalseItem, ...]:
        """Parse ``{"items": [{"statement","is_true","justification"}]}``.

        Args:
            payload: Réponse JSON décodée.
            chapter: Chapitre courant.

        Returns:
            Les ``TrueFalseItem``.
        """
        label = f"{self.support_type.value}:{chapter.index}"
        mapping = require_mapping(payload, context_label=label)
        items: list[TrueFalseItem] = []
        for raw in require_list(mapping, "items", context_label=label):
            entry = require_mapping(raw, context_label=label)
            items.append(
                TrueFalseItem(
                    statement=require_str(entry, "statement", context_label=label),
                    is_true=require_bool(entry, "is_true", context_label=label),
                    justification=require_str(
                        entry, "justification", context_label=label
                    ),
                    source_ref=chapter.anchor,
                )
            )
        return tuple(items)

    def _render_content(
        self, items: tuple[TrueFalseItem, ...], *, language: Language
    ) -> str:
        """Rendu combiné (affirmation + réponse + justification)."""
        parts = [f"# {_HEADING} ({language.value})", ""]
        for number, item in enumerate(items, start=1):
            parts.append(f"{number}. {item.statement}")
            parts.append(
                f"   **Réponse : {_label(item.is_true)}** — {item.justification}"
            )
            parts.append("")
        return "\n".join(parts).rstrip() + "\n"

    def _render_subject(
        self, items: tuple[TrueFalseItem, ...], *, language: Language
    ) -> str:
        """Rendu sujet (affirmations seules)."""
        parts = [f"# {_HEADING} ({language.value})", ""]
        for number, item in enumerate(items, start=1):
            parts.append(f"{number}. {item.statement}  {_PROMPT_SUFFIX}")
        parts.append("")
        return "\n".join(parts).rstrip() + "\n"

    def _render_correction(
        self, items: tuple[TrueFalseItem, ...], *, language: Language
    ) -> str:
        """Rendu corrigé (réponse + justification)."""
        parts = [f"# {_HEADING} — Corrigé ({language.value})", ""]
        for number, item in enumerate(items, start=1):
            parts.append(
                f"{number}. **{_label(item.is_true)}** — {item.justification}"
            )
        parts.append("")
        return "\n".join(parts).rstrip() + "\n"
