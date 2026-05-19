"""Exécution d'une fonction avec retry exponentiel et classification d'erreur."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

from fahmi2.core.retry.policy import RetryDecision, RetryPolicy

T = TypeVar("T")


def with_retry(
    fn: Callable[[], T],
    *,
    policy: RetryPolicy,
    classify: Callable[[BaseException], RetryDecision],
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Exécute ``fn`` avec retry selon la ``policy`` et la fonction de classification.

    Args:
        fn: Fonction sans argument à exécuter.
        policy: Politique de retry (nombre d'essais, backoff, jitter).
        classify: Fonction qui décide ``RETRY`` / ``NO_RETRY`` / ``RAISE_BUDGET``
            face à une exception.
        sleep: Fonction d'attente, injectable pour les tests.

    Returns:
        La valeur retournée par ``fn`` lors d'une exécution réussie.

    Raises:
        BaseException: La dernière exception levée par ``fn`` si toutes les
            tentatives échouent ou si ``classify`` retourne ``NO_RETRY`` /
            ``RAISE_BUDGET``.
    """
    for attempt in range(1, policy.max_attempts + 1):
        try:
            return fn()
        except BaseException as exc:  # noqa: BLE001 — on relaie via classify
            decision = classify(exc)
            if decision is RetryDecision.NO_RETRY:
                raise
            if decision is RetryDecision.RAISE_BUDGET:
                raise
            if attempt >= policy.max_attempts:
                raise
            sleep(policy.compute_delay(attempt=attempt))
    raise RuntimeError("Unreachable: retry loop must return or raise")
