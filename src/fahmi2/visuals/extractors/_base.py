"""Socle des extracteurs LLM des Visualisations : contexte DI + invocation/retry.

``VisualsContext`` regroupe les dépendances stables injectées par l'orchestrateur.
``invoke_visuals_llm`` mutualise l'appel LLM avec retry (parité moteur via
``default_classify``) et l'émission d'un ``VisualsRetryAttempt`` — équivalent de
``invoke_support_llm`` côté Pédagogie, mais avec les événements des Visualisations.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime

from fahmi2.core.concurrency.pause_token import PauseToken
from fahmi2.core.errors.error_info import ErrorInfo
from fahmi2.core.retry.policy import RetryPolicy
from fahmi2.domain.enums import Language
from fahmi2.domain.visuals import VisualsSettings
from fahmi2.infra.llm.interface import LLMProvider, LLMResponse
from fahmi2.infra.llm.invocation import invoke_llm_chat_with_retry
from fahmi2.infra.prompts.loader import PromptLoader
from fahmi2.pipeline.event_bus import EventBus
from fahmi2.visuals.events import VisualsEvent, VisualsRetryAttempt


@dataclass(frozen=True)
class VisualsContext:
    """Dépendances injectées aux extracteurs des Visualisations.

    Attributes:
        settings: Réglages Visualisations du projet (modèle/config LLM, densité…).
        llm_provider: Provider LLM.
        prompts: Loader de prompts (défauts bundlés + override ``%APPDATA%``).
        event_bus: Bus d'événements Visualisations.
        pause_token: Jeton coopératif pause/annulation.
        retry_policy: Politique de retry des appels LLM.
    """

    settings: VisualsSettings
    llm_provider: LLMProvider
    prompts: PromptLoader
    event_bus: EventBus[VisualsEvent]
    pause_token: PauseToken
    retry_policy: RetryPolicy


def _now() -> datetime:
    """Horodatage UTC courant.

    Returns:
        ``datetime`` UTC aware.
    """
    return datetime.now(tz=UTC)


def invoke_visuals_llm(
    ctx: VisualsContext,
    *,
    stage: str,
    language: Language,
    user_prompt: str,
    system_prompt: str | None = None,
    response_format: dict[str, str] | None = None,
) -> LLMResponse:
    """Appelle le LLM avec retry et émission de ``VisualsRetryAttempt``.

    Args:
        ctx: Contexte d'exécution.
        stage: Étape du pipeline (pour les événements, ex. ``"graph_extraction"``).
        language: Langue (pour les événements).
        user_prompt: Prompt utilisateur.
        system_prompt: Prompt système optionnel.
        response_format: Contrainte de format provider (cf. ``invoke_llm_chat``) ;
            passer ``JSON_OBJECT_RESPONSE_FORMAT`` quand la sortie est parsée en JSON.

    Returns:
        La ``LLMResponse``.

    Raises:
        Fahmi2Error: La dernière erreur si toutes les tentatives échouent.
    """

    def _on_retry(attempt: int, delay_seconds: float, error: ErrorInfo) -> None:
        ctx.event_bus.publish(
            VisualsRetryAttempt(
                timestamp=_now(),
                stage=stage,
                language=language,
                attempt=attempt,
                delay_seconds=delay_seconds,
                error=error,
            )
        )

    return invoke_llm_chat_with_retry(
        ctx.llm_provider,
        model=str(ctx.settings.llm_model),
        config=ctx.settings.llm_config,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        retry_policy=ctx.retry_policy,
        on_retry=_on_retry,
        response_format=response_format,
    )
