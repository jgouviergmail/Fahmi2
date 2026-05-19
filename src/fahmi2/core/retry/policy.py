"""Définition de ``RetryPolicy`` et énumération des décisions de retry."""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from enum import Enum, auto

_JITTER_LOW = 0.5
_JITTER_HIGH = 1.5
_JITTER_RANGE = _JITTER_HIGH - _JITTER_LOW
_RANDOM_DIVISOR = 1 << 32


class RetryDecision(Enum):
    """Décision à prendre face à une exception levée par une opération à retry."""

    RETRY = auto()
    NO_RETRY = auto()
    RAISE_BUDGET = auto()


def _uniform_jitter_multiplier() -> float:
    """Retourne un multiplicateur uniforme dans ``[_JITTER_LOW, _JITTER_HIGH]``.

    Utilise ``secrets`` (cryptographique) pour éviter le warning ruff S311 et
    rester déterministe pour les tests d'enveloppe (les bornes restent valides).

    Returns:
        Un flottant dans l'intervalle ``[0.5, 1.5]``.
    """
    fraction = secrets.randbits(32) / _RANDOM_DIVISOR
    return _JITTER_LOW + fraction * _JITTER_RANGE


@dataclass(frozen=True)
class RetryPolicy:
    """Politique de retry exponentielle bornée avec jitter optionnel.

    Attributes:
        max_attempts: Nombre maximal de tentatives (>= 1).
        initial_delay_seconds: Délai avant la 1re retry (> 0).
        max_delay_seconds: Plafond du délai entre retries (>= initial_delay).
        backoff_multiplier: Multiplicateur appliqué à chaque tentative (>= 1).
        jitter: Si ``True``, le délai est multiplié par un facteur uniforme
            dans ``[0.5, 1.5]`` pour éviter les pics de retry synchronisés.
    """

    max_attempts: int = 5
    initial_delay_seconds: float = 1.0
    max_delay_seconds: float = 60.0
    backoff_multiplier: float = 2.0
    jitter: bool = True

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if self.initial_delay_seconds <= 0:
            raise ValueError("initial_delay_seconds must be > 0")
        if self.max_delay_seconds < self.initial_delay_seconds:
            raise ValueError("max_delay_seconds must be >= initial_delay_seconds")
        if self.backoff_multiplier < 1:
            raise ValueError("backoff_multiplier must be >= 1")

    def compute_delay(self, *, attempt: int) -> float:
        """Calcule le délai d'attente avant la tentative ``attempt`` (1-indexed).

        Args:
            attempt: Numéro de tentative (1 = première retry après l'échec initial).

        Returns:
            Délai en secondes, borné par ``max_delay_seconds``, éventuellement bruité.

        Raises:
            ValueError: Si ``attempt < 1``.
        """
        if attempt < 1:
            raise ValueError("attempt must be >= 1")
        base = min(
            self.initial_delay_seconds * (self.backoff_multiplier ** (attempt - 1)),
            self.max_delay_seconds,
        )
        if not self.jitter:
            return base
        return base * _uniform_jitter_multiplier()
