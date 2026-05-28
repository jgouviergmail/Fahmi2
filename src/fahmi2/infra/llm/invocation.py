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
from fahmi2.infra.llm.interface import (
    DEFAULT_MAX_OUTPUT_TOKENS,
    LLMProvider,
    LLMResponse,
    Message,
)

#: Limite haute du ``raw_content`` reporté dans les ``technical_details`` d'une
#: erreur ``LLM.INVALID_JSON``. La précédente valeur (500) était trop courte
#: pour diagnostiquer un cas réel (glossaire localisé en arabe/allemand : 1 à
#: 50 ko) — on ne voyait ni la fin du contenu ni si celui-ci était tronqué côté
#: provider. Cette limite plus haute capture la quasi-totalité des réponses
#: LLM utiles (les artefacts conservés sur disque vont par ailleurs jusqu'à
#: plusieurs Mo), tout en évitant qu'un log JSONL ne sature en cas de
#: déversement texte aberrant. Si le contenu dépasse cette borne, ``raw_content``
#: est tronqué et un drapeau ``truncated_in_log`` rapporte le fait, en plus de
#: ``content_length`` qui donne la taille **réelle** émise par le LLM.
_RAW_CONTENT_MAX_CHARS = 50_000


def invoke_llm_chat(
    llm_provider: LLMProvider,
    *,
    model: str,
    config: PhaseConfig,
    system_prompt: str | None,
    user_prompt: str,
    max_tokens: int | None = DEFAULT_MAX_OUTPUT_TOKENS,
) -> LLMResponse:
    """Appelle ``llm_provider.chat`` avec une ``PhaseConfig``.

    Args:
        llm_provider: Provider LLM à invoquer.
        model: Identifiant du modèle (ex: ``"deepseek-v4-flash"``).
        config: Config LLM (thinking / reasoning_effort / température).
        system_prompt: Prompt système optionnel.
        user_prompt: Prompt utilisateur (corps de la requête).
        max_tokens: Borne supérieure de tokens en sortie. **Défaut** :
            ``DEFAULT_MAX_OUTPUT_TOKENS`` (plafond du modèle), pour éviter une
            troncature silencieuse au petit défaut du provider — vaut pour le
            pipeline **et** les supports pédagogiques (gros supports possibles).

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


def parse_llm_json(
    content: str,
    *,
    context_label: str,
    finish_reason: str | None = None,
) -> Any:  # noqa: ANN401
    """Parse une réponse LLM JSON, en isolant d'éventuels délimiteurs.

    Args:
        content: Contenu textuel de la réponse LLM.
        context_label: Libellé de contexte pour les messages d'erreur
            (ex: ``"reformulation"``, ``"flashcards_concepts"``).
        finish_reason: Raison de fin de génération rapportée par le provider
            (``LLMResponse.finish_reason``). Reportée dans les
            ``technical_details`` de l'erreur ``LLM.INVALID_JSON`` pour
            permettre de discriminer une troncature silencieuse (``"length"``,
            ``"content_filter"`` selon le provider) d'une réponse complète
            mais malformée (``"stop"`` — le LLM pense avoir fini). **Défaut** :
            ``None`` pour rester rétrocompatible avec les générateurs/tests
            qui ne disposent pas de cette information.

    Returns:
        L'objet Python décodé.

    Raises:
        LLMError: ``LLM.INVALID_JSON`` si le contenu n'est pas du JSON valide.
            Les ``technical_details`` portent ``context_label``, ``raw_content``
            (jusqu'à ``_RAW_CONTENT_MAX_CHARS``), ``content_length`` (taille
            réelle émise), ``truncated_in_log`` (``True`` si le ``raw_content``
            a été tronqué pour le log), et ``finish_reason`` quand fourni.
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
        content_length = len(content)
        truncated_in_log = content_length > _RAW_CONTENT_MAX_CHARS
        raise LLMError(
            code="LLM.INVALID_JSON",
            user_message=(
                f"La réponse du LLM pour {context_label} n'est pas du JSON valide."
            ),
            severity=Severity.ERROR,
            technical_details={
                "context_label": context_label,
                "raw_content": content[:_RAW_CONTENT_MAX_CHARS],
                "content_length": content_length,
                "truncated_in_log": truncated_in_log,
                "finish_reason": finish_reason,
            },
        ) from exc
