"""ViewModel du chat de dialogue (logique d'état, sans Qt — testable).

Concentre la logique testable de l'onglet Dialogue : machine d'état (cf. spec
§10.1) et cycle de vie de la conversation courante (titre auto, ajout de tours).
Ne dépend ni de Qt ni d'``infra``.
"""

from __future__ import annotations

from dataclasses import replace

from fahmi2.domain.chat import ChatMessage, Conversation
from fahmi2.domain.enums import ChatTabState, Language
from fahmi2.domain.ids import ConversationId

_TITLE_MAX_CHARS = 60
_UNTITLED = "Nouvelle conversation"


class ChatViewModel:
    """Logique d'état de l'onglet Dialogue (indépendante de Qt)."""

    def resolve_state(
        self,
        *,
        has_project: bool,
        has_corpus: bool,
        is_answering: bool,
        has_error: bool,
    ) -> ChatTabState:
        """Détermine l'état courant de l'onglet.

        Args:
            has_project: Un projet est sélectionné.
            has_corpus: Le corpus (consolidé) existe pour le projet.
            is_answering: Une réponse est en cours de génération.
            has_error: Une erreur est à signaler.

        Returns:
            L'état UX courant.
        """
        if not has_project:
            return ChatTabState.NO_PROJECT
        if not has_corpus:
            return ChatTabState.NO_CORPUS
        if has_error:
            return ChatTabState.ERROR
        if is_answering:
            return ChatTabState.ANSWERING
        return ChatTabState.READY

    def start_conversation(self, language: Language) -> Conversation:
        """Crée une conversation vide.

        Args:
            language: Langue de réponse.

        Returns:
            Une ``Conversation`` neuve (titre provisoire).
        """
        return Conversation(
            conversation_id=ConversationId.new(),
            title=_UNTITLED,
            language=language,
        )

    def derive_title(self, question: str) -> str:
        """Dérive un titre lisible d'une question (tronqué).

        Args:
            question: Première question de la conversation.

        Returns:
            Le titre (tronqué à ``_TITLE_MAX_CHARS``).
        """
        cleaned = question.strip().replace("\n", " ")
        if not cleaned:
            return _UNTITLED
        if len(cleaned) <= _TITLE_MAX_CHARS:
            return cleaned
        return f"{cleaned[:_TITLE_MAX_CHARS].rstrip()}…"

    def append_user(self, conversation: Conversation, question: str) -> Conversation:
        """Ajoute la question ; fixe le titre si c'est le premier message.

        Args:
            conversation: Conversation courante.
            question: Question de l'utilisateur.

        Returns:
            La conversation mise à jour (immuable).
        """
        updated = conversation.with_message(
            ChatMessage(role="user", content=question)
        )
        if not conversation.messages:
            return replace(updated, title=self.derive_title(question))
        return updated

    def append_assistant(
        self, conversation: Conversation, message: ChatMessage
    ) -> Conversation:
        """Ajoute la réponse assistant.

        Args:
            conversation: Conversation courante.
            message: Message assistant (avec citations + coût).

        Returns:
            La conversation mise à jour (immuable).
        """
        return conversation.with_message(message)
