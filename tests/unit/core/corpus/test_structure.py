"""Tests du parseur de structure du document consolidé (chapitres + sections)."""

from __future__ import annotations

from fahmi2.core.corpus import parse_chapters, parse_sections

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


_SAMPLE = """# Titre global

## Résumé

Texte méta.

# 1. Premier chapitre

Intro chapitre 1.

## 1.1 Sous-section A

Corps A.

# 2. Deuxième chapitre

## 2.1 Sous-section B

### 2.1.1 Feuille profonde

Corps profond.
"""


def test_parse_sections_extrait_le_chemin_structurel() -> None:
    sections = parse_sections(_SAMPLE)
    paths = [s.section_path for s in sections]
    assert paths == [(1,), (1, 1), (2,), (2, 1), (2, 1, 1)]


def test_parse_sections_ignore_titre_global_et_sections_meta() -> None:
    titres = [s.title for s in parse_sections(_SAMPLE)]
    assert "Résumé" not in titres
    assert titres[0] == "Premier chapitre"


def test_parse_sections_niveau_et_corps_direct() -> None:
    feuille = parse_sections(_SAMPLE)[-1]
    assert feuille.level == 3
    assert feuille.section_path == (2, 1, 1)
    assert feuille.body_markdown == "Corps profond."


def test_parse_sections_ancre_inclut_le_numero() -> None:
    sous = parse_sections(_SAMPLE)[1]  # 1.1 Sous-section A
    assert sous.anchor == "11-sous-section-a"


def test_parse_sections_document_sans_rubrique_numerotee() -> None:
    assert parse_sections("# Titre\n\n## Résumé\n\ntexte") == ()
