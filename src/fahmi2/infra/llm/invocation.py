"""Helpers LLM généralisés : invocation chat + parsing JSON robuste.

Mutualise l'appel ``LLMProvider.chat`` à partir d'une ``PhaseConfig`` et le
parsing tolérant des réponses JSON (délimiteurs ```` ```json ```` éventuels),
avec mapping vers une erreur typée. Réutilisé par les handlers de phase
(``pipeline/handlers/_base.py``) et par les générateurs de supports pédagogiques.
"""

from __future__ import annotations

import json
from typing import Any

from fahmi2.core.errors.exceptions import LLMError
from fahmi2.core.errors.severity import Severity
from fahmi2.domain.phase import PhaseConfig
from fahmi2.infra.llm.interface import LLMProvider, LLMResponse, Message

_RAW_CONTENT_MAX_CHARS = 500


def invoke_llm_chat(
    llm_provider: LLMProvider,
    *,
    model: str,
    config: PhaseConfig,
    system_prompt: str | None,
    user_prompt: str,
    max_tokens: int | None = None,
) -> LLMResponse:
    """Appelle ``llm_provider.chat`` avec une ``PhaseConfig``.

    Args:
        llm_provider: Provider LLM à invoquer.
        model: Identifiant du modèle (ex: ``"deepseek-v4-flash"``).
        config: Config LLM (thinking / reasoning_effort / température).
        system_prompt: Prompt système optionnel.
        user_prompt: Prompt utilisateur (corps de la requête).
        max_tokens: Borne supérieure de tokens en sortie (``None`` = défaut modèle).

    Returns:
        La ``LLMResponse``.
    """
    messages: list[Message] = []
    if system_prompt:
        messages.append(Message(role="system", content=system_prompt))
    messages.append(Message(role="user", content=user_prompt))
    reasoning_effort_str = (
        str(config.reasoning_effort) if config.reasoning_effort else None
    )
    return llm_provider.chat(
        messages=messages,
        model=model,
        thinking=config.thinking_enabled,
        reasoning_effort=reasoning_effort_str,
        temperature=config.temperature,
        max_tokens=max_tokens,
    )


def parse_llm_json(content: str, *, context_label: str) -> Any:  # noqa: ANN401
    """Parse une réponse LLM JSON, en isolant d'éventuels délimiteurs.

    Args:
        content: Contenu textuel de la réponse LLM.
        context_label: Libellé de contexte pour les messages d'erreur
            (ex: ``"reformulation"``, ``"flashcards_concepts"``).

    Returns:
        L'objet Python décodé.

    Raises:
        LLMError: ``LLM.INVALID_JSON`` si le contenu n'est pas du JSON valide.
    """
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.strip("`")
        if cleaned.lower().startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise LLMError(
            code="LLM.INVALID_JSON",
            user_message=(
                f"La réponse du LLM pour {context_label} n'est pas du JSON valide."
            ),
            severity=Severity.ERROR,
            technical_details={
                "context_label": context_label,
                "raw_content": content[:_RAW_CONTENT_MAX_CHARS],
            },
        ) from exc
