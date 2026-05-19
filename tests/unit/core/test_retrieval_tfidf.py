"""Tests du TfidfGlossaryRetriever."""

from fahmi2.core.retrieval.interface import GlossaryRetriever
from fahmi2.core.retrieval.tfidf import TfidfGlossaryRetriever


def test_retriever_satisfies_protocol() -> None:
    r: GlossaryRetriever = TfidfGlossaryRetriever()
    _ = r.retrieve(query="x", terms=["y"], top_k=1)


def test_retrieve_returns_relevant_term_first() -> None:
    r = TfidfGlossaryRetriever()
    terms = ["produit intérieur brut", "inflation", "marché financier"]
    result = r.retrieve(
        query="Le PIB nominal et le PIB réel mesurent le produit intérieur brut.",
        terms=terms,
        top_k=2,
    )
    assert result[0] == "produit intérieur brut"


def test_retrieve_respects_top_k() -> None:
    r = TfidfGlossaryRetriever()
    terms = ["alpha", "beta", "gamma", "delta", "epsilon"]
    result = r.retrieve(query="alpha beta gamma", terms=terms, top_k=2)
    assert len(result) <= 2


def test_retrieve_handles_empty_terms() -> None:
    r = TfidfGlossaryRetriever()
    assert r.retrieve(query="anything", terms=[], top_k=10) == []


def test_retrieve_handles_empty_query() -> None:
    r = TfidfGlossaryRetriever()
    terms = ["alpha", "beta"]
    result = r.retrieve(query="", terms=terms, top_k=10)
    # Avec une query vide, on renvoie les premiers terms (fallback déterministe)
    assert set(result) <= set(terms)
    assert len(result) <= len(terms)


def test_retrieve_returns_all_when_top_k_exceeds() -> None:
    r = TfidfGlossaryRetriever()
    terms = ["alpha", "beta"]
    result = r.retrieve(query="alpha beta", terms=terms, top_k=100)
    assert set(result) == {"alpha", "beta"}


def test_retrieve_deterministic_for_identical_input() -> None:
    r = TfidfGlossaryRetriever()
    terms = ["alpha", "beta", "gamma"]
    r1 = r.retrieve(query="alpha gamma", terms=terms, top_k=3)
    r2 = r.retrieve(query="alpha gamma", terms=terms, top_k=3)
    assert r1 == r2
