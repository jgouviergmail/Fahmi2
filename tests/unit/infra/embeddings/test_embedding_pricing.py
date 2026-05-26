"""Tests de la grille tarifaire des embeddings."""

from __future__ import annotations

import pytest

from fahmi2.infra.embeddings._pricing import embedding_cost_usd


def test_known_model_rate() -> None:
    # 1M tokens × 0,02 $/Mtok = 0,02 $.
    cost = embedding_cost_usd(model="text-embedding-3-small", total_tokens=1_000_000)
    assert cost == pytest.approx(0.02)


def test_unknown_model_uses_default() -> None:
    cost = embedding_cost_usd(model="modele-inconnu", total_tokens=1_000_000)
    assert cost == pytest.approx(0.02)


def test_zero_tokens_is_free() -> None:
    assert embedding_cost_usd(model="text-embedding-3-large", total_tokens=0) == 0.0
