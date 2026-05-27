"""Entités immuables du chat de dialogue ancré sur le corpus.

``domain/`` ne dépend ni d'``infra`` ni de Qt : le rôle d'un message est un type
**du domaine** (``ChatRole``), distinct du ``Role`` d'``infra/llm`` ; la conversion
``ChatMessage`` → ``infra/llm.Message`` se fait dans ``chat/prompt_builder.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from typing import Literal

from fahmi2.domain.enums import (
    ChatGroundingMode,
    EmbeddingModel,
    Language,
    LLMModel,
    ReasoningEffort,
    RetrievalStrategy,
)
from fahmi2.domain.ids import ConversationId

ChatRole = Literal["user", "assistant"]

#: Sous-dossier du workspace dédié à la fonctionnalité Dialogue (chat).
CHAT_WORKSPACE_SUBDIR = "chat"

_DEFAULT_CHAT_TEMPERATURE = 0.3
_DEFAULT_TOP_K = 6


@dataclass(frozen=True)
class CorpusChunk:
    """Passage indexable du corpus (section du consolidé ou entrée de glossaire).

    Attributes:
        chunk_id: Identifiant stable du chunk (ancre + ordinal, ou ``glossary::…``).
        chapter_title: Titre du chapitre d'origine.
        section_title: Titre de la section (ou du chapitre à défaut).
        anchor: Ancre GFM (``slugify_anchor``) → citation cliquable.
        text: Contenu textuel du passage.
        origin: ``"consolidated"`` ou ``"glossary"``.
    """

    chunk_id: str
    chapter_title: str
    section_title: str
    anchor: str
    text: str
    origin: str


@dataclass(frozen=True)
class RetrievedPassage:
    """Passage récupéré + score de pertinence.

    Attributes:
        chunk: Le passage du corpus.
        score: Score de pertinence (cosine), croissant = plus pertinent.
    """

    chunk: CorpusChunk
    score: float


@dataclass(frozen=True)
class Citation:
    """Référence vers un passage cité dans une réponse.

    Attributes:
        number: Numéro d'affichage 1-based, séquentiel par ordre d'apparition
            (dédupliqué par ancre) ; relie le marqueur ``[N]`` du corps à la
            ligne « Sources ».
        chapter_title: Titre du chapitre cité.
        section_title: Titre de la section citée.
        anchor: Ancre GFM du passage (lien cliquable).
        snippet: Court extrait du passage cité.
    """

    number: int
    chapter_title: str
    section_title: str
    anchor: str
    snippet: str


@dataclass(frozen=True)
class ChatMessage:
    """Un tour de conversation (question ou réponse).

    Attributes:
        role: ``"user"`` ou ``"assistant"``.
        content: Contenu textuel du message.
        citations: Citations associées (réponses ancrées uniquement).
        cost_usd: Coût LLM du message (0 pour une question).
        prompt_tokens: Tokens d'entrée consommés.
        completion_tokens: Tokens de sortie générés.
        created_at: Horodatage de création (``None`` si non daté).
    """

    role: ChatRole
    content: str
    citations: tuple[Citation, ...] = ()
    cost_usd: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    created_at: datetime | None = None


@dataclass(frozen=True)
class Conversation:
    """Conversation persistée, propre à un projet.

    Attributes:
        conversation_id: Identifiant stable.
        title: Titre (dérivé de la 1ʳᵉ question, renommable).
        language: Langue de réponse.
        messages: Tours de la conversation, dans l'ordre.
        created_at: Horodatage de création.
        updated_at: Horodatage de dernière mise à jour.
    """

    conversation_id: ConversationId
    title: str
    language: Language
    messages: tuple[ChatMessage, ...] = ()
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def with_message(self, message: ChatMessage) -> Conversation:
        """Retourne une copie avec ``message`` ajouté en fin.

        Args:
            message: Tour à ajouter.

        Returns:
            Nouvelle instance immuable.
        """
        return replace(self, messages=(*self.messages, message))

    def total_cost_usd(self) -> float:
        """Somme des coûts des messages de la conversation.

        Returns:
            Coût cumulé en USD.
        """
        return sum(message.cost_usd for message in self.messages)


@dataclass(frozen=True)
class ChatSettings:
    """Réglages de l'onglet Dialogue (blob ``settings_json`` v2, clé ``chat``).

    Attributes:
        grounding_mode: Posture de fidélité (strict par défaut).
        retrieval_strategy: Stratégie de retrieval (``AUTO`` par défaut).
        query_expansion_enabled: Active la reformulation LLM si retrieval faible.
        model: Modèle LLM pour les réponses.
        embedding_model: Modèle d'embedding (retrieval sémantique ; ignoré en
            lexical). Changer ce modèle force une réindexation du corpus.
        thinking_enabled: Active le mode raisonnement DeepSeek.
        reasoning_effort: Niveau de raisonnement (si ``thinking_enabled``).
        temperature: Température LLM.
        top_k: Nombre de passages injectés en contexte.
    """

    grounding_mode: ChatGroundingMode = ChatGroundingMode.STRICT
    retrieval_strategy: RetrievalStrategy = RetrievalStrategy.AUTO
    query_expansion_enabled: bool = True
    model: LLMModel = LLMModel.DEEPSEEK_V4_FLASH
    embedding_model: EmbeddingModel = EmbeddingModel.TEXT_EMBEDDING_3_SMALL
    thinking_enabled: bool = False
    reasoning_effort: ReasoningEffort | None = None
    temperature: float = _DEFAULT_CHAT_TEMPERATURE
    top_k: int = _DEFAULT_TOP_K
