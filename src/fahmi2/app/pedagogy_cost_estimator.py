"""Estimation pré-génération du coût des supports pédagogiques (heuristique).

Estime, par (support LLM × langue × chapitre), un coût en USD : les tokens
d'entrée sont déduits de la taille du chapitre, les tokens de sortie d'une table
par densité, et le mode thinking applique un multiplicateur (cf. ``_cost_common``).
Les flashcards glossaire (sans LLM) coûtent 0. L'examen blanc consomme tout le
document en un appel par langue. Objectif : un ordre de grandeur, pas une
prédiction au cent près.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from fahmi2.app._cost_common import (
    TOKENS_PER_WORD,
    cost_range,
    thinking_output_multiplier,
)
from fahmi2.domain.enums import Language, SupportDensity, SupportType
from fahmi2.domain.pedagogy import NO_LLM_SUPPORTS, PedagogySettings
from fahmi2.infra.llm._pricing import ModelPricing, get_pricing
from fahmi2.pedagogy.chapters import Chapter

#: Tokens de sortie estimés par chapitre, selon la densité (supports par chapitre).
_DENSITY_OUTPUT_TOKENS: dict[SupportDensity, int] = {
    SupportDensity.LIGHT: 300,
    SupportDensity.STANDARD: 600,
    SupportDensity.DENSE: 1000,
}

#: Tokens de sortie estimés pour un examen blanc (document entier), selon la densité.
_MOCK_EXAM_OUTPUT_TOKENS: dict[SupportDensity, int] = {
    SupportDensity.LIGHT: 800,
    SupportDensity.STANDARD: 1500,
    SupportDensity.DENSE: 2500,
}


@dataclass(frozen=True)
class PedagogyCostEstimation:
    """Estimation de coût des supports.

    Attributes:
        per_support_usd: Coût estimé par type de support.
        total_usd: Coût total estimé (ponctuel).
        chapters_total: Nombre total de chapitres (toutes langues confondues).
        low_usd: Bas de fourchette d'incertitude (±33 %).
        high_usd: Haut de fourchette d'incertitude (±33 %).
    """

    per_support_usd: dict[SupportType, float]
    total_usd: float
    chapters_total: int
    low_usd: float
    high_usd: float


class PedagogyCostEstimator:
    """Estime le coût LLM des supports sélectionnés (ordre de grandeur)."""

    def estimate(
        self,
        *,
        pedagogy: PedagogySettings,
        chapters_by_language: Mapping[Language, tuple[Chapter, ...]],
    ) -> PedagogyCostEstimation:
        """Estime le coût total.

        Args:
            pedagogy: Réglages pédagogie.
            chapters_by_language: Chapitres parsés par langue.

        Returns:
            ``PedagogyCostEstimation`` (coût par support + total + nb chapitres).
        """
        pricing = get_pricing(str(pedagogy.llm_model))
        thinking_mult = thinking_output_multiplier(pedagogy.llm_config)
        out_per_chapter = _DENSITY_OUTPUT_TOKENS[pedagogy.density]
        out_mock = _MOCK_EXAM_OUTPUT_TOKENS[pedagogy.density]

        per_support: dict[SupportType, float] = {}
        chapters_total = 0
        for language in pedagogy.languages:
            chapters = chapters_by_language.get(language, ())
            chapters_total += len(chapters)
            chapter_inputs = [
                int(len(chapter.body_markdown.split()) * TOKENS_PER_WORD)
                for chapter in chapters
            ]
            for support in pedagogy.selected_supports:
                cost = self._support_cost(
                    support,
                    chapter_inputs=chapter_inputs,
                    out_per_chapter=out_per_chapter,
                    out_mock=out_mock,
                    thinking_mult=thinking_mult,
                    pricing=pricing,
                )
                per_support[support] = per_support.get(support, 0.0) + cost
        total = sum(per_support.values())
        low, high = cost_range(total)
        return PedagogyCostEstimation(
            per_support_usd=per_support,
            total_usd=total,
            chapters_total=chapters_total,
            low_usd=low,
            high_usd=high,
        )

    @staticmethod
    def _support_cost(
        support: SupportType,
        *,
        chapter_inputs: list[int],
        out_per_chapter: int,
        out_mock: int,
        thinking_mult: float,
        pricing: ModelPricing,
    ) -> float:
        """Coût d'un support pour une langue.

        Args:
            support: Type de support.
            chapter_inputs: Tokens d'entrée estimés par chapitre.
            out_per_chapter: Tokens de sortie estimés par chapitre.
            out_mock: Tokens de sortie estimés pour un examen blanc.
            thinking_mult: Multiplicateur thinking sur les tokens de sortie.
            pricing: Grille tarifaire du modèle.

        Returns:
            Coût USD pour ce support sur cette langue.
        """
        if support in NO_LLM_SUPPORTS:
            return 0.0
        if support is SupportType.MOCK_EXAM:
            return pricing.cost_for(
                prompt_tokens=sum(chapter_inputs),
                completion_tokens=int(out_mock * thinking_mult),
                cached_prompt_tokens=0,
            )
        return sum(
            pricing.cost_for(
                prompt_tokens=chapter_input,
                completion_tokens=int(out_per_chapter * thinking_mult),
                cached_prompt_tokens=0,
            )
            for chapter_input in chapter_inputs
        )
