"""Tests de la grille tarifaire vision (USD/token + estimation par slide)."""

from fahmi2.infra.vision._pricing import (
    ESTIMATED_INPUT_TOKENS_PER_SLIDE,
    ESTIMATED_OUTPUT_TOKENS_PER_SLIDE,
    estimated_cost_per_slide_usd,
    vision_cost_usd,
)


def test_vision_cost_usd_gpt5_mini() -> None:
    """1M tokens d'entrée + 1M de sortie au tarif gpt-5-mini."""
    cost = vision_cost_usd(
        model="gpt-5-mini", input_tokens=1_000_000, output_tokens=1_000_000
    )
    assert cost == 0.25 + 2.00


def test_vision_cost_usd_zero_tokens() -> None:
    assert vision_cost_usd(model="gpt-5-mini", input_tokens=0, output_tokens=0) == 0.0


def test_vision_cost_usd_unknown_model_falls_back() -> None:
    """Modèle inconnu : retombe sur le tarif par défaut (pas d'exception)."""
    assert (
        vision_cost_usd(model="gpt-9-futur", input_tokens=1_000_000, output_tokens=0)
        == 0.25
    )


def test_estimated_cost_per_slide_consistent() -> None:
    """L'estimation par slide découle des tokens estimés et de la grille."""
    expected = vision_cost_usd(
        model="gpt-5-mini",
        input_tokens=ESTIMATED_INPUT_TOKENS_PER_SLIDE,
        output_tokens=ESTIMATED_OUTPUT_TOKENS_PER_SLIDE,
    )
    assert estimated_cost_per_slide_usd("gpt-5-mini") == expected
