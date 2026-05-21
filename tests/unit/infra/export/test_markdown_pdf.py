"""Tests de l'assemblage Markdown et du rendu PDF."""

from __future__ import annotations

from pathlib import Path

import pytest

from fahmi2.infra.export.markdown_pdf import (
    assemble_markdown,
    pdf_fonts_available,
    render_markdown_to_pdf,
)


def test_assemble_markdown_joins_bodies() -> None:
    out = assemble_markdown("Titre", ("# A\n\ncorps a", "# B\n\ncorps b"))
    assert out.startswith("# Titre")
    assert "# A" in out
    assert "# B" in out
    assert "---" in out


def test_assemble_markdown_empty() -> None:
    out = assemble_markdown("Titre", ())
    assert out.startswith("# Titre")


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
