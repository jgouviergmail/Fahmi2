"""Helpers LLM généralisés : invocation chat + parsing JSON robuste.

Mutualise l'appel ``LLMProvider.chat`` à partir d'une ``PhaseConfig`` et le
parsing tolérant des réponses JSON (délimiteurs ```` ```json ```` éventuels),
avec mapping vers une erreur typée. Réutilisé par les handlers de phase
(``pipeline/handlers/_base.py``) et par les générateurs de supports pédagogiques.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any

from fahmi2.core.errors.error_info import ErrorInfo
from fahmi2.core.errors.exceptions import Fahmi2Error, LLMError
from fahmi2.core.errors.severity import Severity
from fahmi2.core.retry.classification import default_classify
from fahmi2.core.retry.policy import RetryDecision, RetryPolicy
from fahmi2.core.retry.runner import with_retry
from fahmi2.domain.phase import PhaseConfig
from fahmi2.infra.llm.interface import (
    DEFAULT_MAX_OUTPUT_TOKENS,
    LLMProvider,
    LLMResponse,
    Message,
)

#: Signature du callback de retry : ``(numéro_tentative, délai_s, erreur) -> None``.
#: Appelé **avant** la propagation d'une erreur **retryable**, pour permettre à
#: l'appelant d'émettre un événement spécifique à sa fonctionnalité.
RetryNotifier = Callable[[int, float, ErrorInfo], None]

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
    response_format: dict[str, str] | None = None,
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
        response_format: Contrainte de format imposée au provider. À passer
            quand la sortie est destinée à ``parse_llm_json`` :
            ``JSON_OBJECT_RESPONSE_FORMAT`` force le provider à produire un
            JSON syntaxiquement valide (échappement garanti côté serveur), ce
            qui évite la classe de bugs où un LLM insère des guillemets droits
            non échappés à l'intérieur d'une valeur string et casse le parsing
            aval. ``None`` = sortie libre.

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
        response_format=response_format,
    )


def invoke_llm_chat_with_retry(
    llm_provider: LLMProvider,
    *,
    model: str,
    config: PhaseConfig,
    system_prompt: str | None,
    user_prompt: str,
    retry_policy: RetryPolicy,
    on_retry: RetryNotifier,
    classify: Callable[[BaseException], RetryDecision] = default_classify,
    response_format: dict[str, str] | None = None,
    max_tokens: int | None = DEFAULT_MAX_OUTPUT_TOKENS,
) -> LLMResponse:
    """Appelle ``invoke_llm_chat`` avec retry + notification de tentative.

    Mutualise la boucle « appel → si erreur retryable, notifier puis relancer »
    partagée par les fonctionnalités qui émettent un événement de retry propre
    (Pédagogie, Visualisations). Le ``on_retry`` est invoqué **uniquement** pour une
    erreur classée ``RETRY``, avant la propagation gérée par ``with_retry``.

    Args:
        llm_provider: Provider LLM à invoquer.
        model: Identifiant du modèle.
        config: Config LLM (thinking / reasoning_effort / température).
        system_prompt: Prompt système optionnel.
        user_prompt: Prompt utilisateur.
        retry_policy: Politique de retry (tentatives, délais).
        on_retry: Callback ``(tentative, délai_s, ErrorInfo)`` appelé avant chaque
            relance d'une erreur retryable (typiquement : publier un événement).
        classify: Classifieur d'erreur (défaut : ``default_classify``).
        response_format: Contrainte de format provider (cf. ``invoke_llm_chat``).
        max_tokens: Borne supérieure de tokens en sortie.

    Returns:
        La ``LLMResponse``.

    Raises:
        Fahmi2Error: La dernière erreur si toutes les tentatives échouent.
    """
    attempts = {"n": 0}

    def _once() -> LLMResponse:
        attempts["n"] += 1
        try:
            return invoke_llm_chat(
                llm_provider,
                model=model,
                config=config,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                max_tokens=max_tokens,
                response_format=response_format,
            )
        except Fahmi2Error as exc:
            if classify(exc) is RetryDecision.RETRY:
                on_retry(
                    attempts["n"],
                    retry_policy.compute_delay(attempt=attempts["n"]),
                    ErrorInfo.from_exception(exc),
                )
            raise

    return with_retry(_once, policy=retry_policy, classify=classify)


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
        LLMError:
            - ``LLM.EMPTY_CONTENT`` si la réponse est vide ou ne contient que
              du whitespace. Documenté côté DeepSeek comme un comportement
              intermittent du JSON mode strict (« the API may occasionally
              return empty content ») — typé séparément pour être **retryable**
              (cf. ``_RETRYABLE_LLM_CODES`` dans ``core/retry/classification``).
            - ``LLM.INVALID_JSON`` si le contenu n'est pas du JSON valide.
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
    if not cleaned:
        raise LLMError(
            code="LLM.EMPTY_CONTENT",
            user_message=(
                f"La réponse du LLM pour {context_label} est vide. "
                "Le run réessaiera automatiquement."
            ),
            severity=Severity.WARNING,
            technical_details={
                "context_label": context_label,
                "content_length": len(content),
                "finish_reason": finish_reason,
            },
        )
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
