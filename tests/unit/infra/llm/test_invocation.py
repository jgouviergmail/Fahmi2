"""Tests des helpers LLM généralisés (invocation + parsing JSON)."""

from __future__ import annotations

from typing import cast

import pytest

from fahmi2.core.errors.exceptions import LLMError
from fahmi2.domain.phase import PhaseConfig
from fahmi2.infra.llm._fakes import FakeLLMProvider
from fahmi2.infra.llm.interface import DEFAULT_MAX_OUTPUT_TOKENS, Message
from fahmi2.infra.llm.invocation import invoke_llm_chat, parse_llm_json


def test_parse_llm_json_strips_code_fence() -> None:
    assert parse_llm_json('```json\n{"a": 1}\n```', context_label="x") == {"a": 1}


def test_parse_llm_json_plain_object() -> None:
    assert parse_llm_json('{"b": 2}', context_label="x") == {"b": 2}


def test_parse_llm_json_raises_typed_error() -> None:
    with pytest.raises(LLMError) as exc_info:
        parse_llm_json("pas du json", context_label="flashcards")
    assert exc_info.value.code == "LLM.INVALID_JSON"
    assert exc_info.value.technical_details["context_label"] == "flashcards"


def test_parse_llm_json_error_reports_full_diagnostic() -> None:
    """``LLM.INVALID_JSON`` doit reporter content_length + truncated_in_log + finish_reason.

    Critique pour diagnostiquer un parsing échoué sur un gros payload (ex.
    glossaire localisé arabe/allemand de 30 ko) : sans ces métadonnées on ne
    sait pas si la réponse est tronquée côté provider, ou complète mais
    malformée.
    """
    short_invalid = "[{not valid"
    with pytest.raises(LLMError) as exc_info:
        parse_llm_json(short_invalid, context_label="phase_6", finish_reason="stop")
    details = exc_info.value.technical_details
    assert details["content_length"] == len(short_invalid)
    assert details["truncated_in_log"] is False
    assert details["finish_reason"] == "stop"
    # ``raw_content`` complet (pas tronqué tant que < _RAW_CONTENT_MAX_CHARS).
    assert details["raw_content"] == short_invalid


def test_parse_llm_json_error_flags_log_truncation_on_huge_payload() -> None:
    """Un contenu > 50_000 chars est tronqué dans le log mais ``content_length`` reflète
    la taille réelle et ``truncated_in_log`` vaut ``True``."""
    huge = "x" * 60_000  # > _RAW_CONTENT_MAX_CHARS (50_000)
    with pytest.raises(LLMError) as exc_info:
        parse_llm_json(huge, context_label="glossary", finish_reason="length")
    details = exc_info.value.technical_details
    assert details["content_length"] == 60_000
    assert details["truncated_in_log"] is True
    assert len(details["raw_content"]) == 50_000
    assert details["finish_reason"] == "length"


def test_parse_llm_json_default_finish_reason_is_none() -> None:
    """Appel sans ``finish_reason`` : la clé est présente avec valeur ``None`` (rétrocompat)."""
    with pytest.raises(LLMError) as exc_info:
        parse_llm_json("nope", context_label="x")
    assert exc_info.value.technical_details["finish_reason"] is None


def test_invoke_llm_chat_builds_messages_and_calls_provider() -> None:
    provider = FakeLLMProvider()
    response = invoke_llm_chat(
        provider,
        model="deepseek-v4-flash",
        config=PhaseConfig(),
        system_prompt="sys",
        user_prompt="user",
    )
    assert isinstance(response.content, str)
    # Le system + user prompts sont bien transmis au provider.
    last_call = provider.calls[-1]
    sent = cast("list[Message]", last_call["messages"])
    assert [m.role for m in sent] == ["system", "user"]
    assert last_call["model"] == "deepseek-v4-flash"


def test_invoke_llm_chat_defaults_to_generous_max_tokens() -> None:
    # Source unique du plafond anti-troncature : pipeline ET supports pédagogiques
    # passent par ce helper, qui demande par défaut le plafond du modèle.
    provider = FakeLLMProvider()
    invoke_llm_chat(
        provider,
        model="deepseek-v4-flash",
        config=PhaseConfig(),
        system_prompt=None,
        user_prompt="user",
    )
    assert provider.calls[-1]["max_tokens"] == DEFAULT_MAX_OUTPUT_TOKENS


def test_invoke_llm_chat_without_system_prompt() -> None:
    provider = FakeLLMProvider()
    invoke_llm_chat(
        provider,
        model="deepseek-v4-flash",
        config=PhaseConfig(),
        system_prompt=None,
        user_prompt="seul",
    )
    sent = cast("list[Message]", provider.calls[-1]["messages"])
    assert [m.role for m in sent] == ["user"]
