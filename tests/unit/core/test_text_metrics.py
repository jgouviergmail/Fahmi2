"""Tests de l'estimation de tokens."""

from __future__ import annotations

from fahmi2.core.text_metrics import CHARS_PER_TOKEN, estimate_tokens


def test_estimate_tokens_proportional() -> None:
    assert estimate_tokens("a" * (CHARS_PER_TOKEN * 10)) == 10


def test_estimate_tokens_minimum_one() -> None:
    assert estimate_tokens("") == 1
    assert estimate_tokens("x") == 1
