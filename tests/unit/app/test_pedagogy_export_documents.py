"""Tests de l'export Markdown / PDF des supports pédagogiques."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from fahmi2.app.pedagogy_export import (
    export_pedagogy_to_markdown,
    export_pedagogy_to_pdf,
)
from fahmi2.domain.enums import Language, SupportType
from fahmi2.domain.ids import ProjectId
from fahmi2.domain.pedagogy import PEDAGOGY_WORKSPACE_SUBDIR
from fahmi2.domain.project import Project
from fahmi2.infra.export.markdown_pdf import pdf_fonts_available
from fahmi2.infra.storage.fs_artifacts import FsArtifactStore
from fahmi2.pedagogy.artifact_writer import (
    artifact_correction_markdown_path,
    artifact_markdown_path,
)


def _project(tmp_path: Path, make_pedagogy_settings: Any) -> Project:
    return Project(
        id=ProjectId.new(),
        name="Mon Cours",
        workspace_folder=tmp_path / "ws",
        created_at=datetime.now(tz=UTC),
        pedagogy=make_pedagogy_settings(),
    )


def _seed_markdown(pedagogy_dir: Path) -> None:
    artifacts = FsArtifactStore()
    artifacts.write_text_atomic(
        artifact_markdown_path(
            pedagogy_dir, SupportType.FLASHCARDS_CONCEPTS, Language.FR
        ),
        "# Flashcards — Glossaire (fr)\n\n### PIB\n\nProduit intérieur brut\n",
    )
    artifacts.write_text_atomic(
        artifact_markdown_path(pedagogy_dir, SupportType.QCM, Language.FR),
        "# QCM (fr)\n\n### 1. Q ?\n\n- A. a\n- B. b\n",
    )
    artifacts.write_text_atomic(
        artifact_correction_markdown_path(pedagogy_dir, SupportType.QCM, Language.FR),
        "# QCM — Corrigé (fr)\n\n### 1. Q ?\n\n**Réponse : A**\n",
    )


def test_export_markdown_writes_subject_and_correction(
    tmp_path: Path, make_pedagogy_settings: Any
) -> None:
    project = _project(tmp_path, make_pedagogy_settings)
    _seed_markdown(project.workspace_folder / PEDAGOGY_WORKSPACE_SUBDIR)
    out_dir = tmp_path / "export"
    result = export_pedagogy_to_markdown(project, output_dir=out_dir)
    subject = out_dir / "supports.fr.md"
    correction = out_dir / "supports.fr.corrige.md"
    assert subject.exists()
    assert correction.exists()
    assert result.document_count == 2
    content = subject.read_text(encoding="utf-8")
    assert "Flashcards — Glossaire" in content
    assert "QCM (fr)" in content


def test_export_markdown_empty(tmp_path: Path, make_pedagogy_settings: Any) -> None:
    project = _project(tmp_path, make_pedagogy_settings)
    result = export_pedagogy_to_markdown(project, output_dir=tmp_path / "export")
    assert result.document_count == 0


@pytest.mark.skipif(not pdf_fonts_available(), reason="Police Unicode indisponible")
def test_export_pdf_writes_files(
    tmp_path: Path, make_pedagogy_settings: Any
) -> None:
    project = _project(tmp_path, make_pedagogy_settings)
    _seed_markdown(project.workspace_folder / PEDAGOGY_WORKSPACE_SUBDIR)
    out_dir = tmp_path / "export"
    result = export_pedagogy_to_pdf(project, output_dir=out_dir)
    assert (out_dir / "supports.fr.pdf").exists()
    assert (out_dir / "supports.fr.corrige.pdf").exists()
    assert result.document_count == 2
