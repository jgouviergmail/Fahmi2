"""Tests du streaming factice (FakeLLMProvider.chat_stream)."""

from __future__ import annotations

from fahmi2.infra.llm._fakes import FakeLLMProvider
from fahmi2.infra.llm.interface import LLMResponse, Message


def _response(content: str) -> LLMResponse:
    return LLMResponse(
        content=content,
        thinking_content=None,
        prompt_tokens=10,
        completion_tokens=5,
        cached_prompt_tokens=0,
        cost_usd=0.01,
    )


def test_chat_stream_yields_deltas_then_final() -> None:
    provider = FakeLLMProvider(default_response=_response("Le PIB mesure tout"))
    chunks = list(
        provider.chat_stream(
            messages=[Message(role="user", content="q")],
            model="deepseek-v4-flash",
            thinking=False,
            temperature=0.3,
        )
    )
    deltas = "".join(c.content_delta for c in chunks if not c.is_final)
    assert deltas == "Le PIB mesure tout"
    final = chunks[-1]
    assert final.is_final is True
    assert final.response is not None
    assert final.response.cost_usd == 0.01
