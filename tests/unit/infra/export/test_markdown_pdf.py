"""Tests du rendu PDF et de la table d'extensions de format."""

from __future__ import annotations

import io
import unicodedata
from pathlib import Path
from typing import Any, cast

import pytest
from pypdf import PdfReader

from fahmi2.core.errors.exceptions import ConfigError
from fahmi2.core.slugify import slugify_anchor
from fahmi2.domain.enums import ExportFormat, Language
from fahmi2.infra.export import markdown_pdf
from fahmi2.infra.export.markdown_pdf import (
    EXTENSION_BY_FORMAT,
    _normalize_for_pdf,
    cjk_font_available,
    pdf_fonts_available,
    render_markdown_to_html,
    render_markdown_to_pdf,
)


def _embedded_font_bases(pdf_bytes: bytes) -> list[str]:
    """Noms de police (``/BaseFont``) référencés dans la 1ʳᵉ page d'un PDF."""
    reader = PdfReader(io.BytesIO(pdf_bytes))
    resources = cast("dict[str, Any]", reader.pages[0]["/Resources"])
    fonts = cast("dict[str, Any]", resources["/Font"])
    return [str(value.get_object().get("/BaseFont")) for value in fonts.values()]


_TABLE_MD = "# Glossaire\n\n| Terme | Définition |\n|---|---|\n| ROI | Rentabilité |\n"
_TOC_MD = (
    "# Cours\n\n## Sommaire\n\n1. [Chapitre un](#1-chapitre-un)\n\n"
    "# 1. Chapitre un\n\nTexte.\n"
)


def test_extension_by_format() -> None:
    assert EXTENSION_BY_FORMAT[ExportFormat.MARKDOWN] == ".md"
    assert EXTENSION_BY_FORMAT[ExportFormat.PDF] == ".pdf"
    assert EXTENSION_BY_FORMAT[ExportFormat.HTML] == ".html"
    assert EXTENSION_BY_FORMAT[ExportFormat.DOCX] == ".docx"
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


@pytest.mark.skipif(not pdf_fonts_available(), reason="Police Unicode indisponible")
def test_strip_unrenderable_removes_emoji_keeps_text() -> None:
    markdown_pdf._ensure_pdf_fonts_registered()
    # 📖 (U+1F4D6) absent d'Arial → retiré ; le texte reste intact.
    result = markdown_pdf._strip_unrenderable_for_pdf(
        "📖 Définition — états financiers", markdown_pdf._PDF_FONT_REGULAR
    )
    assert "📖" not in result
    assert "Définition — états financiers" in result


@pytest.mark.skipif(not pdf_fonts_available(), reason="Police Unicode indisponible")
def test_strip_unrenderable_keeps_format_and_whitespace() -> None:
    markdown_pdf._ensure_pdf_fonts_registered()
    # U+E0001 (LANGUAGE TAG, catégorie Cf) : absent de la police mais conservé
    # (garde-fou format/bidi) ; espaces et sauts de ligne préservés.
    assert unicodedata.category("\U000e0001") == "Cf"
    text = "a\U000e0001 b\nc"
    result = markdown_pdf._strip_unrenderable_for_pdf(text, markdown_pdf._PDF_FONT_REGULAR)
    assert result == text


@pytest.mark.skipif(not pdf_fonts_available(), reason="Police Unicode indisponible")
def test_render_pdf_strips_emoji_without_crash(tmp_path: Path) -> None:
    # Un bandeau « 📖 Définition » ne doit pas faire planter le rendu ni laisser de
    # carré : l'émoji est absent du texte extrait du PDF.
    out = tmp_path / "emoji.pdf"
    render_markdown_to_pdf("# Cours\n\n> 📖 **Définition** — un terme.\n", out)
    pdf = out.read_bytes()
    assert pdf[:5] == b"%PDF-"
    text = PdfReader(io.BytesIO(pdf)).pages[0].extract_text()
    assert "📖" not in text
    assert "Définition" in text


@pytest.mark.skipif(not cjk_font_available(), reason="Police CJK indisponible")
def test_render_pdf_chinese_embeds_cjk_font(tmp_path: Path) -> None:
    out = tmp_path / "zh.pdf"
    render_markdown_to_pdf(
        "# 第一章 机器学习\n\n这是中文测试段落。\n", out, language=Language.ZH
    )
    pdf = out.read_bytes()
    assert pdf[:5] == b"%PDF-"
    # La police CJK (Microsoft YaHei) est embarquée (sous-ensemble).
    assert any("YaHei" in base for base in _embedded_font_bases(pdf))


@pytest.mark.skipif(not pdf_fonts_available(), reason="Police Unicode indisponible")
def test_render_pdf_arabic_is_shaped(tmp_path: Path) -> None:
    out = tmp_path / "ar.pdf"
    render_markdown_to_pdf("مرحبا بالعالم هذا اختبار\n", out, language=Language.AR)
    pdf = out.read_bytes()
    assert pdf[:5] == b"%PDF-"
    text = PdfReader(io.BytesIO(pdf)).pages[0].extract_text()
    # Lettres arabes liées => formes de présentation U+FE70..U+FEFF (shaping).
    assert any(0xFE70 <= ord(ch) <= 0xFEFF for ch in text)


def test_render_pdf_chinese_raises_without_cjk_font(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(markdown_pdf, "_cjk_font_path", lambda: Path("nonexistent.ttc"))
    markdown_pdf._ensure_cjk_font_registered.cache_clear()
    with pytest.raises(ConfigError) as excinfo:
        render_markdown_to_pdf("# 测试\n", tmp_path / "x.pdf", language=Language.ZH)
    assert excinfo.value.code == "EXPORT.NO_CJK_FONT"
    markdown_pdf._ensure_cjk_font_registered.cache_clear()
