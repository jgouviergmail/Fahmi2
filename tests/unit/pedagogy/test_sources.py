"""Tests des helpers de source du document consolidé."""

from __future__ import annotations

from pathlib import Path

from fahmi2.domain.enums import Language
from fahmi2.infra.storage.fs_artifacts import FsArtifactStore
from fahmi2.pedagogy.sources import (
    consolidated_doc_path,
    load_chapters,
    source_mtime_ns,
)


def test_consolidated_doc_path(tmp_path: Path) -> None:
    assert consolidated_doc_path(tmp_path, Language.FR) == (
        tmp_path / "consolidated.fr.md"
    )


def test_source_mtime_none_when_missing(tmp_path: Path) -> None:
    assert source_mtime_ns(tmp_path, Language.FR) is None


def test_load_chapters_reads_and_parses(tmp_path: Path) -> None:
    FsArtifactStore().write_text_atomic(
        tmp_path / "consolidated.fr.md", "# Cours\n\n# 1. Bases\n\nContenu.\n"
    )
    chapters = load_chapters(tmp_path, Language.FR)
    assert [c.title for c in chapters] == ["Bases"]
    assert source_mtime_ns(tmp_path, Language.FR) is not None


def test_load_chapters_empty_when_missing(tmp_path: Path) -> None:
    assert load_chapters(tmp_path, Language.FR) == ()
