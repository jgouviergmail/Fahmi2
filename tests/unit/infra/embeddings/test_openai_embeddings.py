"""Tests de OpenAIEmbeddingProvider (client OpenAI mocké)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from fahmi2.infra.embeddings.openai_adapter import OpenAIEmbeddingProvider


def _mock_client(vectors: list[list[float]]) -> Any:
    client = MagicMock()
    response = MagicMock()
    response.data = [MagicMock(embedding=vector) for vector in vectors]
    client.embeddings.create.return_value = response
    return client


def test_embed_documents_calls_api_and_parses() -> None:
    client = _mock_client([[0.1, 0.2], [0.3, 0.4]])
    provider = OpenAIEmbeddingProvider(api_key="dummy", client=client)
    vectors = provider.embed_documents(["a", "b"])
    assert vectors == [[0.1, 0.2], [0.3, 0.4]]
    call = client.embeddings.create.call_args
    assert call.kwargs["model"] == "text-embedding-3-small"
    assert call.kwargs["input"] == ["a", "b"]


def test_embed_query_returns_single_vector() -> None:
    client = _mock_client([[0.5, 0.6]])
    provider = OpenAIEmbeddingProvider(api_key="dummy", client=client)
    assert provider.embed_query("question") == [0.5, 0.6]


def test_embed_documents_empty_skips_api() -> None:
    client = MagicMock()
    provider = OpenAIEmbeddingProvider(api_key="dummy", client=client)
    assert provider.embed_documents([]) == []
    client.embeddings.create.assert_not_called()
