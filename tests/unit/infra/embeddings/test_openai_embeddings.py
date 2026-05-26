"""Tests de OpenAIEmbeddingProvider (client OpenAI mocké)."""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

import pytest
from openai import AuthenticationError

from fahmi2.core.errors.exceptions import EmbeddingError
from fahmi2.infra.embeddings.openai_adapter import OpenAIEmbeddingProvider


def _mock_client(vectors: list[list[float]], *, total_tokens: int = 0) -> Any:
    client = MagicMock()
    response = MagicMock()
    response.data = [MagicMock(embedding=vector) for vector in vectors]
    response.usage.total_tokens = total_tokens
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


def test_embed_documents_maps_auth_error_to_typed_error() -> None:
    # Homogénéité avec les adapters STT/LLM : une exception OpenAI devient une
    # erreur typée FR (au lieu de remonter brute).
    client = MagicMock()
    response_mock = MagicMock()
    response_mock.request = MagicMock()
    client.embeddings.create.side_effect = AuthenticationError(
        message="bad key", response=response_mock, body=None
    )
    provider = OpenAIEmbeddingProvider(api_key="dummy", client=client)
    with pytest.raises(EmbeddingError) as exc_info:
        provider.embed_documents(["x"])
    assert exc_info.value.code == "EMBEDDING.AUTH_INVALID"


def test_consumed_cost_usd_reflects_usage() -> None:
    client = _mock_client([[0.1, 0.2]], total_tokens=1_000_000)
    provider = OpenAIEmbeddingProvider(
        api_key="dummy", client=client, model="text-embedding-3-small"
    )
    provider.embed_documents(["x"])
    assert provider.consumed_cost_usd() == pytest.approx(0.02)
