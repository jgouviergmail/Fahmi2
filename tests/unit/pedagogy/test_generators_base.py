"""Tests du socle des générateurs LLM (retry/events + parsing typé)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from fahmi2.core.errors.exceptions import LLMError
from fahmi2.core.errors.severity import Severity
from fahmi2.core.retry.policy import RetryPolicy
from fahmi2.domain.enums import Language, SupportType
from fahmi2.infra.llm.interface import LLMResponse
from fahmi2.infra.prompts.loader import PromptLoader
from fahmi2.infra.storage.fs_artifacts import FsArtifactStore
from fahmi2.pedagogy.events import PedagogyEvent, SupportRetryAttempt
from fahmi2.pedagogy.generators._base import (
    invoke_support_llm,
    require_list,
    require_str,
)
from fahmi2.pedagogy.support_generator import SupportContext
from fahmi2.pipeline.event_bus import EventBus
from fahmi2.pipeline.pause_token import PauseToken


class _FailingThenOk:
    """Provider factice : échoue n fois (LLM.RATE_LIMIT) puis répond ``{}``."""

    def __init__(self, *, fail_times: int) -> None:
        self._fail_times = fail_times
        self.calls = 0

    def chat(self, **_kwargs: Any) -> LLMResponse:
        self.calls += 1
        if self.calls <= self._fail_times:
            raise LLMError(
                code="LLM.RATE_LIMIT", user_message="rate", severity=Severity.ERROR
            )
        return LLMResponse(
            content="{}", thinking_content=None, prompt_tokens=1,
            completion_tokens=1, cached_prompt_tokens=0, cost_usd=0.0,
        )

    def estimate_cost(self, **_kwargs: Any) -> float:
        return 0.0


def _ctx(provider: Any, make_pedagogy_settings: Any) -> SupportContext:
    return SupportContext(
        pedagogy=make_pedagogy_settings(),
        generation_output_dir=Path("."),
        pedagogy_dir=Path("."),
        llm_provider=provider,
        prompts=PromptLoader(),
        artifacts=FsArtifactStore(),
        event_bus=EventBus[PedagogyEvent](),
        pause_token=PauseToken(),
        retry_policy=RetryPolicy(
            max_attempts=3, jitter=False, initial_delay_seconds=0.001
        ),
    )


def test_invoke_retries_then_succeeds_and_emits_event(
    make_pedagogy_settings: Any,
) -> None:
    provider = _FailingThenOk(fail_times=1)
    ctx = _ctx(provider, make_pedagogy_settings)
    events: list[PedagogyEvent] = []
    ctx.event_bus.subscribe(events.append)

    response = invoke_support_llm(
        ctx, support_type=SupportType.QCM, language=Language.FR,
        system_prompt=None, user_prompt="x",
    )
    assert response.content == "{}"
    assert provider.calls == 2
    assert any(isinstance(e, SupportRetryAttempt) for e in events)


def test_invoke_gives_up_after_max_attempts(make_pedagogy_settings: Any) -> None:
    provider = _FailingThenOk(fail_times=10)
    ctx = _ctx(provider, make_pedagogy_settings)
    with pytest.raises(LLMError):
        invoke_support_llm(
            ctx, support_type=SupportType.QCM, language=Language.FR,
            system_prompt=None, user_prompt="x",
        )


def test_require_helpers() -> None:
    assert require_str({"a": "x"}, "a", context_label="t") == "x"
    assert require_list({"a": [1, 2]}, "a", context_label="t") == [1, 2]
    with pytest.raises(LLMError):
        require_str({"a": 1}, "a", context_label="t")
    with pytest.raises(LLMError):
        require_list({}, "missing", context_label="t")
