"""Tests de DeepSeekAdapter (client OpenAI mocké)."""

from typing import Any
from unittest.mock import MagicMock

import pytest
from openai import AuthenticationError, RateLimitError

import fahmi2.infra.llm.deepseek_adapter as deepseek_mod
from fahmi2.core.errors.exceptions import LLMError
from fahmi2.infra.llm.deepseek_adapter import (
    _REQUEST_TIMEOUT_SECONDS,
    DeepSeekAdapter,
    _parse_chat_response,
)
from fahmi2.infra.llm.interface import Message


def _chat_payload(
    *,
    content: str = "hi",
    reasoning: str | None = None,
    prompt_tokens: int = 100,
    completion_tokens: int = 30,
    cached: int = 0,
) -> dict[str, Any]:
    message: dict[str, Any] = {"content": content}
    if reasoning is not None:
        message["reasoning_content"] = reasoning
    return {
        "choices": [{"message": message}],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "prompt_cache_hit_tokens": cached,
        },
    }


def test_parse_chat_response_basic() -> None:
    response = _parse_chat_response(
        _chat_payload(content="hello", prompt_tokens=200, completion_tokens=50),
        "deepseek-v4-flash",
    )
    assert response.content == "hello"
    assert response.thinking_content is None
    assert response.prompt_tokens == 200
    assert response.completion_tokens == 50
    assert response.cached_prompt_tokens == 0
    assert response.cost_usd > 0


def test_parse_chat_response_with_reasoning() -> None:
    response = _parse_chat_response(
        _chat_payload(content="answer", reasoning="step1\nstep2"),
        "deepseek-v4-flash",
    )
    assert response.thinking_content == "step1\nstep2"


def test_parse_chat_response_with_cached_tokens() -> None:
    response = _parse_chat_response(
        _chat_payload(prompt_tokens=200, completion_tokens=0, cached=150),
        "deepseek-v4-flash",
    )
    assert response.cached_prompt_tokens == 150
    # 150 tokens at cache hit + 50 at miss
    expected_cost = (150 * 0.0028 + 50 * 0.14) / 1_000_000
    assert response.cost_usd == pytest.approx(expected_cost)


def test_chat_invokes_client_with_messages() -> None:
    mock_client = MagicMock()
    response_mock = MagicMock()
    response_mock.model_dump.return_value = _chat_payload()
    mock_client.chat.completions.create.return_value = response_mock

    adapter = DeepSeekAdapter(api_key="dummy", client=mock_client)
    adapter.chat(
        messages=[Message(role="system", content="s"), Message(role="user", content="u")],
        model="deepseek-v4-flash",
        thinking=False,
        temperature=0.3,
    )
    call = mock_client.chat.completions.create.call_args
    assert call.kwargs["model"] == "deepseek-v4-flash"
    assert call.kwargs["messages"] == [
        {"role": "system", "content": "s"},
        {"role": "user", "content": "u"},
    ]
    assert call.kwargs["temperature"] == 0.3
    # extra_body est toujours présent (au minimum thinking.type=disabled)
    assert call.kwargs["extra_body"] == {"thinking": {"type": "disabled"}}


def test_chat_thinking_enabled_sends_correct_extra_body() -> None:
    mock_client = MagicMock()
    response_mock = MagicMock()
    response_mock.model_dump.return_value = _chat_payload()
    mock_client.chat.completions.create.return_value = response_mock

    adapter = DeepSeekAdapter(api_key="dummy", client=mock_client)
    adapter.chat(
        messages=[Message(role="user", content="u")],
        model="deepseek-v4-flash",
        thinking=True,
        temperature=0.3,
    )
    call = mock_client.chat.completions.create.call_args
    assert call.kwargs["extra_body"] == {"thinking": {"type": "enabled"}}


def test_chat_thinking_disabled_sends_disabled_extra_body() -> None:
    mock_client = MagicMock()
    response_mock = MagicMock()
    response_mock.model_dump.return_value = _chat_payload()
    mock_client.chat.completions.create.return_value = response_mock

    adapter = DeepSeekAdapter(api_key="dummy", client=mock_client)
    adapter.chat(
        messages=[Message(role="user", content="u")],
        model="deepseek-v4-flash",
        thinking=False,
        temperature=0.3,
    )
    call = mock_client.chat.completions.create.call_args
    assert call.kwargs["extra_body"] == {"thinking": {"type": "disabled"}}


def test_chat_reasoning_effort_sent_only_when_thinking_enabled() -> None:
    mock_client = MagicMock()
    response_mock = MagicMock()
    response_mock.model_dump.return_value = _chat_payload()
    mock_client.chat.completions.create.return_value = response_mock

    adapter = DeepSeekAdapter(api_key="dummy", client=mock_client)
    adapter.chat(
        messages=[Message(role="user", content="u")],
        model="deepseek-v4-flash",
        thinking=True,
        reasoning_effort="max",
        temperature=0.3,
    )
    call = mock_client.chat.completions.create.call_args
    assert call.kwargs["extra_body"] == {
        "thinking": {"type": "enabled"},
        "reasoning_effort": "max",
    }


def test_chat_reasoning_effort_ignored_when_thinking_disabled() -> None:
    mock_client = MagicMock()
    response_mock = MagicMock()
    response_mock.model_dump.return_value = _chat_payload()
    mock_client.chat.completions.create.return_value = response_mock

    adapter = DeepSeekAdapter(api_key="dummy", client=mock_client)
    adapter.chat(
        messages=[Message(role="user", content="u")],
        model="deepseek-v4-flash",
        thinking=False,
        reasoning_effort="max",
        temperature=0.3,
    )
    call = mock_client.chat.completions.create.call_args
    assert call.kwargs["extra_body"] == {"thinking": {"type": "disabled"}}


def test_chat_passes_max_tokens_when_specified() -> None:
    mock_client = MagicMock()
    response_mock = MagicMock()
    response_mock.model_dump.return_value = _chat_payload()
    mock_client.chat.completions.create.return_value = response_mock

    adapter = DeepSeekAdapter(api_key="dummy", client=mock_client)
    adapter.chat(
        messages=[Message(role="user", content="u")],
        model="deepseek-v4-flash",
        thinking=False,
        temperature=0.3,
        max_tokens=500,
    )
    assert mock_client.chat.completions.create.call_args.kwargs["max_tokens"] == 500


def test_chat_maps_auth_error() -> None:
    mock_client = MagicMock()
    response_mock = MagicMock()
    response_mock.request = MagicMock()
    mock_client.chat.completions.create.side_effect = AuthenticationError(
        message="bad", response=response_mock, body=None
    )
    adapter = DeepSeekAdapter(api_key="dummy", client=mock_client)
    with pytest.raises(LLMError) as exc_info:
        adapter.chat(
            messages=[Message(role="user", content="u")],
            model="deepseek-v4-flash",
            thinking=False,
            temperature=0.3,
        )
    assert exc_info.value.code == "LLM.AUTH_INVALID"


def test_chat_maps_rate_limit_error() -> None:
    mock_client = MagicMock()
    response_mock = MagicMock()
    response_mock.request = MagicMock()
    mock_client.chat.completions.create.side_effect = RateLimitError(
        message="429", response=response_mock, body=None
    )
    adapter = DeepSeekAdapter(api_key="dummy", client=mock_client)
    with pytest.raises(LLMError) as exc_info:
        adapter.chat(
            messages=[Message(role="user", content="u")],
            model="deepseek-v4-flash",
            thinking=False,
            temperature=0.3,
        )
    assert exc_info.value.code == "LLM.RATE_LIMIT"


def test_estimate_cost_delegates_to_pricing() -> None:
    adapter = DeepSeekAdapter(api_key="dummy", client=MagicMock())
    cost = adapter.estimate_cost(
        prompt_tokens=1_000_000,
        completion_tokens=0,
        model="deepseek-v4-flash",
        thinking=False,
    )
    assert cost == pytest.approx(0.14)


def test_client_is_created_with_explicit_timeout(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    def _fake_openai(**kwargs: Any) -> object:
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(deepseek_mod, "OpenAI", _fake_openai)
    DeepSeekAdapter(api_key="k")
    assert captured["timeout"] == _REQUEST_TIMEOUT_SECONDS
