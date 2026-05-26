"""Tests du rendu Markdown → DOCX (htmldocx)."""

from __future__ import annotations

import zipfile
from pathlib import Path

from fahmi2.infra.export.markdown_docx import render_markdown_to_docx

_MD = (
    "# Titre\n\n"
    "Paragraphe **gras** et *italique*.\n\n"
    "## Sous-titre 第一章\n\n"
    "| A | B |\n|---|---|\n| 中文 | عربي |\n\n"
    "- point un\n- point deux\n"
)


def _document_xml(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        return archive.read("word/document.xml").decode("utf-8")


def test_render_docx_creates_valid_file(tmp_path: Path) -> None:
    out = tmp_path / "doc.docx"
    render_markdown_to_docx(_MD, out)
    assert out.exists()
    # Un .docx est un zip OOXML : signature "PK".
    assert out.read_bytes()[:2] == b"PK"


def test_render_docx_preserves_structure_and_unicode(tmp_path: Path) -> None:
    out = tmp_path / "doc.docx"
    render_markdown_to_docx(_MD, out)
    xml = _document_xml(out)
    assert "Titre" in xml
    assert "<w:tbl>" in xml          # tableau converti
    assert "第一章" in xml            # chinois préservé
    assert "عربي" in xml             # arabe préservé


def test_render_docx_creates_parent_directory(tmp_path: Path) -> None:
    out = tmp_path / "nested" / "doc.docx"
    render_markdown_to_docx("# Titre\n\nTexte.\n", out)
    assert out.exists()
