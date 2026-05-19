"""Tests de l'interface GlossaryRetriever et de son implémentation triviale."""

from fahmi2.core.retrieval.interface import GlossaryRetriever, PassthroughRetriever


def test_passthrough_returns_all_terms_unchanged() -> None:
    retriever = PassthroughRetriever()
    terms = ["alpha", "beta", "gamma"]
    result = retriever.retrieve(query="anything", terms=terms, top_k=10)
    assert result == terms


def test_passthrough_respects_top_k() -> None:
    retriever = PassthroughRetriever()
    terms = ["alpha", "beta", "gamma"]
    result = retriever.retrieve(query="anything", terms=terms, top_k=2)
    assert result == ["alpha", "beta"]


def test_passthrough_handles_empty() -> None:
    retriever = PassthroughRetriever()
    result = retriever.retrieve(query="x", terms=[], top_k=10)
    assert result == []


def test_passthrough_returns_new_list_not_reference() -> None:
    retriever = PassthroughRetriever()
    terms = ["alpha", "beta"]
    result = retriever.retrieve(query="x", terms=terms, top_k=10)
    assert result is not terms


def test_passthrough_satisfies_protocol() -> None:
    retriever: GlossaryRetriever = PassthroughRetriever()
    _ = retriever.retrieve(query="x", terms=["y"], top_k=1)
