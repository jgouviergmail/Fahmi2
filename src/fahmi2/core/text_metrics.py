"""Estimation grossière du nombre de tokens (heuristique caractères).

Source unique partagée (chunking du corpus, garde-fou d'historique du chat, …).
Approximation volontairement simple : ~4 caractères par token.
"""

from __future__ import annotations

CHARS_PER_TOKEN = 4


def estimate_tokens(text: str) -> int:
    """Estime le nombre de tokens d'un texte.

    Args:
        text: Texte à mesurer.

    Returns:
        Nombre de tokens estimé (au moins 1).
    """
    return max(1, len(text) // CHARS_PER_TOKEN)
