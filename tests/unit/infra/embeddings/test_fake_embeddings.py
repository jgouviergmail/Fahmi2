"""Tests du FakeEmbeddingProvider (déterministe, sans réseau)."""

from __future__ import annotations

from fahmi2.infra.embeddings._fakes import FakeEmbeddingProvider


def test_deterministic_and_same_dimension() -> None:
    provider = FakeEmbeddingProvider()
    first = provider.embed_query("le pib mesure la richesse")
    second = provider.embed_query("le pib mesure la richesse")
    assert first == second
    docs = provider.embed_documents(["a b c", "d e"])
    assert len(docs) == 2
    assert len(docs[0]) == len(docs[1])


def test_shared_vocabulary_is_closer() -> None:
    provider = FakeEmbeddingProvider()
    base = provider.embed_query("produit intérieur brut richesse")
    close = provider.embed_query("produit intérieur brut")
    far = provider.embed_query("photosynthèse lumière énergie")

    def _dot(a: list[float], b: list[float]) -> float:
        return sum(x * y for x, y in zip(a, b, strict=True))

    assert _dot(base, close) > _dot(base, far)
