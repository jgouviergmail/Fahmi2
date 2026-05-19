"""Tests du FakeLLMProvider."""

import pytest

from fahmi2.core.errors.exceptions import LLMError
from fahmi2.core.errors.severity import Severity
from fahmi2.infra.llm._fakes import FakeLLMProvider, make_request_key
from fahmi2.infra.llm.interface import LLMProvider, LLMResponse, Message


def _msgs() -> list[Message]:
    return [
        Message(role="system", content="be helpful"),
        Message(role="user", content="hello"),
    ]


def test_fake_implements_protocol() -> None:
    fake: LLMProvider = FakeLLMProvider()
    response = fake.chat(
        messages=_msgs(),
        model="deepseek-v4-flash",
        thinking=False,
        temperature=0.3,
    )
    assert isinstance(response, LLMResponse)


def test_fake_returns_default_when_no_scenario() -> None:
    fake = FakeLLMProvider()
    response = fake.chat(
        messages=_msgs(),
        model="deepseek-v4-flash",
        thinking=False,
        temperature=0.3,
    )
    assert response.content.startswith("Réponse générée")


def test_fake_returns_scripted_response_by_key() -> None:
    key = make_request_key(
        messages=_msgs(),
        model="deepseek-v4-flash",
        thinking=False,
        temperature=0.3,
    )
    scripted = LLMResponse(
        content="scripted",
        thinking_content=None,
        prompt_tokens=10,
        completion_tokens=20,
        cached_prompt_tokens=0,
        cost_usd=0.01,
    )
    fake = FakeLLMProvider(scenarios={key: scripted})
    response = fake.chat(
        messages=_msgs(),
        model="deepseek-v4-flash",
        thinking=False,
        temperature=0.3,
    )
    assert response is scripted


def test_fake_failure_raises_specified_error() -> None:
    key = make_request_key(
        messages=_msgs(),
        model="deepseek-v4-flash",
        thinking=False,
        temperature=0.3,
    )
    fake = FakeLLMProvider(
        failures={
            key: LLMError(
                code="LLM.RATE_LIMIT", user_message="boom", severity=Severity.WARNING
            )
        }
    )
    with pytest.raises(LLMError):
        fake.chat(
            messages=_msgs(),
            model="deepseek-v4-flash",
            thinking=False,
            temperature=0.3,
        )


def test_fake_records_calls() -> None:
    fake = FakeLLMProvider()
    fake.chat(
        messages=_msgs(),
        model="deepseek-v4-flash",
        thinking=True,
        temperature=0.5,
    )
    assert len(fake.calls) == 1
    assert fake.calls[0]["model"] == "deepseek-v4-flash"
    assert fake.calls[0]["thinking"] is True


def test_estimate_cost_uses_pricing() -> None:
    fake = FakeLLMProvider()
    cost = fake.estimate_cost(
        prompt_tokens=1_000_000,
        completion_tokens=0,
        model="deepseek-v4-flash",
        thinking=False,
    )
    assert cost == pytest.approx(0.14)


def test_make_request_key_is_deterministic() -> None:
    k1 = make_request_key(
        messages=_msgs(), model="m", thinking=False, temperature=0.3
    )
    k2 = make_request_key(
        messages=_msgs(), model="m", thinking=False, temperature=0.3
    )
    assert k1 == k2


def test_make_request_key_differs_on_temperature() -> None:
    k1 = make_request_key(
        messages=_msgs(), model="m", thinking=False, temperature=0.3
    )
    k2 = make_request_key(
        messages=_msgs(), model="m", thinking=False, temperature=0.5
    )
    assert k1 != k2
