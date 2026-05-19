"""Tarifs USD par million de tokens pour les modèles DeepSeek v4.

Source : ``https://api-docs.deepseek.com/quick_start/pricing/`` (mai 2026).
Les constantes sont centralisées ici pour faciliter les mises à jour ; elles
sont consommées par ``DeepSeekAdapter`` et le ``CostEstimator``.
"""

from __future__ import annotations

from dataclasses import dataclass

_TOKENS_PER_MILLION = 1_000_000


@dataclass(frozen=True)
class ModelPricing:
    """Tarifs en USD par million de tokens pour un modèle donné.

    Attributes:
        input_cache_hit_usd_per_million: Tarif tokens d'entrée servis depuis le
            cache.
        input_cache_miss_usd_per_million: Tarif tokens d'entrée non cachés.
        output_usd_per_million: Tarif tokens de sortie.
    """

    input_cache_hit_usd_per_million: float
    input_cache_miss_usd_per_million: float
    output_usd_per_million: float

    def cost_for(
        self,
        *,
        prompt_tokens: int,
        completion_tokens: int,
        cached_prompt_tokens: int,
    ) -> float:
        """Calcule le coût total en USD pour un appel.

        Args:
            prompt_tokens: Total des tokens d'entrée (cache hit + miss).
            completion_tokens: Tokens de sortie.
            cached_prompt_tokens: Sous-total des tokens d'entrée servis par le
                cache (doit être ``<= prompt_tokens``).

        Returns:
            Coût en USD.
        """
        miss_tokens = max(0, prompt_tokens - cached_prompt_tokens)
        return (
            cached_prompt_tokens * self.input_cache_hit_usd_per_million
            + miss_tokens * self.input_cache_miss_usd_per_million
            + completion_tokens * self.output_usd_per_million
        ) / _TOKENS_PER_MILLION


PRICING: dict[str, ModelPricing] = {
    "deepseek-v4-flash": ModelPricing(
        input_cache_hit_usd_per_million=0.0028,
        input_cache_miss_usd_per_million=0.14,
        output_usd_per_million=0.28,
    ),
    "deepseek-v4-pro": ModelPricing(
        input_cache_hit_usd_per_million=0.003625,
        input_cache_miss_usd_per_million=0.435,
        output_usd_per_million=0.87,
    ),
}


def get_pricing(model: str) -> ModelPricing:
    """Récupère la grille tarifaire pour un modèle.

    Args:
        model: Identifiant exact du modèle (ex: ``deepseek-v4-flash``).

    Returns:
        ``ModelPricing`` correspondant.

    Raises:
        KeyError: Si le modèle est inconnu.
    """
    try:
        return PRICING[model]
    except KeyError as exc:
        raise KeyError(f"Unknown model pricing: {model}") from exc
