"""Classification des exceptions pour la politique de retry.

Décide, pour une exception donnée, s'il faut retenter (``RETRY``), abandonner
(``NO_RETRY``) ou propager un dépassement de budget (``RAISE_BUDGET``). Logique
partagée par le moteur de génération (``pipeline/engine``) et l'orchestrateur de
supports pédagogiques (``pedagogy``).
"""

from __future__ import annotations

from fahmi2.core.errors.exceptions import (
    BudgetExceededError,
    Fahmi2Error,
    LLMError,
    PausedError,
    PermanentError,
    StorageError,
    STTError,
    TransientError,
)
from fahmi2.core.retry.policy import RetryDecision

_RETRYABLE_LLM_CODES: frozenset[str] = frozenset({"LLM.RATE_LIMIT", "LLM.SERVER_ERROR"})
_RETRYABLE_STT_CODES: frozenset[str] = frozenset({"STT.RATE_LIMIT", "STT.API_ERROR"})


def default_classify(exc: BaseException) -> RetryDecision:  # noqa: PLR0911
    """Classifie une exception pour décider du comportement de retry.

    Args:
        exc: Exception levée par un handler ou un générateur.

    Returns:
        ``RetryDecision`` selon les conventions documentées en spec §8.2.
    """
    if isinstance(exc, BudgetExceededError):
        return RetryDecision.RAISE_BUDGET
    if isinstance(exc, PausedError):
        return RetryDecision.NO_RETRY
    if isinstance(exc, TransientError):
        return RetryDecision.RETRY
    if isinstance(exc, PermanentError):
        return RetryDecision.NO_RETRY
    if isinstance(exc, LLMError) and exc.code in _RETRYABLE_LLM_CODES:
        return RetryDecision.RETRY
    if isinstance(exc, STTError) and exc.code in _RETRYABLE_STT_CODES:
        return RetryDecision.RETRY
    if isinstance(exc, StorageError):
        return RetryDecision.NO_RETRY
    if isinstance(exc, Fahmi2Error):
        return RetryDecision.NO_RETRY
    # Erreur inattendue (réseau, autre) — on retente.
    return RetryDecision.RETRY
