"""Moteur de chat : retrieve → prompt → LLM → citations (non-streaming + flux).

Orchestrateur léger. ``answer`` renvoie le ``ChatMessage`` complet ; ``stream_answer``
yield des ``ChatAnswerChunk`` (deltas, puis un dernier porteur du message final avec
citations + coût). La préparation (retrieve + assemblage) et la finalisation
(citations + coût) sont mutualisées.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import dataclass
from datetime import UTC, datetime

from fahmi2.chat.citations import parse_citations
from fahmi2.chat.prompt_builder import build_chat_messages
from fahmi2.core.retrieval.passages import PassageRetriever
from fahmi2.domain.chat import ChatMessage, ChatSettings, RetrievedPassage
from fahmi2.domain.enums import Language
from fahmi2.infra.llm.interface import LLMProvider, LLMResponse, Message
from fahmi2.infra.prompts.loader import PromptLoader


@dataclass(frozen=True)
class ChatAnswerChunk:
    """Fragment de réponse du chat.

    Attributes:
        content_delta: Incrément de texte (vide sur le chunk final).
        message: ``ChatMessage`` complet, présent uniquement sur le chunk final.
    """

    content_delta: str
    message: ChatMessage | None = None


class ChatService:
    """Produit une réponse ancrée à partir d'une question et du corpus."""

    def __init__(
        self, *, llm_provider: LLMProvider, prompt_loader: PromptLoader
    ) -> None:
        """Construit le service.

        Args:
            llm_provider: Provider LLM (DeepSeek en production).
            prompt_loader: Loader de prompts (override > défaut).
        """
        self._llm = llm_provider
        self._prompts = prompt_loader

    def answer(
        self,
        *,
        question: str,
        retriever: PassageRetriever,
        glossary_text: str,
        history: tuple[ChatMessage, ...],
        settings: ChatSettings,
        language: Language,
    ) -> ChatMessage:
        """Génère la réponse assistant (non-streaming).

        Args:
            question: Question de l'utilisateur.
            retriever: Retriever de passages.
            glossary_text: Glossaire pertinent formaté (vide si aucun).
            history: Historique de la conversation (hors question courante).
            settings: Réglages du chat.
            language: Langue de réponse.

        Returns:
            Le ``ChatMessage`` assistant (contenu + citations + coût).
        """
        messages, passages = self._prepare(
            question=question,
            retriever=retriever,
            glossary_text=glossary_text,
            history=history,
            settings=settings,
            language=language,
        )
        response = self._llm.chat(
            messages=messages,
            model=str(settings.model),
            thinking=settings.thinking_enabled,
            reasoning_effort=self._reasoning_effort(settings),
            temperature=settings.temperature,
        )
        return self._build_message(response, passages)

    def stream_answer(
        self,
        *,
        question: str,
        retriever: PassageRetriever,
        glossary_text: str,
        history: tuple[ChatMessage, ...],
        settings: ChatSettings,
        language: Language,
    ) -> Iterator[ChatAnswerChunk]:
        """Génère la réponse en flux (deltas, puis chunk final porteur du message).

        Args:
            question: Question de l'utilisateur.
            retriever: Retriever de passages.
            glossary_text: Glossaire pertinent formaté (vide si aucun).
            history: Historique de la conversation (hors question courante).
            settings: Réglages du chat.
            language: Langue de réponse.

        Yields:
            ``ChatAnswerChunk`` (deltas avec ``message=None``, puis un dernier
            portant le ``ChatMessage`` complet).
        """
        messages, passages = self._prepare(
            question=question,
            retriever=retriever,
            glossary_text=glossary_text,
            history=history,
            settings=settings,
            language=language,
        )
        content_parts: list[str] = []
        final_response: LLMResponse | None = None
        for chunk in self._llm.chat_stream(
            messages=messages,
            model=str(settings.model),
            thinking=settings.thinking_enabled,
            reasoning_effort=self._reasoning_effort(settings),
            temperature=settings.temperature,
        ):
            if chunk.is_final and chunk.response is not None:
                final_response = chunk.response
            elif chunk.content_delta:
                content_parts.append(chunk.content_delta)
                yield ChatAnswerChunk(content_delta=chunk.content_delta)
        response = final_response or LLMResponse(
            content="".join(content_parts),
            thinking_content=None,
            prompt_tokens=0,
            completion_tokens=0,
            cached_prompt_tokens=0,
            cost_usd=0.0,
        )
        yield ChatAnswerChunk(
            content_delta="", message=self._build_message(response, passages)
        )

    def _prepare(
        self,
        *,
        question: str,
        retriever: PassageRetriever,
        glossary_text: str,
        history: tuple[ChatMessage, ...],
        settings: ChatSettings,
        language: Language,
    ) -> tuple[list[Message], tuple[RetrievedPassage, ...]]:
        """Récupère les passages et assemble les messages (commun answer/stream).

        Args:
            question: Question de l'utilisateur.
            retriever: Retriever de passages.
            glossary_text: Glossaire pertinent formaté.
            history: Historique de la conversation.
            settings: Réglages du chat.
            language: Langue de réponse.

        Returns:
            ``(messages, passages)``.
        """
        passages = tuple(retriever.retrieve(query=question, top_k=settings.top_k))
        messages = build_chat_messages(
            question=question,
            passages=passages,
            glossary_text=glossary_text,
            history=history,
            settings=settings,
            language=language,
            prompt_loader=self._prompts,
        )
        return messages, passages

    def _build_message(
        self, response: LLMResponse, passages: tuple[RetrievedPassage, ...]
    ) -> ChatMessage:
        """Construit le ``ChatMessage`` assistant final (citations + coût).

        Args:
            response: Réponse LLM (complète).
            passages: Passages numérotés fournis au prompt.

        Returns:
            Le ``ChatMessage`` assistant.
        """
        return ChatMessage(
            role="assistant",
            content=response.content,
            citations=parse_citations(response.content, passages),
            cost_usd=response.cost_usd,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            created_at=datetime.now(tz=UTC),
        )

    @staticmethod
    def _reasoning_effort(settings: ChatSettings) -> str | None:
        """Niveau d'effort de raisonnement sous forme de chaîne, ou ``None``."""
        return (
            str(settings.reasoning_effort)
            if settings.reasoning_effort is not None
            else None
        )
