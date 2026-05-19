"""Tests des entités Term et Glossary."""

from dataclasses import FrozenInstanceError

import pytest

from fahmi2.domain.enums import Language
from fahmi2.domain.glossary import Glossary, Term
from fahmi2.domain.ids import VideoId


def test_term_minimal() -> None:
    t = Term(term="PIB", definition="produit intérieur brut")
    assert t.term == "PIB"
    assert t.definition == "produit intérieur brut"
    assert t.sources == ()
    assert t.aliases == ()
    assert t.cross_lang == {}


def test_term_with_sources_and_aliases() -> None:
    vid = VideoId.new()
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
