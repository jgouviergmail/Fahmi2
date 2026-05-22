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
