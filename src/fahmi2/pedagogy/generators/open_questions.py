"""Générateur « Questions ouvertes » : énoncés + éléments de réponse (LLM)."""

from __future__ import annotations

from typing import Any

from fahmi2.domain.enums import Language, SupportType
from fahmi2.domain.supports import OpenQuestion
from fahmi2.pedagogy.chapters import Chapter
from fahmi2.pedagogy.generators._base import (
    _EvaluativePerChapterLlmGenerator,
    require_list,
    require_mapping,
    require_str,
    require_str_list,
)

_TEMPLATE_NAME = "pedagogy_open_questions"
_HEADING = "Questions ouvertes"
_EXPECTED_HEADING = "Éléments de réponse attendus"


class OpenQuestionsGenerator(_EvaluativePerChapterLlmGenerator[OpenQuestion]):
    """Produit des questions ouvertes par chapitre."""

    @property
    def support_type(self) -> SupportType:
        """Type de support."""
        return SupportType.OPEN_QUESTIONS

    @property
    def _template_name(self) -> str:
        """Template de prompt."""
        return _TEMPLATE_NAME

    def _parse_items(
        self, payload: Any, *, chapter: Chapter  # noqa: ANN401
    ) -> tuple[OpenQuestion, ...]:
        """Parse ``{"questions": [{"question","expected_points":[...]}]}``.

        Args:
            payload: Réponse JSON décodée.
            chapter: Chapitre courant.

        Returns:
            Les ``OpenQuestion``.
        """
        label = f"{self.support_type.value}:{chapter.index}"
        mapping = require_mapping(payload, context_label=label)
        items: list[OpenQuestion] = []
        for raw in require_list(mapping, "questions", context_label=label):
            entry = require_mapping(raw, context_label=label)
            items.append(
                OpenQuestion(
                    question=require_str(entry, "question", context_label=label),
                    expected_points=require_str_list(
                        entry, "expected_points", context_label=label
                    ),
                    source_ref=chapter.anchor,
                )
            )
        return tuple(items)

    def _render_content(
        self, items: tuple[OpenQuestion, ...], *, language: Language
    ) -> str:
        """Rendu combiné (question + éléments attendus)."""
        parts = [f"# {_HEADING} ({language.value})", ""]
        for number, item in enumerate(items, start=1):
            parts.append(f"### {number}. {item.question}")
            parts.append("")
            parts.append(f"*{_EXPECTED_HEADING} :*")
            parts.extend(f"- {point}" for point in item.expected_points)
            parts.append("")
        return "\n".join(parts).rstrip() + "\n"

    def _render_subject(
        self, items: tuple[OpenQuestion, ...], *, language: Language
    ) -> str:
        """Rendu sujet (questions seules)."""
        parts = [f"# {_HEADING} ({language.value})", ""]
        for number, item in enumerate(items, start=1):
            parts.append(f"### {number}. {item.question}")
            parts.append("")
        return "\n".join(parts).rstrip() + "\n"

    def _render_correction(
        self, items: tuple[OpenQuestion, ...], *, language: Language
    ) -> str:
        """Rendu corrigé (éléments de réponse attendus)."""
        parts = [f"# {_HEADING} — Corrigé ({language.value})", ""]
        for number, item in enumerate(items, start=1):
            parts.append(f"### {number}. {item.question}")
            parts.extend(f"- {point}" for point in item.expected_points)
            parts.append("")
        return "\n".join(parts).rstrip() + "\n"
