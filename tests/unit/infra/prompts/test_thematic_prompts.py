"""Tests de rendu des prompts thématiques (défauts bundlés)."""

from __future__ import annotations

from fahmi2.infra.prompts.loader import PromptLoader


def test_fact_ledger_renders() -> None:
    out = PromptLoader().render(
        "phase_5_fact_ledger",
        output_language_label="français",
        structured_markdown="# Titre\nDu contenu.",
    )
    assert "RELEVÉ EXHAUSTIF" in out
    assert "Du contenu." in out


def test_thematic_plan_renders() -> None:
    out = PromptLoader().render(
        "phase_5_thematic_plan",
        output_language_label="français",
        elements_listing="s1#1 — un fait",
    )
    assert "PLAN THÉMATIQUE" in out
    assert "s1#1 — un fait" in out


def test_thematic_chapter_renders_with_style_directives() -> None:
    out = PromptLoader().render(
        "phase_5_thematic_chapter",
        output_language_label="français",
        style_label="académique",
        style_directives="ton sobre",
        chapter_title="Origines",
        elements_json='[{"id": "s1#1"}]',
    )
    assert "UN chapitre" in out
    assert "Origines" in out
    assert "académique" in out
    assert "ton sobre" in out


def test_thematic_chapter_renders_without_style_directives() -> None:
    out = PromptLoader().render(
        "phase_5_thematic_chapter",
        output_language_label="français",
        style_label="standard",
        style_directives="",
        chapter_title="Origines",
        elements_json="[]",
    )
    assert "Style : standard." in out
