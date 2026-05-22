"""Tests de l'export documentaire des supports (un fichier par support / corrigé)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from fahmi2.app.pedagogy_export import (
    _EXPORT_SUPPORT_ORDER,
    collect_pedagogy_documents,
    export_pedagogy_documents,
)
from fahmi2.domain.enums import ExportFormat, Language, SupportType
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


def test_markdown_one_file_per_support_and_correction(
    tmp_path: Path, make_pedagogy_settings: Any
) -> None:
    project = _project(tmp_path, make_pedagogy_settings)
    _seed_markdown(project.workspace_folder / PEDAGOGY_WORKSPACE_SUBDIR)
    out_dir = tmp_path / "export"
    result = export_pedagogy_documents(
        project, output_dir=out_dir, fmt=ExportFormat.MARKDOWN
    )
    assert (out_dir / "flashcards_concepts.fr.md").exists()
    assert (out_dir / "qcm.fr.md").exists()
    assert (out_dir / "qcm.fr.corrige.md").exists()
    assert result.document_count == 3
    # Plus d'agrégat par langue.
    assert not (out_dir / "supports.fr.md").exists()
    assert "Produit intérieur brut" in (
        out_dir / "flashcards_concepts.fr.md"
    ).read_text(encoding="utf-8")


def test_markdown_empty(tmp_path: Path, make_pedagogy_settings: Any) -> None:
    project = _project(tmp_path, make_pedagogy_settings)
    result = export_pedagogy_documents(
        project, output_dir=tmp_path / "export", fmt=ExportFormat.MARKDOWN
    )
    assert result.document_count == 0


@pytest.mark.skipif(not pdf_fonts_available(), reason="Police Unicode indisponible")
def test_pdf_one_file_per_support(
    tmp_path: Path, make_pedagogy_settings: Any
) -> None:
    project = _project(tmp_path, make_pedagogy_settings)
    _seed_markdown(project.workspace_folder / PEDAGOGY_WORKSPACE_SUBDIR)
    out_dir = tmp_path / "export"
    result = export_pedagogy_documents(
        project, output_dir=out_dir, fmt=ExportFormat.PDF
    )
    assert (out_dir / "flashcards_concepts.fr.pdf").exists()
    assert (out_dir / "qcm.fr.corrige.pdf").exists()
    assert result.document_count == 3


def test_html_self_contained_per_support(
    tmp_path: Path, make_pedagogy_settings: Any
) -> None:
    project = _project(tmp_path, make_pedagogy_settings)
    _seed_markdown(project.workspace_folder / PEDAGOGY_WORKSPACE_SUBDIR)
    out_dir = tmp_path / "export"
    result = export_pedagogy_documents(
        project, output_dir=out_dir, fmt=ExportFormat.HTML
    )
    assert (out_dir / "qcm.fr.html").exists()
    assert (out_dir / "flashcards_concepts.fr.html").exists()
    assert result.document_count == 3
    content = (out_dir / "qcm.fr.html").read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in content
    assert 'charset="utf-8"' in content
    assert "<h1" in content  # l'extension toc ajoute un id : <h1 id="...">.


def test_collect_order_learning_then_exercises(
    tmp_path: Path, make_pedagogy_settings: Any
) -> None:
    project = _project(tmp_path, make_pedagogy_settings)
    ped_dir = project.workspace_folder / PEDAGOGY_WORKSPACE_SUBDIR
    artifacts = FsArtifactStore()
    for support, body in (
        (SupportType.MOCK_EXAM, "# Examen blanc (fr)\n"),
        (SupportType.QCM, "# QCM (fr)\n"),
        (SupportType.REVISION_SHEET, "# Fiche (fr)\n"),
    ):
        artifacts.write_text_atomic(
            artifact_markdown_path(ped_dir, support, Language.FR), body
        )
    stems = [stem for stem, _ in collect_pedagogy_documents(project)]
    assert stems.index("revision_sheet.fr") < stems.index("qcm.fr")
    assert stems.index("qcm.fr") < stems.index("mock_exam.fr")


def test_export_order_covers_every_support() -> None:
    assert set(_EXPORT_SUPPORT_ORDER) == set(SupportType)
    assert len(_EXPORT_SUPPORT_ORDER) == len(set(_EXPORT_SUPPORT_ORDER))
