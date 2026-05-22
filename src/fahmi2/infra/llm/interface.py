"""Interface ``LLMProvider`` et dataclasses associées (``Message``, ``LLMResponse``).

L'interface est volontairement minimale pour pouvoir swap DeepSeek vers d'autres
providers OpenAI-compatibles plus tard (Anthropic, Mistral, etc.).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Literal, Protocol

Role = Literal["system", "user", "assistant"]


@dataclass(frozen=True)
class Message:
    """Message d'une conversation LLM.

    Attributes:
        role: ``system``, ``user``, ou ``assistant``.
        content: Contenu textuel du message.
    """

    role: Role
    content: str


@dataclass(frozen=True)
class LLMResponse:
    """Réponse d'un appel LLM avec métadonnées de coût.

    Attributes:
        content: Texte généré par le modèle.
        thinking_content: Trace de raisonnement si ``thinking=True``, sinon ``None``.
        prompt_tokens: Total des tokens d'entrée.
        completion_tokens: Total des tokens générés.
        cached_prompt_tokens: Tokens d'entrée servis par le cache prompts.
        cost_usd: Coût total de l'appel en USD.
    """

    content: str
    thinking_content: str | None
    prompt_tokens: int
    completion_tokens: int
    cached_prompt_tokens: int
    cost_usd: float


@dataclass(frozen=True)
class LLMStreamChunk:
    """Fragment de réponse en streaming.

    Attributes:
        content_delta: Incrément de texte de réponse (vide sur le chunk final).
        thinking_delta: Incrément de raisonnement (``None`` si absent).
        is_final: ``True`` pour le dernier chunk (porteur de l'usage/coût).
        response: ``LLMResponse`` complète (usage + coût), seulement si ``is_final``.
    """

    content_delta: str
    thinking_delta: str | None = None
    is_final: bool = False
    response: LLMResponse | None = None


class LLMProvider(Protocol):
    """Contrat commun aux adapters LLM (DeepSeek, mais ouvert à d'autres)."""

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
        """Émet un appel chat et retourne la réponse.

        Args:
            messages: Liste ordonnée des messages.
            model: Identifiant du modèle (ex: ``deepseek-v4-flash``).
            thinking: Active le mode raisonnement (envoie côté DeepSeek
                ``{"thinking": {"type": "enabled"}}``).
            reasoning_effort: Niveau d'effort de raisonnement
                (ex: ``"high"`` ou ``"max"`` côté DeepSeek). Pris en compte
                uniquement si ``thinking`` est ``True``. ``None`` = défaut serveur.
            temperature: Température LLM.
            max_tokens: Borne supérieure de tokens en sortie (None = défaut modèle).

        Returns:
            ``LLMResponse``.

        Raises:
            LLMError: En cas d'échec d'appel.
        """

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
        """Émet un appel chat en streaming (deltas + chunk final porteur du coût).

        Args:
            messages: Liste ordonnée des messages.
            model: Identifiant du modèle.
            thinking: Active le mode raisonnement.
            reasoning_effort: Niveau d'effort de raisonnement (si ``thinking``).
            temperature: Température LLM.
            max_tokens: Borne supérieure de tokens en sortie (None = défaut modèle).

        Returns:
            Itérateur de ``LLMStreamChunk`` ; le dernier a ``is_final=True`` et
            porte la ``LLMResponse`` complète (usage + coût).

        Raises:
            LLMError: En cas d'échec d'appel.
        """

    def estimate_cost(
        self,
        *,
        prompt_tokens: int,
        completion_tokens: int,
        model: str,
        thinking: bool,
        cached_prompt_tokens: int = 0,
    ) -> float:
        """Estime le coût USD pour un nombre de tokens donné.

        Args:
            prompt_tokens: Tokens d'entrée (non-cache).
            completion_tokens: Tokens de sortie.
            model: Identifiant du modèle.
            thinking: Mode raisonnement actif (peut affecter le tarif sortie).
            cached_prompt_tokens: Tokens d'entrée déjà en cache.

        Returns:
            Coût total en USD.
        """
