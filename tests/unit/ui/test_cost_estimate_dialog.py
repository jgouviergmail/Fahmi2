"""Tests du rendu des lignes du dialogue d'estimation partagé."""

from __future__ import annotations

from fahmi2.ui.cost_estimate_dialog import build_estimate_body


def test_body_includes_breakdown_total_and_range() -> None:
    body = build_estimate_body(
        header_lines=["<b>Projet :</b> P"],
        breakdown=[("STT", 0.18), ("Phase 1", 0.14)],
        total_usd=1.50,
        low_usd=1.00,
        high_usd=2.00,
        cost_ceiling_usd=None,
    )
    assert "STT" in body
    assert "≈ $1.50" in body
    assert "$1.00 – $2.00" in body
    assert "indicative" in body


def test_body_warns_when_high_exceeds_ceiling() -> None:
    body = build_estimate_body(
        header_lines=[],
        breakdown=[("STT", 0.18)],
        total_usd=1.50,
        low_usd=1.00,
        high_usd=2.00,
        cost_ceiling_usd=1.80,
    )
    assert "plafond" in body.lower()
    assert "dépasse" in body.lower()
