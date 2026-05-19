"""Tests du runner with_retry()."""

import pytest

from fahmi2.core.errors.exceptions import (
    BudgetExceededError,
    Fahmi2Error,
    PermanentError,
    TransientError,
)
from fahmi2.core.errors.severity import Severity
from fahmi2.core.retry.policy import RetryDecision, RetryPolicy
from fahmi2.core.retry.runner import with_retry


def _make_error(cls: type[Fahmi2Error] = TransientError) -> Fahmi2Error:
    return cls(code="X", user_message="oops", severity=Severity.ERROR)


def _classifier_default(exc: BaseException) -> RetryDecision:
    if isinstance(exc, BudgetExceededError):
        return RetryDecision.RAISE_BUDGET
    if isinstance(exc, TransientError):
        return RetryDecision.RETRY
    return RetryDecision.NO_RETRY


def _noop_sleep(_: float) -> None:
    return None


def test_with_retry_returns_value_on_first_attempt() -> None:
    calls = {"n": 0}

    def fn() -> str:
        calls["n"] += 1
        return "ok"

    result = with_retry(
        fn,
        policy=RetryPolicy(jitter=False),
        classify=_classifier_default,
        sleep=_noop_sleep,
    )
    assert result == "ok"
    assert calls["n"] == 1


def test_with_retry_retries_until_success() -> None:
    calls = {"n": 0}

    def fn() -> str:
        calls["n"] += 1
        if calls["n"] < 3:
            raise _make_error(TransientError)
        return "ok"

    result = with_retry(
        fn,
        policy=RetryPolicy(max_attempts=5, initial_delay_seconds=0.001, jitter=False),
        classify=_classifier_default,
        sleep=_noop_sleep,
    )
    assert result == "ok"
    assert calls["n"] == 3


def test_with_retry_raises_after_max_attempts() -> None:
    calls = {"n": 0}

    def fn() -> None:
        calls["n"] += 1
        raise _make_error(TransientError)

    with pytest.raises(TransientError):
        with_retry(
            fn,
            policy=RetryPolicy(
                max_attempts=3, initial_delay_seconds=0.001, jitter=False
            ),
            classify=_classifier_default,
            sleep=_noop_sleep,
        )
    assert calls["n"] == 3


def test_with_retry_no_retry_decision_raises_immediately() -> None:
    calls = {"n": 0}

    def fn() -> None:
        calls["n"] += 1
        raise _make_error(PermanentError)

    with pytest.raises(PermanentError):
        with_retry(
            fn,
            policy=RetryPolicy(
                max_attempts=5, initial_delay_seconds=0.001, jitter=False
            ),
            classify=_classifier_default,
            sleep=_noop_sleep,
        )
    assert calls["n"] == 1


def test_with_retry_raises_budget_immediately() -> None:
    calls = {"n": 0}

    def fn() -> None:
        calls["n"] += 1
        raise BudgetExceededError(
            code="BUDGET.EXCEEDED",
            user_message="oups",
            severity=Severity.WARNING,
        )

    with pytest.raises(BudgetExceededError):
        with_retry(
            fn,
            policy=RetryPolicy(
                max_attempts=5, initial_delay_seconds=0.001, jitter=False
            ),
            classify=_classifier_default,
            sleep=_noop_sleep,
        )
    assert calls["n"] == 1


def test_with_retry_propagates_unexpected_exceptions() -> None:
    def fn() -> None:
        raise ValueError("plain")

    with pytest.raises(ValueError, match="plain"):
        with_retry(
            fn,
            policy=RetryPolicy(
                max_attempts=3, initial_delay_seconds=0.001, jitter=False
            ),
            classify=_classifier_default,
            sleep=_noop_sleep,
        )


def test_with_retry_sleeps_between_attempts() -> None:
    sleeps: list[float] = []

    def fn() -> None:
        raise _make_error(TransientError)

    with pytest.raises(TransientError):
        with_retry(
            fn,
            policy=RetryPolicy(
                max_attempts=3,
                initial_delay_seconds=1.0,
                backoff_multiplier=2.0,
                jitter=False,
            ),
            classify=_classifier_default,
            sleep=sleeps.append,
        )
    # 3 attempts -> 2 sleeps : entre attempt 1 et 2, et entre 2 et 3
    assert sleeps == [1.0, 2.0]
