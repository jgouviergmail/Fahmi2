"""Tarifs des modèles vision (USD par million de tokens) + estimation par slide.

Grille **extensible** : ajouter un modèle = une entrée par dict. Un modèle
inconnu retombe sur le tarif par défaut (celui de ``gpt-5-mini``) plutôt que
de lever — un nouveau modèle non encore tarifé ne casse pas le calcul.
Tarifs vérifiés en 2026-07 (https://developers.openai.com/api/docs/pricing).
"""

from __future__ import annotations

_TOKENS_PER_MILLION = 1_000_000

#: USD / million de tokens d'entrée, par identifiant de modèle vision.
_USD_PER_MILLION_INPUT_TOKENS: dict[str, float] = {
    "gpt-5-mini": 0.25,
    "gpt-5-nano": 0.05,
    "gpt-5.4-mini": 0.75,
}
#: USD / million de tokens de sortie, par identifiant de modèle vision.
_USD_PER_MILLION_OUTPUT_TOKENS: dict[str, float] = {
    "gpt-5-mini": 2.00,
    "gpt-5-nano": 0.40,
    "gpt-5.4-mini": 4.50,
}
_DEFAULT_USD_PER_MILLION_INPUT = 0.25
_DEFAULT_USD_PER_MILLION_OUTPUT = 2.00

#: Tokens d'entrée estimés par slide (image ~1280 px encodée en patches +
#: prompt d'analyse) — pour l'estimation pré-run.
ESTIMATED_INPUT_TOKENS_PER_SLIDE = 1_800
#: Tokens de sortie estimés par slide (texte transcrit + description).
ESTIMATED_OUTPUT_TOKENS_PER_SLIDE = 350


def vision_cost_usd(*, model: str, input_tokens: int, output_tokens: int) -> float:
    """Calcule le coût USD d'un appel vision.

    Args:
        model: Identifiant du modèle vision.
        input_tokens: Tokens d'entrée facturés (champ ``usage`` de l'API).
        output_tokens: Tokens de sortie facturés.

    Returns:
        Le coût en USD (0 si aucun token).
    """
    rate_in = _USD_PER_MILLION_INPUT_TOKENS.get(model, _DEFAULT_USD_PER_MILLION_INPUT)
    rate_out = _USD_PER_MILLION_OUTPUT_TOKENS.get(
        model, _DEFAULT_USD_PER_MILLION_OUTPUT
    )
    return (
        max(0, input_tokens) / _TOKENS_PER_MILLION * rate_in
        + max(0, output_tokens) / _TOKENS_PER_MILLION * rate_out
    )


def estimated_cost_per_slide_usd(model: str) -> float:
    """Coût estimé d'une slide (estimation pré-run du ``CostEstimator``).

    Args:
        model: Identifiant du modèle vision.

    Returns:
        Le coût USD estimé d'un appel vision sur une slide typique.
    """
    return vision_cost_usd(
        model=model,
        input_tokens=ESTIMATED_INPUT_TOKENS_PER_SLIDE,
        output_tokens=ESTIMATED_OUTPUT_TOKENS_PER_SLIDE,
    )
