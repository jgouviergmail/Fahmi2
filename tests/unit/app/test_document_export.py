"""Tests du cœur d'écriture documentaire partagé (``write_documents``)."""

from __future__ import annotations

from pathlib import Path

import pytest

from fahmi2.app.document_export import ExportDocument, write_documents
from fahmi2.domain.enums import ExportFormat
from fahmi2.infra.export.markdown_pdf import EXTENSION_BY_FORMAT, pdf_fonts_available


def test_extension_by_format_doc_formats_only() -> None:
    assert EXTENSION_BY_FORMAT == {
        ExportFormat.MARKDOWN: ".md",
        ExportFormat.PDF: ".pdf",
        ExportFormat.HTML: ".html",
    }
    assert ExportFormat.APKG not in EXTENSION_BY_FORMAT


def test_write_markdown_copies_content_and_preserves_order(tmp_path: Path) -> None:
    docs = [
        ExportDocument(stem="a", markdown="# A\n\nun"),
        ExportDocument(stem="b", markdown="# B\n\ndeux"),
    ]
    result = write_documents(docs, output_dir=tmp_path, fmt=ExportFormat.MARKDOWN)
    assert result.document_count == 2
    assert result.output_paths == (tmp_path / "a.md", tmp_path / "b.md")
    assert (tmp_path / "a.md").read_text(encoding="utf-8") == "# A\n\nun"


def test_write_html_renders_self_contained(tmp_path: Path) -> None:
    result = write_documents(
        [ExportDocument(stem="doc", markdown="# Titre\n\n- x\n")],
        output_dir=tmp_path,
        fmt=ExportFormat.HTML,
    )
    assert result.document_count == 1
    content = (tmp_path / "doc.html").read_text(encoding="utf-8")
    assert "<!DOCTYPE html>" in content
    assert "<h1" in content  # l'extension toc ajoute un id : <h1 id="...">.


def test_write_rejects_non_document_format(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="non documentaire"):
        write_documents(
            [ExportDocument(stem="a", markdown="x")],
            output_dir=tmp_path,
            fmt=ExportFormat.APKG,
        )


@pytest.mark.skipif(not pdf_fonts_available(), reason="Police Unicode indisponible")
def test_write_pdf(tmp_path: Path) -> None:
    result = write_documents(
        [ExportDocument(stem="doc", markdown="# Titre\n\ntexte\n")],
        output_dir=tmp_path,
        fmt=ExportFormat.PDF,
    )
    assert (tmp_path / "doc.pdf").exists()
    assert result.document_count == 1
