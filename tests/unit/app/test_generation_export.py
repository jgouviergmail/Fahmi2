"""Tests de l'export documentaire de la Génération (consolidé + glossaire)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from fahmi2.app.generation_export import (
    collect_generation_documents,
    export_generation_documents,
)
from fahmi2.domain.enums import ExportFormat
from fahmi2.domain.generation import (
    GENERATION_OUTPUT_SUBDIR,
    GENERATION_WORKSPACE_SUBDIR,
)
from fahmi2.domain.ids import ProjectId
from fahmi2.domain.project import Project
from fahmi2.infra.export.markdown_pdf import pdf_fonts_available
from fahmi2.infra.storage.fs_artifacts import FsArtifactStore


def _project(tmp_path: Path) -> Project:
    return Project(
        id=ProjectId.new(),
        name="Cours",
        workspace_folder=tmp_path / "ws",
        created_at=datetime.now(tz=UTC),
        generation=None,
    )


def _seed_output(project: Project) -> Path:
    out = (
        project.workspace_folder
        / GENERATION_WORKSPACE_SUBDIR
        / GENERATION_OUTPUT_SUBDIR
    )
    store = FsArtifactStore()
    store.write_text_atomic(out / "consolidated.fr.md", "# Cours (fr)\n\nCorps.\n")
    store.write_text_atomic(out / "glossary.fr.md", "# Glossaire (fr)\n\n| T | D |\n")
    return out


def test_collect_returns_consolidated_then_glossary(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _seed_output(project)
    docs = collect_generation_documents(project)
    assert [doc.stem for doc in docs] == ["consolidated.fr", "glossary.fr"]
    # Le glossaire est exporté en paysage avec des largeurs de colonnes ; le
    # consolidé reste en portrait par défaut.
    by_stem = {doc.stem: doc for doc in docs}
    assert by_stem["consolidated.fr"].pdf_landscape is False
    assert by_stem["glossary.fr"].pdf_landscape is True
    assert by_stem["glossary.fr"].pdf_column_widths is not None


def test_collect_empty_when_no_output(tmp_path: Path) -> None:
    # generation=None et aucun fichier : liste vide (pas de crash).
    assert collect_generation_documents(_project(tmp_path)) == []


def test_export_markdown_writes_separate_files(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _seed_output(project)
    out_dir = tmp_path / "export"
    result = export_generation_documents(
        project, output_dir=out_dir, fmt=ExportFormat.MARKDOWN
    )
    assert (out_dir / "consolidated.fr.md").exists()
    assert (out_dir / "glossary.fr.md").exists()
    assert result.document_count == 2


@pytest.mark.skipif(not pdf_fonts_available(), reason="Police Unicode indisponible")
def test_export_pdf(tmp_path: Path) -> None:
    project = _project(tmp_path)
    _seed_output(project)
    out_dir = tmp_path / "export"
    result = export_generation_documents(
        project, output_dir=out_dir, fmt=ExportFormat.PDF
    )
    assert (out_dir / "consolidated.fr.pdf").exists()
    assert (out_dir / "glossary.fr.pdf").exists()
    assert result.document_count == 2
