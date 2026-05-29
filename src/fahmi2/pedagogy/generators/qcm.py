"""Générateur « QCM » : questions à choix multiples justifiées (LLM).

Inclut un **dé-biaisage déterministe** : la position de la bonne réponse est
répartie sur l'ensemble des items (rotation), pour éviter qu'elle soit toujours
en première position. La qualité fine des distracteurs relève de l'itération
produit via l'éditeur de prompts (design §12).
"""

from __future__ import annotations

import string
from typing import Any

from fahmi2.core.corpus import Chapter
from fahmi2.domain.enums import Language, SupportType
from fahmi2.domain.supports import QcmItem
from fahmi2.pedagogy.generators._base import (
    _EvaluativePerChapterLlmGenerator,
    require_int,
    require_list,
    require_mapping,
    require_str,
    require_str_list,
    schema_error,
)

_TEMPLATE_NAME = "pedagogy_qcm"
_HEADING = "QCM"
_CHOICE_LETTERS = string.ascii_uppercase
_ANSWER_PREFIX = "Réponse"


def _balance(items: tuple[QcmItem, ...]) -> tuple[QcmItem, ...]:
    """Équilibre la position de la bonne réponse sur l'ensemble des items.

    Pour l'item d'indice ``i``, la bonne proposition est déplacée à la position
    ``i % len(choices)`` (rotation déterministe).

    Args:
        items: Items QCM bruts.

    Returns:
        Les items avec positions de bonne réponse réparties.
    """
    balanced: list[QcmItem] = []
    for i, item in enumerate(items):
        target = i % len(item.choices)
        choices = list(item.choices)
        correct = choices.pop(item.correct_index)
        choices.insert(target, correct)
        balanced.append(
            QcmItem(
                question=item.question,
                choices=tuple(choices),
                correct_index=target,
                justification=item.justification,
                source_ref=item.source_ref,
            )
        )
    return tuple(balanced)


class QcmGenerator(_EvaluativePerChapterLlmGenerator[QcmItem]):
    """Produit des questions à choix multiples par chapitre."""

    @property
    def support_type(self) -> SupportType:
        """Type de support."""
        return SupportType.QCM

    @property
    def _template_name(self) -> str:
        """Template de prompt."""
        return _TEMPLATE_NAME

    def _parse_items(
        self, payload: Any, *, chapter: Chapter  # noqa: ANN401
    ) -> tuple[QcmItem, ...]:
        """Parse les questions puis applique le dé-biaisage.

        Args:
            payload: Réponse JSON décodée.
            chapter: Chapitre courant.

        Returns:
            Les ``QcmItem`` équilibrés.
        """
        label = f"{self.support_type.value}:{chapter.index}"
        mapping = require_mapping(payload, context_label=label)
        items: list[QcmItem] = []
        for raw in require_list(mapping, "questions", context_label=label):
            question = require_mapping(raw, context_label=label)
            try:
                items.append(
                    QcmItem(
                        question=require_str(
                            question, "question", context_label=label
                        ),
                        choices=require_str_list(
                            question, "choices", context_label=label
                        ),
                        correct_index=require_int(
                            question, "correct_index", context_label=label
                        ),
                        justification=require_str(
                            question, "justification", context_label=label
                        ),
                        source_ref=chapter.anchor,
                    )
                )
            except ValueError as exc:
                raise schema_error(label, str(exc)) from exc
        return _balance(tuple(items))

    def _render_content(
        self, items: tuple[QcmItem, ...], *, language: Language
    ) -> str:
        """Rendu combiné (questions + bonne réponse + justification)."""
        return self._render(items, language=language, with_answers=True)

    def _render_subject(
        self, items: tuple[QcmItem, ...], *, language: Language
    ) -> str:
        """Rendu sujet (questions + propositions, sans réponse)."""
        return self._render(items, language=language, with_answers=False)

    def _render_correction(
        self, items: tuple[QcmItem, ...], *, language: Language
    ) -> str:
        """Rendu corrigé (bonne réponse + justification par question)."""
        parts = [f"# {_HEADING} — Corrigé ({language.value})", ""]
        for number, item in enumerate(items, start=1):
            letter = _CHOICE_LETTERS[item.correct_index]
            parts.append(f"### {number}. {item.question}")
            parts.append(f"**{_ANSWER_PREFIX} : {letter}** — {item.justification}")
            parts.append("")
        return "\n".join(parts).rstrip() + "\n"

    def _render(
        self, items: tuple[QcmItem, ...], *, language: Language, with_answers: bool
    ) -> str:
        """Rend les questions, avec ou sans la réponse.

        Args:
            items: Questions.
            language: Langue (titre).
            with_answers: Inclut la bonne réponse + justification si ``True``.

        Returns:
            Le Markdown rendu.
        """
        parts = [f"# {_HEADING} ({language.value})", ""]
        for number, item in enumerate(items, start=1):
            parts.append(f"### {number}. {item.question}")
            parts.append("")
            for choice_index, choice in enumerate(item.choices):
                parts.append(f"- {_CHOICE_LETTERS[choice_index]}. {choice}")
            if with_answers:
                letter = _CHOICE_LETTERS[item.correct_index]
                parts.append("")
                parts.append(
                    f"**{_ANSWER_PREFIX} : {letter}** — {item.justification}"
                )
            parts.append("")
        return "\n".join(parts).rstrip() + "\n"
