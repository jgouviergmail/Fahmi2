"""Tests du manifeste de fraîcheur des supports."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fahmi2.domain.enums import ExportFormat, Language, SupportType
from fahmi2.infra.storage.fs_artifacts import FsArtifactStore
from fahmi2.pedagogy.manifest import (
    PedagogyManifest,
    compute_settings_hash,
    read_manifest,
    write_manifest,
)


def test_settings_hash_is_stable_and_sensitive(make_pedagogy_settings: Any) -> None:
    base = make_pedagogy_settings()
    assert compute_settings_hash(base) == compute_settings_hash(
        make_pedagogy_settings()
    )
    changed = make_pedagogy_settings(pedagogy_directives="autre")
    assert compute_settings_hash(base) != compute_settings_hash(changed)


def test_settings_hash_ignores_export_formats(make_pedagogy_settings: Any) -> None:
    a = make_pedagogy_settings(export_formats=frozenset({ExportFormat.APKG}))
    b = make_pedagogy_settings(export_formats=frozenset({ExportFormat.MARKDOWN}))
    assert compute_settings_hash(a) == compute_settings_hash(b)


def test_is_fresh_logic() -> None:
    manifest = PedagogyManifest()
    st, lang = SupportType.FLASHCARDS_CONCEPTS, Language.FR
    assert not manifest.is_fresh(st, lang, settings_hash="h", source_mtime_ns=10)
    manifest.record(st, lang, settings_hash="h", source_mtime_ns=10)
    assert manifest.is_fresh(st, lang, settings_hash="h", source_mtime_ns=10)
    assert not manifest.is_fresh(st, lang, settings_hash="h2", source_mtime_ns=10)
    assert not manifest.is_fresh(st, lang, settings_hash="h", source_mtime_ns=99)


def test_round_trip(tmp_path: Path) -> None:
    artifacts = FsArtifactStore()
    manifest = PedagogyManifest()
    manifest.record(
        SupportType.FLASHCARDS_CONCEPTS,
        Language.FR,
        settings_hash="h",
        source_mtime_ns=10,
    )
    write_manifest(artifacts, tmp_path, manifest)
    loaded = read_manifest(tmp_path)
    assert loaded.is_fresh(
        SupportType.FLASHCARDS_CONCEPTS,
        Language.FR,
        settings_hash="h",
        source_mtime_ns=10,
    )


def test_read_missing_returns_empty(tmp_path: Path) -> None:
    loaded = read_manifest(tmp_path)
    assert not loaded.is_fresh(
        SupportType.FLASHCARDS_CONCEPTS,
        Language.FR,
        settings_hash="h",
        source_mtime_ns=1,
    )
