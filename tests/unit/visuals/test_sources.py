"""Tests du chargement des sources des Visualisations."""

from __future__ import annotations

import json
from pathlib import Path

from fahmi2.domain.enums import Language
from fahmi2.visuals._constants import MAX_UNIT_CHARS
from fahmi2.visuals.sources import load_glossary_master_terms, load_text_units

_ENCODING = "utf-8"


def _write(path: Path, text: str) -> None:
    path.write_text(text, encoding=_ENCODING)


def test_load_text_units_doc_absent(tmp_path: Path) -> None:
    assert load_text_units(tmp_path, Language.FR) == ()


def test_load_text_units_filtre_meta_et_sections_courtes(tmp_path: Path) -> None:
    doc = (
        "# Titre global\n\n"
        "## Résumé\n\n"
        "Section méta, pas de numéro : doit être ignorée même si assez longue "
        "pour dépasser le seuil minimal de corps exploitable.\n\n"
        "# 1. Premier chapitre\n\n"
        "Corps de chapitre assez long pour être retenu comme unité de texte "
        "exploitable par l'extraction sémantique des Visualisations.\n\n"
        "## 1.1 Trop court\n\n"
        "minus\n"
    )
    _write(tmp_path / "consolidated.fr.md", doc)
    units = load_text_units(tmp_path, Language.FR)
    paths = [u.section_path for u in units]
    assert paths == [(1,)]  # méta ignorée, sous-section trop courte ignorée
    assert units[0].title == "Premier chapitre"
    assert units[0].part == 0


def test_load_text_units_fragmente_les_sections_longues(tmp_path: Path) -> None:
    paragraph = "phrase de contenu. " * 120  # ~2280 caractères
    long_body = "\n\n".join([paragraph] * 4)  # ~9000 caractères > MAX_UNIT_CHARS
    assert len(long_body) > MAX_UNIT_CHARS
    doc = f"# 1. Chapitre volumineux\n\n{long_body}\n"
    _write(tmp_path / "consolidated.fr.md", doc)
    units = load_text_units(tmp_path, Language.FR)
    assert len(units) >= 2
    assert {u.section_path for u in units} == {(1,)}
    assert [u.part for u in units] == list(range(1, len(units) + 1))
    assert all(len(u.text) <= MAX_UNIT_CHARS for u in units)


def test_load_glossary_master_terms(tmp_path: Path) -> None:
    payload = {
        "terms": [
            {"term": "Bilan", "definition": "Photo du patrimoine.",
             "aliases": [], "sources": []},
        ]
    }
    _write(tmp_path / "glossary_master.json", json.dumps(payload))
    terms = load_glossary_master_terms(tmp_path)
    assert len(terms) == 1
    assert terms[0].term == "Bilan"


def test_load_glossary_master_terms_absent(tmp_path: Path) -> None:
    assert load_glossary_master_terms(tmp_path) == ()
