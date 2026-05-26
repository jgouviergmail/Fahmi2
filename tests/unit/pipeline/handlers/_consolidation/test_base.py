"""Tests des helpers déterministes partagés de consolidation."""

from __future__ import annotations

from fahmi2.pipeline.handlers._consolidation._base import (
    ConsolidationResult,
    renumber_subheadings,
    strip_existing_numbering,
    subheadings_of,
)


def test_consolidation_result_carries_markdown_and_cost() -> None:
    res = ConsolidationResult(consolidated_markdown="# T\n", cost_usd=1.5)
    assert res.consolidated_markdown == "# T\n"
    assert res.cost_usd == 1.5


def test_strip_existing_numbering() -> None:
    assert strip_existing_numbering("1.2 Titre") == "Titre"
    assert strip_existing_numbering("1. Titre") == "Titre"
    assert strip_existing_numbering("Titre") == "Titre"


def test_renumber_subheadings_numbers_h2_h3() -> None:
    body = "## Alpha\ntexte\n### Beta\n"
    renumbered, subs = renumber_subheadings(body, 1)
    assert "## 1.1 Alpha" in renumbered
    assert "### 1.1.1 Beta" in renumbered
    assert [(s.level, s.number, s.title) for s in subs] == [
        (2, "1.1", "Alpha"),
        (3, "1.1.1", "Beta"),
    ]


def test_subheadings_of_parses_numbered_headings() -> None:
    subs = subheadings_of("## 1.1 Alpha\ntexte\n### 1.1.1 Beta\n")
    assert [(s.level, s.number, s.title) for s in subs] == [
        (2, "1.1", "Alpha"),
        (3, "1.1.1", "Beta"),
    ]


def test_subheadings_of_ignores_code_fences() -> None:
    body = "## 1.1 Réel\n```\n## pas un titre\n```\n"
    subs = subheadings_of(body)
    assert [s.title for s in subs] == ["Réel"]
