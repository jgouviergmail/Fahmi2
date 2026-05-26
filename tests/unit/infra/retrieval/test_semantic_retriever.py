"""Tests du SemanticPassageRetriever (index persisté + empreinte de validité)."""

from __future__ import annotations

from pathlib import Path

import pytest

from fahmi2.domain.chat import CorpusChunk
from fahmi2.domain.enums import Language
from fahmi2.infra.embeddings._fakes import FakeEmbeddingProvider
from fahmi2.infra.retrieval.semantic import (
    SemanticPassageRetriever,
    build_index_fingerprint,
    purge_index,
)
from fahmi2.infra.storage.fs_artifacts import FsArtifactStore


def _chunk(chunk_id: str, text: str) -> CorpusChunk:
    return CorpusChunk(
        chunk_id=chunk_id,
        chapter_title="C",
        section_title="S",
        anchor=chunk_id,
        text=text,
        origin="consolidated",
    )


class _CountingProvider(FakeEmbeddingProvider):
    """Fake comptant les appels d'indexation (embed_documents)."""

    def __init__(self) -> None:
        super().__init__()
        self.document_calls = 0

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        self.document_calls += 1
        return super().embed_documents(texts)


_CHUNKS = (
    _chunk("1", "produit intérieur brut richesse nationale agrégée"),
    _chunk("2", "photosynthèse lumière chlorophylle énergie"),
)


def _fingerprint(mtime: int) -> str:
    return build_index_fingerprint(
        model="fake", source_mtime_ns=mtime, language=Language.FR
    )


def test_retrieval_orders_by_similarity(tmp_path: Path) -> None:
    retriever = SemanticPassageRetriever(
        chunks=_CHUNKS,
        embedding_provider=FakeEmbeddingProvider(),
        index_path=tmp_path / "index.npz",
        fingerprint=_fingerprint(1),
        artifacts=FsArtifactStore(),
    )
    results = retriever.retrieve(query="produit intérieur brut richesse", top_k=2)
    assert results[0].chunk.chunk_id == "1"


def test_index_reused_when_fingerprint_matches(tmp_path: Path) -> None:
    provider = _CountingProvider()
    index_path = tmp_path / "index.npz"
    for _ in range(2):
        SemanticPassageRetriever(
            chunks=_CHUNKS,
            embedding_provider=provider,
            index_path=index_path,
            fingerprint=_fingerprint(1),
            artifacts=FsArtifactStore(),
        )
    assert provider.document_calls == 1  # 2e construction : index réutilisé


def test_index_rebuilt_when_fingerprint_changes(tmp_path: Path) -> None:
    provider = _CountingProvider()
    index_path = tmp_path / "index.npz"
    SemanticPassageRetriever(
        chunks=_CHUNKS,
        embedding_provider=provider,
        index_path=index_path,
        fingerprint=_fingerprint(1),
        artifacts=FsArtifactStore(),
    )
    SemanticPassageRetriever(
        chunks=_CHUNKS,
        embedding_provider=provider,
        index_path=index_path,
        fingerprint=_fingerprint(2),  # mtime changé → péremption
        artifacts=FsArtifactStore(),
    )
    assert provider.document_calls == 2


def test_consumed_cost_usd_tracks_embeddings(tmp_path: Path) -> None:
    provider = FakeEmbeddingProvider(cost_per_call=0.01)
    retriever = SemanticPassageRetriever(
        chunks=_CHUNKS,
        embedding_provider=provider,
        index_path=tmp_path / "index.npz",
        fingerprint=_fingerprint(1),
        artifacts=FsArtifactStore(),
    )  # indexation : 1 appel embed_documents
    retriever.retrieve(query="produit intérieur brut", top_k=2)  # +1 embed_query
    assert retriever.consumed_cost_usd() == pytest.approx(0.02)


def test_purge_index_removes_file(tmp_path: Path) -> None:
    index_path = tmp_path / "index.npz"
    SemanticPassageRetriever(
        chunks=_CHUNKS,
        embedding_provider=FakeEmbeddingProvider(),
        index_path=index_path,
        fingerprint=_fingerprint(1),
        artifacts=FsArtifactStore(),
    )
    assert index_path.exists()
    purge_index(index_path)
    assert not index_path.exists()
