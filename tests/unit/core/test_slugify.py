"""Tests de ``slugify_anchor`` (ancre GFM partagée)."""

from __future__ import annotations

from fahmi2.core.slugify import slugify_anchor


def test_basic_keeps_number_prefix() -> None:
    assert slugify_anchor("1. Analyse financière") == "1-analyse-financière"


def test_keeps_accents() -> None:
    assert slugify_anchor("Stratégie") == "stratégie"


def test_slash_becomes_dash() -> None:
    # Divergence historique corrigée : phase 5 fait foi (slash → tiret).
    assert slugify_anchor("clients/fournisseurs") == "clients-fournisseurs"


def test_strips_punctuation_and_collapses_dashes() -> None:
    assert slugify_anchor("2. WACC, EBITDA & ROI") == "2-wacc-ebitda-roi"


def test_trims_edge_dashes_and_emdash() -> None:
    assert slugify_anchor("  — notions —  ") == "notions"
