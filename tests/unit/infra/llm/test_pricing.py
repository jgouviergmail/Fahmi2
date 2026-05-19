"""Tests des constantes tarifaires DeepSeek v4."""

import pytest

from fahmi2.infra.llm._pricing import PRICING, ModelPricing, get_pricing


def test_pricing_contains_both_models() -> None:
    assert set(PRICING) == {"deepseek-v4-flash", "deepseek-v4-pro"}


def test_get_pricing_known_model() -> None:
    pricing = get_pricing("deepseek-v4-flash")
    assert isinstance(pricing, ModelPricing)


def test_get_pricing_unknown_raises() -> None:
    with pytest.raises(KeyError):
        get_pricing("unknown-model")


def test_cost_for_flash_only_miss_no_cache() -> None:
    p = get_pricing("deepseek-v4-flash")
    cost = p.cost_for(
        prompt_tokens=1_000_000,
        completion_tokens=0,
        cached_prompt_tokens=0,
    )
    assert cost == pytest.approx(0.14)


def test_cost_for_flash_output() -> None:
    p = get_pricing("deepseek-v4-flash")
    cost = p.cost_for(
        prompt_tokens=0,
        completion_tokens=1_000_000,
        cached_prompt_tokens=0,
    )
    assert cost == pytest.approx(0.28)


def test_cost_for_flash_with_cache_hit() -> None:
    p = get_pricing("deepseek-v4-flash")
    cost = p.cost_for(
        prompt_tokens=1_000_000,
        completion_tokens=0,
        cached_prompt_tokens=1_000_000,
    )
    assert cost == pytest.approx(0.0028)


def test_cost_for_partial_cache() -> None:
    p = get_pricing("deepseek-v4-flash")
    cost = p.cost_for(
        prompt_tokens=1_000_000,
        completion_tokens=0,
        cached_prompt_tokens=500_000,
    )
    expected = (500_000 * 0.0028 + 500_000 * 0.14) / 1_000_000
    assert cost == pytest.approx(expected)


def test_cost_for_pro() -> None:
    p = get_pricing("deepseek-v4-pro")
    cost = p.cost_for(
        prompt_tokens=1_000_000,
        completion_tokens=1_000_000,
        cached_prompt_tokens=0,
    )
    assert cost == pytest.approx(0.435 + 0.87)


def test_cost_for_handles_cached_overflow() -> None:
    # Si cached > prompt, on borne à 0 miss_tokens (defensive)
    p = get_pricing("deepseek-v4-flash")
    cost = p.cost_for(
        prompt_tokens=100,
        completion_tokens=0,
        cached_prompt_tokens=1000,
    )
    expected = 1000 * 0.0028 / 1_000_000
    assert cost == pytest.approx(expected)
