"""Tests du rendu PDF et de la table d'extensions de format."""

from __future__ import annotations

from pathlib import Path

import pytest

from fahmi2.core.slugify import slugify_anchor
from fahmi2.domain.enums import ExportFormat
from fahmi2.infra.export.markdown_pdf import (
    EXTENSION_BY_FORMAT,
    _normalize_for_pdf,
    pdf_fonts_available,
    render_markdown_to_html,
    render_markdown_to_pdf,
)

_TABLE_MD = "# Glossaire\n\n| Terme | Définition |\n|---|---|\n| ROI | Rentabilité |\n"
_TOC_MD = (
    "# Cours\n\n## Sommaire\n\n1. [Chapitre un](#1-chapitre-un)\n\n"
    "# 1. Chapitre un\n\nTexte.\n"
)


def test_extension_by_format() -> None:
    assert EXTENSION_BY_FORMAT[ExportFormat.MARKDOWN] == ".md"
    assert EXTENSION_BY_FORMAT[ExportFormat.PDF] == ".pdf"
    assert EXTENSION_BY_FORMAT[ExportFormat.HTML] == ".html"
    assert ExportFormat.APKG not in EXTENSION_BY_FORMAT


@pytest.mark.skipif(not pdf_fonts_available(), reason="Police Unicode indisponible")
def test_render_pdf_unicode(tmp_path: Path) -> None:
    out = tmp_path / "doc.pdf"
    render_markdown_to_pdf(
        "# Flashcards — Glossaire\n\nTexte… « x », **gras**, *ital*, éàç, ×, ≤.\n",
        out,
    )
    assert out.exists()
    assert out.read_bytes()[:5] == b"%PDF-"


@pytest.mark.skipif(not pdf_fonts_available(), reason="Police Unicode indisponible")
def test_render_pdf_handles_hr_and_lists(tmp_path: Path) -> None:
    out = tmp_path / "doc2.pdf"
    render_markdown_to_pdf("### Q\n\nR\n\n---\n\n- a\n- b\n", out)
    assert out.exists()


def test_render_html_renders_tables(tmp_path: Path) -> None:
    out = tmp_path / "doc.html"
    render_markdown_to_html(_TABLE_MD, out)
    content = out.read_text(encoding="utf-8")
    assert "<table>" in content
    assert "<td>ROI</td>" in content


def test_render_html_toc_links_are_clickable(tmp_path: Path) -> None:
    # L'ancre du sommaire (générée comme phase 5) et l'id du titre (extension toc)
    # doivent coïncider → le sommaire est cliquable.
    title = "Analyse financière : un levier"
    anchor = slugify_anchor(f"1. {title}")
    md = f"# Cours\n\n## Sommaire\n\n1. [{title}](#{anchor})\n\n# 1. {title}\n\nTexte.\n"
    out = tmp_path / "conso.html"
    render_markdown_to_html(md, out)
    content = out.read_text(encoding="utf-8")
    assert f'href="#{anchor}"' in content
    assert f'id="{anchor}"' in content


@pytest.mark.skipif(not pdf_fonts_available(), reason="Police Unicode indisponible")
def test_render_pdf_handles_internal_anchor_links(tmp_path: Path) -> None:
    # Le sommaire du consolidé contient des liens `[texte](#ancre)` : xhtml2pdf
    # les rend en liens internes cliquables (pas de crash).
    out = tmp_path / "toc.pdf"
    render_markdown_to_pdf(_TOC_MD, out)
    assert out.exists()
    assert out.read_bytes()[:5] == b"%PDF-"


@pytest.mark.skipif(not pdf_fonts_available(), reason="Police Unicode indisponible")
def test_render_pdf_renders_table(tmp_path: Path) -> None:
    out = tmp_path / "tbl.pdf"
    render_markdown_to_pdf(_TABLE_MD, out)
    assert out.exists()
    assert out.read_bytes()[:5] == b"%PDF-"


@pytest.mark.skipif(not pdf_fonts_available(), reason="Police Unicode indisponible")
def test_render_pdf_landscape_with_column_widths(tmp_path: Path) -> None:
    # Glossaire : paysage + largeurs de colonnes (ne doit pas planter).
    out = tmp_path / "gloss.pdf"
    render_markdown_to_pdf(
        _TABLE_MD,
        out,
        landscape=True,
        table_column_widths=("40%", "60%"),
    )
    assert out.exists()
    assert out.read_bytes()[:5] == b"%PDF-"


def test_normalize_for_pdf_maps_unrendered_dashes() -> None:
    # U+2010/2011/2012 -> "-", U+2015 -> em-dash, soft hyphen retiré.
    assert _normalize_for_pdf("a‐b‑c‒d") == "a-b-c-d"
    assert _normalize_for_pdf("x―y") == "x—y"
    assert _normalize_for_pdf("mot­coupe") == "motcoupe"
    # Em-dash (—) et en-dash (–) sont conservés (rendus correctement).
    assert _normalize_for_pdf("a—b–c") == "a—b–c"
