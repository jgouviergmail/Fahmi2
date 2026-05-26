"""Tests du rendu de fragment Markdown inline (chat / aperçu de passage)."""

from __future__ import annotations

from fahmi2.infra.export.markdown_pdf import render_markdown_fragment


def test_renders_bold_and_list() -> None:
    rendered = render_markdown_fragment("Texte **gras**\n\n- a\n- b")
    assert "<strong>gras</strong>" in rendered
    assert "<li>a</li>" in rendered


def test_renders_table() -> None:
    rendered = render_markdown_fragment("| A | B |\n|---|---|\n| 1 | 2 |")
    assert "<table>" in rendered
