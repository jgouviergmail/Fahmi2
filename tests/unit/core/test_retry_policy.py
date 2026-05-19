"""Tests de la RetryPolicy."""

import pytest

from fahmi2.core.retry.policy import RetryDecision, RetryPolicy


def test_default_policy_values() -> None:
    p = RetryPolicy()
    assert p.max_attempts == 5
    assert p.initial_delay_seconds == 1.0
    assert p.max_delay_seconds == 60.0
    assert p.backoff_multiplier == 2.0
    assert p.jitter is True


def test_compute_delay_grows_exponentially() -> None:
    p = RetryPolicy(
        initial_delay_seconds=1.0,
        max_delay_seconds=60.0,
        backoff_multiplier=2.0,
        jitter=False,
    )
    assert p.compute_delay(attempt=1) == 1.0
    assert p.compute_delay(attempt=2) == 2.0
    assert p.compute_delay(attempt=3) == 4.0
    assert p.compute_delay(attempt=4) == 8.0


def test_compute_delay_caps_at_max() -> None:
    p = RetryPolicy(
        initial_delay_seconds=10.0,
        max_delay_seconds=15.0,
        backoff_multiplier=2.0,
        jitter=False,
    )
    assert p.compute_delay(attempt=1) == 10.0
    assert p.compute_delay(attempt=2) == 15.0
    assert p.compute_delay(attempt=5) == 15.0


def test_jitter_stays_within_bounds() -> None:
    p = RetryPolicy(
        initial_delay_seconds=10.0,
        max_delay_seconds=100.0,
        backoff_multiplier=2.0,
        jitter=True,
    )
    for attempt in range(1, 6):
        base = min(10.0 * (2.0 ** (attempt - 1)), 100.0)
        for _ in range(100):
            d = p.compute_delay(attempt=attempt)
            assert 0.5 * base <= d <= 1.5 * base


def test_retry_decision_values() -> None:
    assert RetryDecision.RETRY.name == "RETRY"
    assert RetryDecision.NO_RETRY.name == "NO_RETRY"
    assert RetryDecision.RAISE_BUDGET.name == "RAISE_BUDGET"


def test_policy_validates_positive_max_attempts() -> None:
    with pytest.raises(ValueError):
        RetryPolicy(max_attempts=0)
    with pytest.raises(ValueError):
        RetryPolicy(max_attempts=-1)


def test_policy_validates_delays() -> None:
    with pytest.raises(ValueError):
        RetryPolicy(initial_delay_seconds=0)
    with pytest.raises(ValueError):
        RetryPolicy(initial_delay_seconds=10.0, max_delay_seconds=5.0)
    with pytest.raises(ValueError):
        RetryPolicy(backoff_multiplier=0.5)


def test_compute_delay_validates_attempt() -> None:
    p = RetryPolicy()
    with pytest.raises(ValueError):
        p.compute_delay(attempt=0)
