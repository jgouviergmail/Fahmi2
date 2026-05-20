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
        (ValueError("plain"), RetryDecision.RETRY),
    ],
)
def test_default_classify(exc: BaseException, expected: RetryDecision) -> None:
    assert default_classify(exc) is expected
