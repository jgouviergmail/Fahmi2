"""Adaptateur ``LLMProvider`` pour DeepSeek (compatible SDK OpenAI).

DeepSeek expose une API compatible OpenAI à l'URL ``https://api.deepseek.com``.
Le mode raisonnement est activé via le paramètre ``extra_body={"thinking": ...}``
(spécifique DeepSeek) — non standard OpenAI.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

from openai import APIError, APIStatusError, AuthenticationError, OpenAI, RateLimitError

from fahmi2.core.errors.exceptions import LLMError
from fahmi2.core.errors.severity import Severity
from fahmi2.core.text_metrics import estimate_tokens
from fahmi2.infra.llm._pricing import get_pricing
from fahmi2.infra.llm.interface import LLMResponse, LLMStreamChunk, Message

_PROVIDER_BASE_URL = "https://api.deepseek.com"
_PROVIDER_NAME = "deepseek"
_REASONING_FIELD = "reasoning_content"
_CACHED_TOKENS_FIELD = "prompt_cache_hit_tokens"
#: ``finish_reason`` signalant une sortie coupée car la limite de tokens est atteinte.
_FINISH_REASON_LENGTH = "length"

# DeepSeek garde la connexion ouverte (keep-alive) et ne la ferme qu'après ~10
# minutes sans démarrage d'inférence : timeout client large pour absorber les
# requêtes lentes sous charge (notamment reasoning_effort élevé).
_REQUEST_TIMEOUT_SECONDS = 600.0


def _map_exception_to_llm_error(exc: BaseException) -> LLMError:
    if isinstance(exc, AuthenticationError):
        return LLMError(
            code="LLM.AUTH_INVALID",
            user_message=(
                "La clé DeepSeek est refusée. Vérifie-la dans Paramètres › Clés API."
            ),
            severity=Severity.ERROR,
            technical_details={"provider": _PROVIDER_NAME},
        )
    if isinstance(exc, RateLimitError):
        return LLMError(
            code="LLM.RATE_LIMIT",
            user_message="Limite de débit DeepSeek atteinte.",
            severity=Severity.WARNING,
            technical_details={"provider": _PROVIDER_NAME},
        )
    if isinstance(exc, APIStatusError):
        return LLMError(
            code="LLM.SERVER_ERROR",
            user_message="Erreur côté serveur DeepSeek.",
            severity=Severity.ERROR,
            technical_details={"provider": _PROVIDER_NAME, "status": exc.status_code},
        )
    if isinstance(exc, APIError):
        return LLMError(
            code="LLM.API_ERROR",
            user_message="Échec d'appel à l'API DeepSeek.",
            severity=Severity.ERROR,
            technical_details={"provider": _PROVIDER_NAME, "error": str(exc)},
        )
    return LLMError(
        code="LLM.UNEXPECTED",
        user_message="Erreur inattendue lors de l'appel à DeepSeek.",
        severity=Severity.ERROR,
        technical_details={"provider": _PROVIDER_NAME, "error": str(exc)},
    )


class DeepSeekAdapter:
    """Implémentation ``LLMProvider`` pour l'API DeepSeek."""

    def __init__(
        self,
        *,
        api_key: str,
        client: OpenAI | None = None,
        base_url: str = _PROVIDER_BASE_URL,
        timeout: float = _REQUEST_TIMEOUT_SECONDS,
    ) -> None:
        """Construit l'adaptateur.

        Args:
            api_key: Clé API DeepSeek.
            client: Client OpenAI injectable (utile pour les tests).
            base_url: URL de base de l'API.
            timeout: Timeout des requêtes en secondes (absorbe le keep-alive).
        """
        self._client = client or OpenAI(
            api_key=api_key, base_url=base_url, timeout=timeout
        )

    def chat(
        self,
        *,
        messages: list[Message],
        model: str,
        thinking: bool,
        reasoning_effort: str | None = None,
        temperature: float,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        """Émet un appel chat et retourne la réponse parsée.

        Args:
            messages: Conversation.
            model: Identifiant du modèle DeepSeek.
            thinking: Active ``{"thinking": {"type": "enabled"}}``.
            reasoning_effort: Si ``thinking`` est ``True``, envoyé en
                ``{"reasoning_effort": <valeur>}``. Ignoré sinon.
            temperature: Température.
            max_tokens: Limite de tokens en sortie (None = défaut modèle).

        Returns:
            ``LLMResponse``.

        Raises:
            LLMError: En cas d'échec d'appel.
        """
        kwargs = self._build_kwargs(
            messages=messages,
            model=model,
            thinking=thinking,
            reasoning_effort=reasoning_effort,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        try:
            response = self._client.chat.completions.create(**kwargs)
        except BaseException as exc:  # noqa: BLE001 — mappé vers une LLMError typée
            raise _map_exception_to_llm_error(exc) from exc

        return _parse_chat_response(response.model_dump(), model)

    def _build_kwargs(
        self,
        *,
        messages: list[Message],
        model: str,
        thinking: bool,
        reasoning_effort: str | None,
        temperature: float,
        max_tokens: int | None,
    ) -> dict[str, Any]:
        """Construit les kwargs communs d'appel (``chat`` et ``chat_stream``).

        Args:
            messages: Conversation.
            model: Modèle DeepSeek.
            thinking: Active le mode raisonnement.
            reasoning_effort: Niveau d'effort (si ``thinking``).
            temperature: Température.
            max_tokens: Limite de tokens en sortie (None = défaut modèle).

        Returns:
            Le dict de kwargs (sans ``stream``).
        """
        kwargs: dict[str, Any] = {
            "model": model,
            "messages": [{"role": m.role, "content": m.content} for m in messages],
            "temperature": temperature,
        }
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens
        extra_body: dict[str, Any] = {
            "thinking": {"type": "enabled" if thinking else "disabled"}
        }
        if thinking and reasoning_effort is not None:
            extra_body["reasoning_effort"] = reasoning_effort
        kwargs["extra_body"] = extra_body
        return kwargs

    def chat_stream(
        self,
        *,
        messages: list[Message],
        model: str,
        thinking: bool,
        reasoning_effort: str | None = None,
        temperature: float,
        max_tokens: int | None = None,
    ) -> Iterator[LLMStreamChunk]:
        """Émet un appel chat en streaming SSE (deltas + chunk final porteur du coût).

        Args:
            messages: Conversation.
            model: Modèle DeepSeek.
            thinking: Active le mode raisonnement.
            reasoning_effort: Niveau d'effort (si ``thinking``).
            temperature: Température.
            max_tokens: Limite de tokens en sortie.

        Yields:
            ``LLMStreamChunk`` (deltas, puis un dernier ``is_final`` porteur du coût).

        Raises:
            LLMError: En cas d'échec d'appel.
        """
        kwargs = self._build_kwargs(
            messages=messages,
            model=model,
            thinking=thinking,
            reasoning_effort=reasoning_effort,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        kwargs["stream"] = True
        kwargs["stream_options"] = {"include_usage": True}
        prompt_text = " ".join(m.content for m in messages)
        content_parts: list[str] = []
        reasoning_parts: list[str] = []
        usage: dict[str, Any] | None = None
        try:
            stream = self._client.chat.completions.create(**kwargs)
            for raw_chunk in stream:
                chunk = raw_chunk.model_dump()
                choices = chunk.get("choices") or []
                if choices:
                    delta = choices[0].get("delta") or {}
                    content_delta = str(delta.get("content") or "")
                    reasoning_raw = delta.get(_REASONING_FIELD)
                    reasoning_delta = str(reasoning_raw) if reasoning_raw else None
                    if content_delta or reasoning_delta:
                        content_parts.append(content_delta)
                        if reasoning_delta:
                            reasoning_parts.append(reasoning_delta)
                        yield LLMStreamChunk(
                            content_delta=content_delta,
                            thinking_delta=reasoning_delta,
                        )
                if chunk.get("usage"):
                    usage = chunk["usage"]
        except BaseException as exc:  # noqa: BLE001 — mappé vers une LLMError typée
            raise _map_exception_to_llm_error(exc) from exc
        yield LLMStreamChunk(
            content_delta="",
            is_final=True,
            response=_build_stream_response(
                content="".join(content_parts),
                thinking_content="".join(reasoning_parts) or None,
                usage=usage,
                model=model,
                prompt_text=prompt_text,
            ),
        )

    def estimate_cost(
        self,
        *,
        prompt_tokens: int,
        completion_tokens: int,
        model: str,
        thinking: bool,
        cached_prompt_tokens: int = 0,
    ) -> float:
        """Délègue au module ``_pricing``.

        Args:
            prompt_tokens: Tokens d'entrée.
            completion_tokens: Tokens de sortie.
            model: Modèle.
            thinking: Ignoré (les tarifs sont identiques).
            cached_prompt_tokens: Tokens en cache hit.

        Returns:
            Coût en USD.
        """
        del thinking
        return get_pricing(model).cost_for(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cached_prompt_tokens=cached_prompt_tokens,
        )


def _parse_chat_response(payload: dict[str, Any], model: str) -> LLMResponse:
    """Construit un ``LLMResponse`` à partir du dump JSON OpenAI/DeepSeek.

    Args:
        payload: Réponse au format ``ChatCompletion.model_dump()``.
        model: Modèle utilisé (pour calcul du coût).

    Returns:
        ``LLMResponse``.
    """
    choice = payload["choices"][0]
    message = choice["message"]
    content = str(message.get("content", ""))
    thinking_content_raw = message.get(_REASONING_FIELD)
    thinking_content = (
        str(thinking_content_raw) if thinking_content_raw is not None else None
    )

    usage = payload.get("usage") or {}
    prompt_tokens = int(usage.get("prompt_tokens", 0))
    completion_tokens = int(usage.get("completion_tokens", 0))
    cached_prompt_tokens = int(usage.get(_CACHED_TOKENS_FIELD, 0) or 0)

    # Troncature à la limite de tokens : ne JAMAIS accepter un contenu coupé en
    # silence (perte de données). On lève une erreur explicite et actionnable.
    if choice.get("finish_reason") == _FINISH_REASON_LENGTH:
        raise LLMError(
            code="LLM.OUTPUT_TRUNCATED",
            user_message=(
                "La réponse du modèle a été tronquée (limite de tokens de sortie "
                "atteinte). La source est probablement trop volumineuse pour un "
                "seul traitement : réduis-la ou découpe-la en plusieurs entrées."
            ),
            severity=Severity.ERROR,
            technical_details={
                "provider": _PROVIDER_NAME,
                "model": model,
                "completion_tokens": completion_tokens,
            },
        )

    pricing = get_pricing(model)
    cost = pricing.cost_for(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cached_prompt_tokens=cached_prompt_tokens,
    )

    return LLMResponse(
        content=content,
        thinking_content=thinking_content,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cached_prompt_tokens=cached_prompt_tokens,
        cost_usd=cost,
    )


def _build_stream_response(
    *,
    content: str,
    thinking_content: str | None,
    usage: dict[str, Any] | None,
    model: str,
    prompt_text: str,
) -> LLMResponse:
    """Construit la ``LLMResponse`` finale d'un flux (usage exact ou estimé).

    Args:
        content: Contenu accumulé.
        thinking_content: Raisonnement accumulé (ou ``None``).
        usage: Bloc ``usage`` du dernier chunk (``None`` → repli par estimation).
        model: Modèle (pour le coût).
        prompt_text: Concaténation des messages (repli d'estimation des tokens).

    Returns:
        ``LLMResponse`` (coût exact si ``usage`` présent, sinon estimé).
    """
    if usage:
        prompt_tokens = int(usage.get("prompt_tokens", 0))
        completion_tokens = int(usage.get("completion_tokens", 0))
        cached_prompt_tokens = int(usage.get(_CACHED_TOKENS_FIELD, 0) or 0)
    else:
        prompt_tokens = estimate_tokens(prompt_text)
        completion_tokens = estimate_tokens(content)
        cached_prompt_tokens = 0
    cost = get_pricing(model).cost_for(
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cached_prompt_tokens=cached_prompt_tokens,
    )
    return LLMResponse(
        content=content,
        thinking_content=thinking_content,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        cached_prompt_tokens=cached_prompt_tokens,
        cost_usd=cost,
    )
