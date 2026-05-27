"""Tests de l'export documentaire des supports (un fichier par support / corrigé)."""

from __future__ import annotations

import io
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest
from pypdf import PdfReader

from fahmi2.app.pedagogy_export import (
    _EXPORT_SUPPORT_ORDER,
    collect_pedagogy_documents,
    export_pedagogy_documents,
)
from fahmi2.domain.enums import ExportFormat, Language, SupportType
from fahmi2.domain.ids import ProjectId
from fahmi2.domain.pedagogy import PEDAGOGY_WORKSPACE_SUBDIR
from fahmi2.domain.project import Project
from fahmi2.infra.export.markdown_pdf import cjk_font_available, pdf_fonts_available
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
    stems = [doc.stem for doc in collect_pedagogy_documents(project)]
    assert stems.index("revision_sheet.fr") < stems.index("qcm.fr")
    assert stems.index("qcm.fr") < stems.index("mock_exam.fr")


def test_export_order_covers_every_support() -> None:
    assert set(_EXPORT_SUPPORT_ORDER) == set(SupportType)
    assert len(_EXPORT_SUPPORT_ORDER) == len(set(_EXPORT_SUPPORT_ORDER))


def test_collect_sets_language_per_document(
    tmp_path: Path, make_pedagogy_settings: Any
) -> None:
    # La langue est portée par chaque document → les corrections de rendu PDF
    # (strip émojis, coupe CJK) s'appliquent aux supports comme à la génération.
    project = _project(tmp_path, make_pedagogy_settings)
    ped_dir = project.workspace_folder / PEDAGOGY_WORKSPACE_SUBDIR
    artifacts = FsArtifactStore()
    artifacts.write_text_atomic(
        artifact_markdown_path(ped_dir, SupportType.KEY_POINTS, Language.ZH),
        "# 要点 (zh)\n\n要点内容。\n",
    )
    artifacts.write_text_atomic(
        artifact_markdown_path(ped_dir, SupportType.KEY_POINTS, Language.FR),
        "# Points clés (fr)\n\nContenu.\n",
    )
    by_stem = {doc.stem: doc for doc in collect_pedagogy_documents(project)}
    assert by_stem["key_points.zh"].language is Language.ZH
    assert by_stem["key_points.fr"].language is Language.FR
    # Les supports restent en portrait (pas de tableau large).
    assert by_stem["key_points.zh"].landscape is False


@pytest.mark.skipif(not cjk_font_available(), reason="Police CJK indisponible")
def test_pdf_chinese_support_strips_emoji_and_renders(
    tmp_path: Path, make_pedagogy_settings: Any
) -> None:
    # Un support chinois avec émoji décoratif s'exporte en PDF sans carré ni crash
    # (corrections propagées depuis le renderer partagé).
    project = _project(tmp_path, make_pedagogy_settings)
    ped_dir = project.workspace_folder / PEDAGOGY_WORKSPACE_SUBDIR
    long_cjk = "财务分析解读企业健康状况会计信息的可靠性" * 6
    FsArtifactStore().write_text_atomic(
        artifact_markdown_path(ped_dir, SupportType.REVISION_SHEET, Language.ZH),
        f"# 复习卡 (zh)\n\n> 📖 **定义** — {long_cjk}\n",
    )
    out_dir = tmp_path / "export"
    export_pedagogy_documents(project, output_dir=out_dir, fmt=ExportFormat.PDF)
    pdf_path = out_dir / "revision_sheet.zh.pdf"
    assert pdf_path.exists()
    text = PdfReader(io.BytesIO(pdf_path.read_bytes())).pages[0].extract_text()
    assert "📖" not in text
