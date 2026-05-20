"""Générateur de flashcards à partir du glossaire (sans LLM).

Recto = terme (+ acronyme entre parenthèses s'il existe), verso = définition.
Première tranche verticale (design §6) : produit un ``SupportArtifact`` JSON + MD
sans aucun appel LLM (coût 0).
"""

from __future__ import annotations

from fahmi2.domain.enums import Language, SupportType
from fahmi2.domain.glossary import Term
from fahmi2.domain.supports import Flashcard, SupportArtifact
from fahmi2.pedagogy.chapters import Chapter
from fahmi2.pedagogy.support_generator import SupportContext, SupportGenerator

_GLOSSARY_SOURCE_REF = "glossaire"
_CARD_SEPARATOR = "\n---\n\n"


class FlashcardsGlossaryGenerator(SupportGenerator):
    """Produit une carte recto/verso par terme du glossaire."""

    @property
    def support_type(self) -> SupportType:
        """Type de support produit."""
        return SupportType.FLASHCARDS_GLOSSARY

    @property
    def uses_llm(self) -> bool:
        """Générateur déterministe, sans LLM."""
        return False

    def generate(
        self,
        ctx: SupportContext,
        *,
        language: Language,
        chapters: tuple[Chapter, ...],
        glossary: tuple[Term, ...],
    ) -> SupportArtifact:
        """Génère le jeu de flashcards depuis le glossaire.

        Args:
            ctx: Contexte (inutilisé ici : pas de LLM, pas de prompt).
            language: Langue cible.
            chapters: Chapitres (inutilisés pour ce support).
            glossary: Termes du glossaire pour cette langue.

        Returns:
            Le ``SupportArtifact`` (cartes + Markdown rendu, coût 0).
        """
        del ctx, chapters
        cards = tuple(self._term_to_card(term, language) for term in glossary)
        return SupportArtifact(
            support_type=self.support_type,
            language=language,
            items=cards,
            rendered_markdown=self._render_markdown(cards, language),
            cost_usd=0.0,
        )

    def _term_to_card(self, term: Term, language: Language) -> Flashcard:
        """Construit la flashcard d'un terme.

        Args:
            term: Terme du glossaire.
            language: Langue (pour les tags).

        Returns:
            La ``Flashcard`` recto/verso.
        """
        front = f"{term.term} ({term.acronym})" if term.acronym else term.term
        return Flashcard(
            front=front,
            back=term.definition,
            source_ref=term.term or _GLOSSARY_SOURCE_REF,
            tags=(self.support_type.value, language.value),
        )

    def _render_markdown(
        self, cards: tuple[Flashcard, ...], language: Language
    ) -> str:
        """Rend le jeu de cartes en Markdown lisible.

        Args:
            cards: Cartes générées.
            language: Langue (titre).

        Returns:
            Le Markdown du paquet.
        """
        header = f"# Flashcards — Glossaire ({language.value})\n"
        if not cards:
            return f"{header}\n_Aucun terme de glossaire disponible._\n"
        blocks = [f"### {card.front}\n\n{card.back}\n" for card in cards]
        return header + "\n" + _CARD_SEPARATOR.join(blocks)
