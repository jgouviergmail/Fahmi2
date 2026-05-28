"""Interface ``LLMProvider`` et dataclasses associées (``Message``, ``LLMResponse``).

L'interface est volontairement minimale pour pouvoir swap DeepSeek vers d'autres
providers OpenAI-compatibles plus tard (Anthropic, Mistral, etc.).
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from typing import Literal, Protocol

Role = Literal["system", "user", "assistant"]

#: Plafond de tokens de sortie demandé par défaut. Sans ``max_tokens`` explicite,
#: le provider applique un **petit défaut** qui tronque silencieusement les sorties
#: longues : on demande donc le **maximum du modèle**. Les deux modèles DeepSeek V4
#: (flash et pro) partagent le même plafond de sortie de **384 K tokens** (contexte
#: 1 M) ; à revisiter si un provider à plafond inférieur est ajouté.
DEFAULT_MAX_OUTPUT_TOKENS = 384_000


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
        finish_reason: Raison de fin de génération telle que rapportée par le
            provider (ex: ``"stop"`` quand la génération s'est terminée
            normalement, ``"length"`` quand le plafond ``max_tokens`` a été
            atteint, ``"content_filter"``, etc.). ``None`` si le provider ne
            l'expose pas. **Diagnostic** : précieux pour discriminer une réponse
            tronquée silencieusement d'une réponse complète mais malformée
            lorsque le parsing JSON aval échoue (cf. ``parse_llm_json``).
            **Défaut** : ``None`` pour rester rétrocompatible avec les tests
            historiques qui construisent ``LLMResponse`` sans ce champ.
    """

    content: str
    thinking_content: str | None
    prompt_tokens: int
    completion_tokens: int
    cached_prompt_tokens: int
    cost_usd: float
    finish_reason: str | None = None


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


#: ``response_format`` à passer pour forcer le provider à émettre un JSON
#: syntaxiquement valide (échappement garanti côté serveur). Utilisé par toutes
#: les invocations dont la sortie est parsée par ``parse_llm_json``.
#: Source unique pour éviter qu'un appelant n'oublie la clé ``"type"`` ou ne
#: dérive vers une variante non supportée par DeepSeek/OpenAI.
JSON_OBJECT_RESPONSE_FORMAT: dict[str, str] = {"type": "json_object"}


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
        response_format: dict[str, str] | None = None,
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
            response_format: Contrainte de format imposée au provider
                (ex: ``JSON_OBJECT_RESPONSE_FORMAT = {"type": "json_object"}``
                pour forcer une sortie JSON valide avec échappement garanti côté
                serveur). ``None`` = sortie libre (texte ou Markdown).

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
        response_format: dict[str, str] | None = None,
    ) -> Iterator[LLMStreamChunk]:
        """Émet un appel chat en streaming (deltas + chunk final porteur du coût).

        Args:
            messages: Liste ordonnée des messages.
            model: Identifiant du modèle.
            thinking: Active le mode raisonnement.
            reasoning_effort: Niveau d'effort de raisonnement (si ``thinking``).
            temperature: Température LLM.
            max_tokens: Borne supérieure de tokens en sortie (None = défaut modèle).
            response_format: Idem ``chat`` : contrainte de format provider
                (ex: ``JSON_OBJECT_RESPONSE_FORMAT``).

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
