"""Tests du manifeste de fraîcheur + persistance des coûts des Visualisations."""

from __future__ import annotations

from fahmi2.domain.enums import Language
from fahmi2.visuals.manifest import VisualsManifest


def _record(
    manifest: VisualsManifest,
    language: Language,
    *,
    map_cost: float = 0.0,
    diagrams_cost: float = 0.0,
) -> None:
    manifest.record(
        language,
        settings_hash="h",
        structure_mtime_ns=1,
        glossary_mtime_ns=2,
        content_mtime_ns=3,
        map_cost_usd=map_cost,
        diagrams_cost_usd=diagrams_cost,
    )


def test_roundtrip_preserve_couts_structure_et_langue() -> None:
    manifest = VisualsManifest()
    manifest.record_structure_cost(0.10, 0.02)
    _record(manifest, Language.FR, map_cost=0.01, diagrams_cost=0.005)
    restored = VisualsManifest.from_dict(manifest.to_dict())
    assert restored.structure_costs() == (0.10, 0.02)
    assert restored.language_costs() == {Language.FR: (0.01, 0.005)}


def test_manifeste_v1_sans_couts_charge_a_zero() -> None:
    # Format v1 : entrées sans clés de coût, pas de structure_costs.
    payload = {
        "version": 1,
        "entries": {
            "fr": {
                "settings_hash": "h",
                "structure_mtime_ns": 1,
                "glossary_mtime_ns": 2,
                "content_mtime_ns": 3,
            }
        },
    }
    manifest = VisualsManifest.from_dict(payload)
    assert manifest.structure_costs() == (0.0, 0.0)
    assert manifest.language_costs() == {Language.FR: (0.0, 0.0)}


def test_is_fresh_insensible_aux_couts() -> None:
    manifest = VisualsManifest()
    _record(manifest, Language.FR, map_cost=0.99, diagrams_cost=0.99)
    assert manifest.is_fresh(
        Language.FR,
        settings_hash="h",
        structure_mtime_ns=1,
        glossary_mtime_ns=2,
        content_mtime_ns=3,
    )
