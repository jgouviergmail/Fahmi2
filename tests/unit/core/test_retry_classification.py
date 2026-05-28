"""Tests de la classification des exceptions pour le retry."""

from __future__ import annotations

import pytest

from fahmi2.core.errors.exceptions import (
    BudgetExceededError,
    LLMError,
    PausedError,
    PermanentError,
    TransientError,
)
from fahmi2.core.errors.severity import Severity
from fahmi2.core.retry.classification import default_classify
from fahmi2.core.retry.policy import RetryDecision


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (
            TransientError(code="X", user_message="x", severity=Severity.ERROR),
            RetryDecision.RETRY,
        ),
        (
            PermanentError(code="X", user_message="x", severity=Severity.ERROR),
            RetryDecision.NO_RETRY,
        ),
        (
            BudgetExceededError(
                code="BUDGET.EXCEEDED", user_message="x", severity=Severity.WARNING
            ),
            RetryDecision.RAISE_BUDGET,
        ),
        (
            PausedError(code="RUN.PAUSED", user_message="x", severity=Severity.INFO),
            RetryDecision.NO_RETRY,
        ),
        (
            LLMError(code="LLM.RATE_LIMIT", user_message="x", severity=Severity.WARNING),
            RetryDecision.RETRY,
        ),
        (
            LLMError(code="LLM.AUTH_INVALID", user_message="x", severity=Severity.ERROR),
            RetryDecision.NO_RETRY,
        ),
        # Cas documenté DeepSeek (« the API may occasionally return empty
        # content ») : doit être retryable, sinon la phase tombe à la 1ère
        # occurrence d'un comportement explicitement transitoire.
        (
            LLMError(
                code="LLM.EMPTY_CONTENT", user_message="x", severity=Severity.WARNING
            ),
            RetryDecision.RETRY,
        ),
        # Le LLM a produit un JSON valide mais hors schéma. Retry à l'identique
        # peut récupérer le bon schéma (le LLM est non-déterministe).
        (
            LLMError(
                code="LLM.UNEXPECTED_JSON_SHAPE",
                user_message="x",
                severity=Severity.ERROR,
            ),
            RetryDecision.RETRY,
        ),
        # INVALID_JSON reste NO_RETRY : si le contenu est syntactiquement
        # cassé, retry à l'identique n'a aucune raison de réussir.
        (
            LLMError(
                code="LLM.INVALID_JSON", user_message="x", severity=Severity.ERROR
            ),
            RetryDecision.NO_RETRY,
        ),
        (ValueError("plain"), RetryDecision.RETRY),
    ],
)
def test_default_classify(exc: BaseException, expected: RetryDecision) -> None:
    assert default_classify(exc) is expected
