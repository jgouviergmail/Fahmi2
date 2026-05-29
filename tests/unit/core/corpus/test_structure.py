"""Tests du parseur de chapitres du document consolidé."""

from __future__ import annotations

from fahmi2.core.corpus import parse_chapters

_DOC = """# Mon cours

## Résumé

Abstract...

## Introduction générale

Intro...

## Sommaire

- [1. Bases](#1-bases)

# 1. Bases

Contenu du chapitre 1.

## 1.1 Définitions

Texte.

# 2. Avancé

Contenu du chapitre 2.

## Conclusion générale

Fin.
"""


def test_parse_chapters_extracts_numbered_h1_only() -> None:
    chapters = parse_chapters(_DOC)
    assert [c.index for c in chapters] == [1, 2]
    assert [c.title for c in chapters] == ["Bases", "Avancé"]


def test_parse_chapters_body_and_anchor() -> None:
    chapters = parse_chapters(_DOC)
    assert "Contenu du chapitre 1." in chapters[0].body_markdown
    assert "## 1.1 Définitions" in chapters[0].body_markdown
    assert chapters[0].anchor == "1-bases"


def test_parse_chapters_empty_when_no_chapter() -> None:
    assert parse_chapters("# Titre\n\n## Résumé\n\ntexte\n") == ()
