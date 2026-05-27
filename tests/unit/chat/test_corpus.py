"""Tests du chargement et du découpage (chunking) du corpus."""

from __future__ import annotations

import json
from pathlib import Path

from fahmi2.chat.corpus import chunk_consolidated, load_corpus_chunks
from fahmi2.domain.enums import Language
from fahmi2.pedagogy.sources import consolidated_doc_path

_DOC = """# Mon cours

## Résumé

abstract

# 1. Bases

Paragraphe introductif du chapitre.

## 1.1 Définitions

Une définition importante ici.

# 2. Avancé

Contenu avancé.
"""


def test_chunk_consolidated_chapters_and_sections() -> None:
    chunks = chunk_consolidated(_DOC)
    assert {c.chapter_title for c in chunks} == {"Bases", "Avancé"}
    sections = {c.section_title for c in chunks}
    assert "1.1 Définitions" in sections
    assert any(c.anchor == "11-définitions" for c in chunks)
    assert all(c.origin == "consolidated" for c in chunks)


def test_chunk_ids_are_unique() -> None:
    chunks = chunk_consolidated(_DOC)
    ids = [c.chunk_id for c in chunks]
    assert len(ids) == len(set(ids))


def test_large_section_splits_into_multiple_chunks() -> None:
    big = "paragraphe répété. " * 400  # ~ 1900 tokens estimés
    doc = f"# T\n\n# 1. Gros\n\n{big}\n\n{big}\n"
    chunks = [c for c in chunk_consolidated(doc) if c.chapter_title == "Gros"]
    assert len(chunks) >= 2


def test_deep_headings_not_cited_as_sections() -> None:
    # Les titres ####+ (au-delà du plan, profondeur > 3) ne deviennent pas des
    # sections citables : leur contenu est rattaché à la section ### parente.
    doc = (
        "# T\n\n# 1. Chapitre\n\n## 1.1 Section\n\n### 1.1.1 Sous-section\n\n"
        "Texte de la sous-section.\n\n#### 5.2.1 Titre profond hérité\n\n"
        "Contenu profond à retrouver.\n"
    )
    chunks = chunk_consolidated(doc)
    titles = {c.section_title for c in chunks}
    assert "1.1.1 Sous-section" in titles
    assert "5.2.1 Titre profond hérité" not in titles  # ####+ jamais cité
    # …mais son contenu reste indexé (rattaché à la section parente).
    assert any("Contenu profond à retrouver" in c.text for c in chunks)


def test_code_fence_kept_intact_in_single_chunk() -> None:
    doc = "# T\n\n# 1. Code\n\nIntro.\n\n```python\na = 1\n\nb = 2\n```\n"
    code_chunks = [c for c in chunk_consolidated(doc) if "```" in c.text]
    assert len(code_chunks) == 1
    # le bloc de code (avec sa ligne vide interne) n'est pas scindé
    assert "a = 1" in code_chunks[0].text
    assert "b = 2" in code_chunks[0].text


def test_load_corpus_chunks_consolidated_and_glossary(tmp_path: Path) -> None:
    out_dir = tmp_path / "output"
    out_dir.mkdir()
    consolidated_doc_path(out_dir, Language.FR).write_text(_DOC, encoding="utf-8")
    (tmp_path / "glossary_master.json").write_text(
        json.dumps(
            {
                "terms": [
                    {
                        "term": "Produit intérieur brut",
                        "definition": "Mesure de la richesse produite.",
                        "acronym": "PIB",
                        "acronym_expansion": "Produit Intérieur Brut",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    chunks = load_corpus_chunks(
        generation_output_dir=out_dir,
        generation_dir=tmp_path,
        language=Language.FR,
    )
    glossary = [c for c in chunks if c.origin == "glossary"]
    assert len(glossary) == 1
    assert "PIB" in glossary[0].text
    assert glossary[0].chunk_id == "glossary::produit-intérieur-brut"
    assert any(c.chapter_title == "Bases" for c in chunks)


def test_load_corpus_chunks_empty_when_no_consolidated(tmp_path: Path) -> None:
    chunks = load_corpus_chunks(
        generation_output_dir=tmp_path / "missing",
        generation_dir=tmp_path,
        language=Language.FR,
    )
    assert chunks == ()


def test_corpus_glossary_chunks_use_localized_term_and_definition(tmp_path: Path) -> None:
    out_dir = tmp_path / "output"
    out_dir.mkdir()
    consolidated_doc_path(out_dir, Language.EN).write_text(
        "# Cours\n\n## Intro\n\nx\n", encoding="utf-8"
    )
    (tmp_path / "glossary_master.json").write_text(
        json.dumps(
            {
                "terms": [
                    {
                        "term": "Bilan",
                        "definition": "doc comptable",
                        "cross_lang": {
                            "en": {
                                "term": "Balance sheet",
                                "definition": "accounting statement",
                            }
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    chunks = load_corpus_chunks(
        generation_output_dir=out_dir, generation_dir=tmp_path, language=Language.EN
    )
    glossary = [c for c in chunks if c.origin == "glossary"]
    # Terme **et** définition localisés ; ni la forme ni la définition source ne subsistent.
    assert any(
        "Balance sheet" in c.text and "accounting statement" in c.text for c in glossary
    )
    assert not any("Bilan" in c.text or "doc comptable" in c.text for c in glossary)
