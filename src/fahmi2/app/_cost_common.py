"""Heuristiques de coût partagées (génération + pédagogie).

Constantes de conversion oral → tokens et multiplicateur de tokens de sortie
quand le mode raisonnement (« thinking ») est actif. Les tokens de raisonnement
sont facturés au tarif output standard, d'où le surcoût.
"""

from __future__ import annotations

from fahmi2.domain.enums import ReasoningEffort
from fahmi2.domain.phase import PhaseConfig

#: Mots oraux par minute (hypothèse pour l'estimation depuis une durée audio).
WORDS_PER_MINUTE_ORAL = 150.0
#: Tokens par mot (hypothèse DeepSeek).
TOKENS_PER_WORD = 1.3

# Multiplicateurs empiriques appliqués aux tokens de sortie quand le mode
# thinking est activé.
_THINKING_OUTPUT_MULTIPLIER_DEFAULT = 2.5
_THINKING_OUTPUT_MULTIPLIER_HIGH = 3.5
_THINKING_OUTPUT_MULTIPLIER_MAX = 6.0


#: Demi-largeur de la fourchette d'incertitude de l'estimation (±33 %).
#: Heuristique communiquée (« estimation indicative »), pas un intervalle statistique.
ESTIMATE_UNCERTAINTY_RATIO = 0.33


def cost_range(total_usd: float) -> tuple[float, float]:
    """Fourchette ``(bas, haut)`` autour d'un total à ``±ESTIMATE_UNCERTAINTY_RATIO``.

    Args:
        total_usd: Total estimé (ponctuel).

    Returns:
        ``(low, high)`` = ``(total*(1-r), total*(1+r))``.
    """
    return (
        total_usd * (1.0 - ESTIMATE_UNCERTAINTY_RATIO),
        total_usd * (1.0 + ESTIMATE_UNCERTAINTY_RATIO),
    )


def thinking_output_multiplier(config: PhaseConfig | None) -> float:
    """Multiplicateur des tokens de sortie selon le mode thinking.

    Args:
        config: Configuration LLM, ou ``None`` (estimation sans thinking).

    Returns:
        ``1.0`` si thinking désactivé, sinon 2.5 / 3.5 (HIGH) / 6 (MAX).
    """
    if config is None or not config.thinking_enabled:
        return 1.0
    if config.reasoning_effort is ReasoningEffort.MAX:
        return _THINKING_OUTPUT_MULTIPLIER_MAX
    if config.reasoning_effort is ReasoningEffort.HIGH:
        return _THINKING_OUTPUT_MULTIPLIER_HIGH
    return _THINKING_OUTPUT_MULTIPLIER_DEFAULT
