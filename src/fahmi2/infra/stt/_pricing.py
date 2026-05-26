"""Tarifs des modèles de transcription cloud OpenAI (USD par minute d'audio).

Grille **extensible** : ajouter un modèle = une entrée dans
``_USD_PER_MINUTE``. Un modèle inconnu retombe sur ``_DEFAULT_USD_PER_MINUTE``
(plutôt que de lever), pour qu'un nouveau modèle non encore tarifé ne casse pas
le calcul de coût. Partagée par l'adapter cloud (coût réel) et le
``CostEstimator`` (estimation pré-run) — source unique des tarifs STT.
"""

from __future__ import annotations

_SECONDS_PER_MINUTE = 60.0

#: USD / minute d'audio, par identifiant de modèle de transcription cloud.
_USD_PER_MINUTE: dict[str, float] = {
    "whisper-1": 0.006,
    "gpt-4o-transcribe": 0.006,
    "gpt-4o-mini-transcribe": 0.003,
}
_DEFAULT_USD_PER_MINUTE = 0.006


def stt_cost_usd(*, model: str, duration_seconds: float) -> float:
    """Calcule le coût USD d'une transcription cloud.

    Args:
        model: Identifiant du modèle de transcription cloud.
        duration_seconds: Durée d'audio transcrite (secondes).

    Returns:
        Le coût en USD (0 si ``duration_seconds`` <= 0).
    """
    if duration_seconds <= 0:
        return 0.0
    rate = _USD_PER_MINUTE.get(model, _DEFAULT_USD_PER_MINUTE)
    return duration_seconds / _SECONDS_PER_MINUTE * rate
