"""Tests de la grille tarifaire des modèles de transcription cloud."""

from __future__ import annotations

import pytest

from fahmi2.infra.stt._pricing import stt_cost_usd


def test_whisper_and_gpt4o_same_rate() -> None:
    # whisper-1 et gpt-4o-transcribe : 0,006 $/min.
    cost = stt_cost_usd(model="whisper-1", duration_seconds=60.0)
    assert cost == pytest.approx(0.006)
    assert stt_cost_usd(
        model="gpt-4o-transcribe", duration_seconds=60.0
    ) == pytest.approx(0.006)


def test_mini_is_cheaper() -> None:
    # gpt-4o-mini-transcribe : 0,003 $/min (2× moins cher).
    cost = stt_cost_usd(model="gpt-4o-mini-transcribe", duration_seconds=60.0)
    assert cost == pytest.approx(0.003)


def test_unknown_model_uses_default() -> None:
    cost = stt_cost_usd(model="modele-inconnu", duration_seconds=60.0)
    assert cost == pytest.approx(0.006)


def test_zero_or_negative_duration_is_free() -> None:
    assert stt_cost_usd(model="whisper-1", duration_seconds=0.0) == 0.0
    assert stt_cost_usd(model="whisper-1", duration_seconds=-10.0) == 0.0
