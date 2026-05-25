"""Tests de la fabrique de retriever (résolution AUTO + repli)."""

from __future__ import annotations

from pathlib import Path

from fahmi2.chat.query_expander import QueryExpander
from fahmi2.chat.retriever_factory import build_passage_retriever
from fahmi2.core.retrieval.passages import TfidfPassageRetriever
from fahmi2.domain.chat import ChatSettings, CorpusChunk
from fahmi2.domain.enums import Language, RetrievalStrategy
from fahmi2.infra.embeddings._fakes import FakeEmbeddingProvider
from fahmi2.infra.llm._fakes import FakeLLMProvider
from fahmi2.infra.prompts.loader import PromptLoader
from fahmi2.infra.retrieval.semantic import SemanticPassageRetriever
from fahmi2.infra.storage.fs_artifacts import FsArtifactStore

_CHUNKS = (
    CorpusChunk(
        chunk_id="1",
        chapter_title="C",
        section_title="S",
        anchor="1",
        text="produit intérieur brut",
        origin="consolidated",
    ),
)


def _build(
    tmp_path: Path,
    *,
    settings: ChatSettings,
    provider: FakeEmbeddingProvider | None,
) -> object:
    return build_passage_retriever(
        chunks=_CHUNKS,
        settings=settings,
        prompts=PromptLoader(),
        llm=FakeLLMProvider(),
        embedding_provider=provider,
        embedding_model="fake",
        index_path=tmp_path / "index.npz",
        source_mtime_ns=1,
        language=Language.FR,
        artifacts=FsArtifactStore(),
    )


def test_auto_with_provider_is_semantic(tmp_path: Path) -> None:
    retriever = _build(
        tmp_path,
        settings=ChatSettings(retrieval_strategy=RetrievalStrategy.AUTO),
        provider=FakeEmbeddingProvider(),
    )
    assert isinstance(retriever, SemanticPassageRetriever)


def test_auto_without_provider_is_lexical(tmp_path: Path) -> None:
    retriever = _build(
        tmp_path,
        settings=ChatSettings(
            retrieval_strategy=RetrievalStrategy.AUTO, query_expansion_enabled=False
        ),
        provider=None,
    )
    assert isinstance(retriever, TfidfPassageRetriever)


def test_semantic_without_provider_falls_back_to_lexical(tmp_path: Path) -> None:
    retriever = _build(
        tmp_path,
        settings=ChatSettings(
            retrieval_strategy=RetrievalStrategy.SEMANTIC, query_expansion_enabled=False
        ),
        provider=None,
    )
    assert isinstance(retriever, TfidfPassageRetriever)


def test_lexical_with_expansion_is_wrapped(tmp_path: Path) -> None:
    retriever = _build(
        tmp_path,
        settings=ChatSettings(
            retrieval_strategy=RetrievalStrategy.LEXICAL, query_expansion_enabled=True
        ),
        provider=None,
    )
    assert isinstance(retriever, QueryExpander)
