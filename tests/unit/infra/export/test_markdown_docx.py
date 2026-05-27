"""Tests du rendu Markdown → DOCX (htmldocx)."""

from __future__ import annotations

import zipfile
from pathlib import Path

from docx import Document
from docx.enum.section import WD_ORIENT

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


def test_render_docx_portrait_by_default(tmp_path: Path) -> None:
    out = tmp_path / "portrait.docx"
    render_markdown_to_docx(_MD, out)
    section = Document(str(out)).sections[0]
    width, height = section.page_width, section.page_height
    assert width is not None and height is not None
    assert section.orientation == WD_ORIENT.PORTRAIT
    assert height > width


def test_render_docx_landscape_sets_orientation(tmp_path: Path) -> None:
    # Glossaire : paysage (largeur > hauteur) comme le PDF.
    out = tmp_path / "landscape.docx"
    render_markdown_to_docx(_MD, out, landscape=True)
    section = Document(str(out)).sections[0]
    width, height = section.page_width, section.page_height
    assert width is not None and height is not None
    assert section.orientation == WD_ORIENT.LANDSCAPE
    assert width > height


def test_render_docx_tables_have_borders_and_full_width(tmp_path: Path) -> None:
    # htmldocx ne traduit ni les bordures CSS ni width:100% ; on les rétablit
    # (style Table Grid + tblW à 100 %) pour s'aligner sur HTML/PDF.
    out = tmp_path / "tbl.docx"
    render_markdown_to_docx(_MD, out)  # _MD contient un tableau
    xml = _document_xml(out)
    assert "TableGrid" in xml  # style à bordures appliqué
    assert 'w:type="pct"' in xml
    assert 'w:w="5000"' in xml  # 100 % de la largeur utile
