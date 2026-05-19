"""Implémentation factice de ``LLMProvider`` pour les tests cross-couche.

Hash l'input (messages + model + thinking + temperature) en clé et lookup dans
un dictionnaire de scénarios. Si la clé n'est pas trouvée, retourne une réponse
générique paramétrable. Permet aussi d'injecter une exception via ``failures``
pour exercer la retry policy et les chemins d'erreur.
"""

from __future__ import annotations

import hashlib
import json

from fahmi2.core.errors.exceptions import Fahmi2Error
from fahmi2.infra.llm._pricing import get_pricing
from fahmi2.infra.llm.interface import LLMResponse, Message


def make_request_key(
    *,
    messages: list[Message],
    model: str,
    thinking: bool,
    temperature: float,
) -> str:
    """Calcule une clé stable pour un appel LLM (utile pour les scénarios).

    Args:
        messages: Messages de l'appel.
        model: Identifiant du modèle.
        thinking: Mode raisonnement.
        temperature: Température.

    Returns:
        Hash SHA-256 hexadécimal de l'input sérialisé canoniquement.
    """
    payload = {
        "messages": [{"role": m.role, "content": m.content} for m in messages],
        "model": model,
        "thinking": thinking,
        "temperature": temperature,
    }
    serialized = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


_DEFAULT_RESPONSE = LLMResponse(
    content="Réponse générée par FakeLLMProvider.",
    thinking_content=None,
    prompt_tokens=50,
    completion_tokens=10,
    cached_prompt_tokens=0,
    cost_usd=0.0,
)


class FakeLLMProvider:
    """LLM factice scénarisable pour les tests."""

    def __init__(
        self,
        *,
        scenarios: dict[str, LLMResponse] | None = None,
        failures: dict[str, Fahmi2Error] | None = None,
        default_response: LLMResponse = _DEFAULT_RESPONSE,
    ) -> None:
        """Construit un ``FakeLLMProvider``.

        Args:
            scenarios: Mapping ``key -> LLMResponse`` (la clé peut être un
                identifiant libre ou un hash via ``make_request_key``).
            failures: Mapping ``key -> exception`` à lever.
            default_response: Retour si aucun scénario ne matche.
        """
        self._scenarios = dict(scenarios or {})
        self._failures = dict(failures or {})
        self._default = default_response
        self.calls: list[dict[str, object]] = []

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
        """Retourne la réponse scénarisée ou un défaut.

        Args:
            messages: Conversation.
            model: Modèle.
            thinking: Mode raisonnement.
            reasoning_effort: Niveau d'effort de raisonnement (enregistré
                dans ``calls`` pour les assertions des tests).
            temperature: Température.
            max_tokens: Ignoré (présent pour respecter l'interface).

        Returns:
            ``LLMResponse``.

        Raises:
            Fahmi2Error: Si un scénario d'échec match la clé.
        """
        del max_tokens
        key = make_request_key(
            messages=messages,
            model=model,
            thinking=thinking,
            temperature=temperature,
        )
        self.calls.append(
            {
                "key": key,
                "messages": messages,
                "model": model,
                "thinking": thinking,
                "reasoning_effort": reasoning_effort,
                "temperature": temperature,
            }
        )
        if key in self._failures:
            raise self._failures[key]
        return self._scenarios.get(key, self._default)

    def estimate_cost(
        self,
        *,
        prompt_tokens: int,
        completion_tokens: int,
        model: str,
        thinking: bool,
        cached_prompt_tokens: int = 0,
    ) -> float:
        """Estime le coût en utilisant la grille tarifaire réelle.

        Permet aux tests des couches supérieures d'observer des coûts
        cohérents.

        Args:
            prompt_tokens: Tokens d'entrée.
            completion_tokens: Tokens de sortie.
            model: Modèle.
            thinking: Mode raisonnement (ignoré dans le calcul de base).
            cached_prompt_tokens: Tokens d'entrée en cache.

        Returns:
            Coût en USD.
        """
        del thinking
        pricing = get_pricing(model)
        return pricing.cost_for(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cached_prompt_tokens=cached_prompt_tokens,
        )
