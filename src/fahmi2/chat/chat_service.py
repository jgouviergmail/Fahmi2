"""Moteur de chat (réponse non-streaming) : retrieve → prompt → LLM → citations.

Orchestrateur léger : récupère les passages, assemble les messages (fidélité),
appelle le LLM, parse les citations et construit un ``ChatMessage``. Le retry et
le streaming sont ajoutés au Lot 3.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fahmi2.chat.citations import parse_citations
from fahmi2.chat.prompt_builder import build_chat_messages
from fahmi2.core.retrieval.passages import PassageRetriever
from fahmi2.domain.chat import ChatMessage, ChatSettings
from fahmi2.domain.enums import Language
from fahmi2.infra.llm.interface import LLMProvider
from fahmi2.infra.prompts.loader import PromptLoader


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
        """Génère la réponse assistant à une question.

        Args:
            question: Question de l'utilisateur.
            retriever: Retriever de passages (lexical au Lot 2).
            glossary_text: Glossaire pertinent formaté (vide si aucun).
            history: Historique de la conversation (hors question courante).
            settings: Réglages du chat.
            language: Langue de réponse.

        Returns:
            Le ``ChatMessage`` assistant (contenu + citations + coût).
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
        # Chat multi-tours : on passe la liste complète de Message (système +
        # historique + question) directement au provider.
        response = self._llm.chat(
            messages=messages,
            model=str(settings.model),
            thinking=settings.thinking_enabled,
            reasoning_effort=(
                str(settings.reasoning_effort)
                if settings.reasoning_effort is not None
                else None
            ),
            temperature=settings.temperature,
        )
        citations = parse_citations(response.content, passages)
        return ChatMessage(
            role="assistant",
            content=response.content,
            citations=citations,
            cost_usd=response.cost_usd,
            prompt_tokens=response.prompt_tokens,
            completion_tokens=response.completion_tokens,
            created_at=datetime.now(tz=UTC),
        )
