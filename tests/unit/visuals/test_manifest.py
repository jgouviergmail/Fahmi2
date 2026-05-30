"""Tests du manifeste de fraîcheur + persistance des coûts des Visualisations."""

from __future__ import annotations

import json
from pathlib import Path

from fahmi2.domain.enums import Language
from fahmi2.visuals.manifest import VisualsManifest, manifest_path, read_manifest


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


def test_manifeste_v1_couts_inconnus_omis() -> None:
    # Format v1 : entrées sans clés de coût, pas de structure_costs → inconnus
    # (None / omis), à distinguer d'un coût nul.
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
    assert manifest.structure_costs() is None
    assert manifest.language_costs() == {}


def test_cout_nul_enregistre_distinct_de_inconnu() -> None:
    # Un coût explicitement nul (ex. langue de structure) est conservé, pas omis.
    manifest = VisualsManifest()
    _record(manifest, Language.FR, map_cost=0.0, diagrams_cost=0.0)
    restored = VisualsManifest.from_dict(manifest.to_dict())
    assert restored.language_costs() == {Language.FR: (0.0, 0.0)}


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


def test_read_manifest_payload_non_dict_renvoie_manifeste_vide(tmp_path: Path) -> None:
    # JSON valide mais non-objet (liste) : manifeste vide, surtout pas de crash
    # ``AttributeError`` dans ``from_dict``.
    manifest_path(tmp_path).write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    manifest = read_manifest(tmp_path)
    assert manifest.structure_costs() is None
    assert manifest.language_costs() == {}


def test_structure_costs_longueur_invalide_ignoree() -> None:
    # Paire de coûts de structure mal formée (longueur != 2) → ignorée (inconnu).
    manifest = VisualsManifest.from_dict({"version": 2, "structure_costs": [1.0]})
    assert manifest.structure_costs() is None


def test_structure_costs_non_castable_ignore() -> None:
    # Valeurs non castables en float → ignorées (inconnu), pas de crash.
    manifest = VisualsManifest.from_dict(
        {"version": 2, "structure_costs": ["a", "b"]}
    )
    assert manifest.structure_costs() is None


def test_cout_langue_non_castable_omis_sans_invalider_le_reste() -> None:
    # Une valeur de coût non castable laisse le coût inconnu (langue omise de
    # language_costs) sans invalider la fraîcheur ni faire échouer toute la lecture.
    payload = {
        "version": 2,
        "entries": {
            "fr": {
                "settings_hash": "h",
                "structure_mtime_ns": 1,
                "glossary_mtime_ns": 2,
                "content_mtime_ns": 3,
                "map_cost_usd": "abc",
            }
        },
    }
    manifest = VisualsManifest.from_dict(payload)
    assert manifest.language_costs() == {}
    assert manifest.is_fresh(
        Language.FR,
        settings_hash="h",
        structure_mtime_ns=1,
        glossary_mtime_ns=2,
        content_mtime_ns=3,
    )


def test_entry_non_dict_ignoree() -> None:
    # Une entrée de langue non-dict est ignorée silencieusement (pas de crash).
    manifest = VisualsManifest.from_dict(
        {"version": 2, "entries": {"fr": "pas-un-dict"}}
    )
    assert manifest.language_costs() == {}
    assert not manifest.is_fresh(
        Language.FR,
        settings_hash="h",
        structure_mtime_ns=1,
        glossary_mtime_ns=2,
        content_mtime_ns=3,
    )
