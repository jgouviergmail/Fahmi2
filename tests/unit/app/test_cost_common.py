"""Tests des helpers de coût partagés."""

from __future__ import annotations

import pytest

from fahmi2.app._cost_common import ESTIMATE_UNCERTAINTY_RATIO, cost_range


def test_cost_range_symmetric() -> None:
    low, high = cost_range(1.50)
    assert low == pytest.approx(1.50 * (1 - ESTIMATE_UNCERTAINTY_RATIO))
    assert high == pytest.approx(1.50 * (1 + ESTIMATE_UNCERTAINTY_RATIO))


def test_cost_range_zero() -> None:
    assert cost_range(0.0) == (0.0, 0.0)
