"""Tests des constantes centralisées des Visualisations."""

from __future__ import annotations

from fahmi2.domain.enums import SupportDensity
from fahmi2.visuals._constants import (
    GLEANING_ROUNDS,
    MAX_SEMANTIC_NODES_PER_UNIT,
    MAX_UNIT_CHARS,
    MIN_UNIT_BODY_CHARS,
)


def test_density_cap_couvre_toutes_les_densites() -> None:
    assert set(MAX_SEMANTIC_NODES_PER_UNIT) == set(SupportDensity)


def test_caps_croissants_avec_la_densite() -> None:
    caps = MAX_SEMANTIC_NODES_PER_UNIT
    assert caps[SupportDensity.LIGHT] < caps[SupportDensity.STANDARD]
    assert caps[SupportDensity.STANDARD] < caps[SupportDensity.DENSE]


def test_bornes_unite_coherentes() -> None:
    assert 0 < MIN_UNIT_BODY_CHARS < MAX_UNIT_CHARS
    assert GLEANING_ROUNDS >= 0
