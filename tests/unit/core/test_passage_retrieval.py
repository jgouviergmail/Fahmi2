"""Tests du retrieval de passages (TF-IDF lexical)."""

from __future__ import annotations

from fahmi2.core.retrieval.passages import TfidfPassageRetriever
from fahmi2.domain.chat import CorpusChunk


def _chunk(chunk_id: str, text: str) -> CorpusChunk:
    return CorpusChunk(
        chunk_id=chunk_id,
        chapter_title="C",
        section_title="S",
        anchor="a",
        text=text,
        origin="consolidated",
    )


def test_retrieves_most_relevant_first() -> None:
    chunks = (
        _chunk("1", "Le produit intérieur brut mesure la richesse produite."),
        _chunk("2", "La photosynthèse transforme la lumière en énergie."),
    )
    results = TfidfPassageRetriever(chunks).retrieve(
        query="la richesse produite et le produit intérieur", top_k=2
    )
    assert results[0].chunk.chunk_id == "1"
    assert len(results) == 2


def test_empty_corpus_returns_empty() -> None:
    assert TfidfPassageRetriever(()).retrieve(query="x", top_k=3) == []


def test_blank_query_returns_empty() -> None:
    chunks = (_chunk("1", "texte"),)
    assert TfidfPassageRetriever(chunks).retrieve(query="   ", top_k=3) == []


def test_respects_top_k() -> None:
    chunks = tuple(_chunk(str(i), f"texte {i} économie marché") for i in range(5))
    results = TfidfPassageRetriever(chunks).retrieve(query="économie", top_k=2)
    assert len(results) == 2
