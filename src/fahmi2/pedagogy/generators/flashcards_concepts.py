"""Générateur « Flashcards concepts » : Q/R sur les idées clés par chapitre (LLM)."""

from __future__ import annotations

from typing import Any

from fahmi2.domain.enums import Language, SupportType
from fahmi2.domain.supports import Flashcard
from fahmi2.pedagogy.chapters import Chapter
from fahmi2.pedagogy.generators._base import (
    _PerChapterLlmGenerator,
    require_list,
    require_mapping,
    require_str,
)

_TEMPLATE_NAME = "pedagogy_flashcards_concepts"
_HEADING = "Flashcards — Concepts"
_CARD_SEPARATOR = "\n---\n\n"


class FlashcardsConceptsGenerator(_PerChapterLlmGenerator[Flashcard]):
    """Produit des cartes recto/verso sur les idées clés de chaque chapitre."""

    @property
    def support_type(self) -> SupportType:
        """Type de support."""
        return SupportType.FLASHCARDS_CONCEPTS

    @property
    def _template_name(self) -> str:
        """Template de prompt."""
        return _TEMPLATE_NAME

    def _parse_items(
        self, payload: Any, *, chapter: Chapter  # noqa: ANN401
    ) -> tuple[Flashcard, ...]:
        """Parse ``{"cards": [{"front","back"}]}`` en flashcards.

        Args:
            payload: Réponse JSON décodée.
            chapter: Chapitre courant.

        Returns:
            Les flashcards du chapitre.
        """
        label = f"{self.support_type.value}:{chapter.index}"
        mapping = require_mapping(payload, context_label=label)
        cards: list[Flashcard] = []
        for raw in require_list(mapping, "cards", context_label=label):
            card = require_mapping(raw, context_label=label)
            cards.append(
                Flashcard(
                    front=require_str(card, "front", context_label=label),
                    back=require_str(card, "back", context_label=label),
                    source_ref=chapter.anchor,
                    tags=(self.support_type.value, chapter.anchor),
                )
            )
        return tuple(cards)

    def _render_content(
        self, items: tuple[Flashcard, ...], *, language: Language
    ) -> str:
        """Rend le paquet de cartes en Markdown.

        Args:
            items: Cartes générées.
            language: Langue (titre).

        Returns:
            Le Markdown rendu.
        """
        header = f"# {_HEADING} ({language.value})\n"
        if not items:
            return f"{header}\n_Aucune carte générée._\n"
        blocks = [f"### {card.front}\n\n{card.back}\n" for card in items]
        return header + "\n" + _CARD_SEPARATOR.join(blocks)
