"""Tests des entités Term et Glossary."""

from dataclasses import FrozenInstanceError

import pytest

from fahmi2.domain.enums import Language
from fahmi2.domain.glossary import (
    Glossary,
    Term,
    parse_glossary_master_terms,
    render_glossary_markdown_table,
)
from fahmi2.domain.ids import SourceId


def test_term_minimal() -> None:
    t = Term(term="PIB", definition="produit intérieur brut")
    assert t.term == "PIB"
    assert t.definition == "produit intérieur brut"
    assert t.sources == ()
    assert t.aliases == ()
    assert t.cross_lang == {}


def test_term_with_sources_and_aliases() -> None:
    vid = SourceId.new()
    t = Term(
        term="PIB",
        definition="produit intérieur brut",
        sources=(vid,),
        aliases=("Produit Intérieur Brut",),
        cross_lang={Language.EN: "GDP"},
    )
    assert t.sources == (vid,)
    assert t.aliases == ("Produit Intérieur Brut",)
    assert t.cross_lang[Language.EN] == "GDP"


def test_term_is_frozen() -> None:
    t = Term(term="X", definition="x")
    with pytest.raises(FrozenInstanceError):
        t.term = "Y"  # type: ignore[misc]


def test_glossary_empty() -> None:
    g = Glossary(language=Language.FR, terms=())
    assert g.language is Language.FR
    assert len(g) == 0
    assert list(g) == []


def test_glossary_with_terms() -> None:
    terms = (
        Term(term="PIB", definition="..."),
        Term(term="Inflation", definition="..."),
    )
    g = Glossary(language=Language.FR, terms=terms)
    assert len(g) == 2
    assert {t.term for t in g} == {"PIB", "Inflation"}


def test_glossary_find_returns_term_or_none() -> None:
    terms = (Term(term="PIB", definition="..."),)
    g = Glossary(language=Language.FR, terms=terms)
    assert g.find("PIB") is terms[0]
    assert g.find("XYZ") is None


def test_glossary_find_is_case_sensitive() -> None:
    terms = (Term(term="PIB", definition="..."),)
    g = Glossary(language=Language.FR, terms=terms)
    assert g.find("pib") is None


def test_glossary_with_added_term_returns_new_instance() -> None:
    g = Glossary(language=Language.FR, terms=())
    new = g.with_added_term(Term(term="PIB", definition="..."))
    assert len(g) == 0
    assert len(new) == 1


def test_glossary_is_iterable_multiple_times() -> None:
    terms = (Term(term="A", definition="a"), Term(term="B", definition="b"))
    g = Glossary(language=Language.FR, terms=terms)
    assert [t.term for t in g] == ["A", "B"]
    assert [t.term for t in g] == ["A", "B"]


def test_parse_master_terms_reads_all_fields() -> None:
    vid = SourceId.new()
    payload = {
        "terms": [
            {
                "term": "PIB",
                "definition": "produit intérieur brut",
                "acronym": "PIB",
                "acronym_expansion": "Produit Intérieur Brut",
                "aliases": ["Produit Intérieur Brut"],
                "sources": [vid.value],
                "cross_lang": {"en": "GDP"},
            },
            {"term": "Inflation", "definition": "hausse des prix"},
        ]
    }
    terms = parse_glossary_master_terms(payload)
    assert len(terms) == 2
    pib = terms[0]
    assert pib.term == "PIB"
    assert pib.acronym_expansion == "Produit Intérieur Brut"
    assert pib.aliases == ("Produit Intérieur Brut",)
    assert pib.cross_lang[Language.EN] == "GDP"
    assert pib.sources == (vid,)


def test_parse_master_terms_empty_payload() -> None:
    assert parse_glossary_master_terms({}) == ()
    assert parse_glossary_master_terms({"terms": []}) == ()


def test_render_table_french_headers_and_invariant_expansion() -> None:
    terms = parse_glossary_master_terms(
        {
            "terms": [
                {
                    "term": "Retour sur investissement",
                    "acronym": "ROI",
                    "acronym_expansion": "Return On Investment",
                    "definition": "Indicateur de rentabilité.",
                },
                {"term": "Inflation", "definition": "Hausse des prix."},
            ]
        }
    )
    md = render_glossary_markdown_table(
        title="Glossaire", language=Language.FR, terms=terms
    )
    assert md.startswith("# Glossaire")
    assert "| Terme | Acronyme | Signification | Définition |" in md
    assert "Return On Investment" in md  # expansion invariante
    assert "| Inflation |  |  | Hausse des prix. |" in md


def test_render_table_english_headers() -> None:
    terms = parse_glossary_master_terms(
        {"terms": [{"term": "GDP", "definition": "Gross domestic product."}]}
    )
    md = render_glossary_markdown_table(
        title="Glossary", language=Language.EN, terms=terms
    )
    assert md.startswith("# Glossary")
    assert "| Term | Acronym | Meaning | Definition |" in md
