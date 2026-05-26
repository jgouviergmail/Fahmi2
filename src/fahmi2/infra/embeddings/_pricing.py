"""Tarifs des modèles d'embedding (USD par million de tokens).

Grille **extensible** : ajouter un modèle = une entrée dans
``_USD_PER_MILLION_TOKENS``. Un modèle inconnu retombe sur ``_DEFAULT_USD_PER_MILLION``
(plutôt que de lever), pour qu'un nouveau modèle non encore tarifé ne casse pas le
calcul de coût — le coût d'embedding restant de toute façon marginal.
"""

from __future__ import annotations

_TOKENS_PER_MILLION = 1_000_000

#: USD / million de tokens, par identifiant de modèle d'embedding.
_USD_PER_MILLION_TOKENS: dict[str, float] = {
    "text-embedding-3-small": 0.02,
    "text-embedding-3-large": 0.13,
    "text-embedding-ada-002": 0.10,
}
_DEFAULT_USD_PER_MILLION = 0.02


def embedding_cost_usd(*, model: str, total_tokens: int) -> float:
    """Calcule le coût USD d'un appel d'embedding.

    Args:
        model: Identifiant du modèle d'embedding.
        total_tokens: Nombre total de tokens facturés (champ ``usage`` de l'API).

    Returns:
        Le coût en USD (0 si ``total_tokens`` <= 0).
    """
    if total_tokens <= 0:
        return 0.0
    rate = _USD_PER_MILLION_TOKENS.get(model, _DEFAULT_USD_PER_MILLION)
    return total_tokens / _TOKENS_PER_MILLION * rate
