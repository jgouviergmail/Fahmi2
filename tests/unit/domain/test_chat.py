"""Tests des entités et enums du chat de dialogue."""

from __future__ import annotations

from fahmi2.domain.chat import (
    ChatMessage,
    ChatSettings,
    Citation,
    Conversation,
    CorpusChunk,
    RetrievedPassage,
)
from fahmi2.domain.enums import (
    ChatGroundingMode,
    Language,
    LLMModel,
    RetrievalStrategy,
)
from fahmi2.domain.ids import ConversationId


def test_grounding_mode_values() -> None:
    assert ChatGroundingMode.STRICT.value == "strict"
    assert ChatGroundingMode.AUGMENTED.value == "augmented"


def test_retrieval_strategy_values() -> None:
    assert RetrievalStrategy.AUTO.value == "auto"
    assert RetrievalStrategy.LEXICAL.value == "lexical"
    assert RetrievalStrategy.SEMANTIC.value == "semantic"


def test_conversation_id_is_distinct_ulid() -> None:
    cid = ConversationId.new()
    assert isinstance(cid.value, str)
    assert len(cid.value) == 26
    assert ConversationId(value=cid.value) == cid


def test_corpus_chunk_and_passage() -> None:
    chunk = CorpusChunk(
        chunk_id="1-bases::0",
        chapter_title="Bases",
        section_title="Bases",
        anchor="1-bases",
        text="contenu",
        origin="consolidated",
    )
    passage = RetrievedPassage(chunk=chunk, score=0.8)
    assert passage.chunk.anchor == "1-bases"
    assert passage.score == 0.8


def test_chat_message_defaults() -> None:
    msg = ChatMessage(role="user", content="bonjour")
    assert msg.role == "user"
    assert msg.citations == ()
    assert msg.cost_usd == 0.0


def test_citation_fields() -> None:
    cit = Citation(
        chapter_title="Bases", section_title="1.1", anchor="11", snippet="…"
    )
    assert cit.anchor == "11"


def test_conversation_with_message_and_total_cost() -> None:
    conv = Conversation(
        conversation_id=ConversationId.new(), title="Q1", language=Language.FR
    )
    conv2 = conv.with_message(ChatMessage(role="user", content="q"))
    conv3 = conv2.with_message(
        ChatMessage(role="assistant", content="r", cost_usd=0.02)
    )
    assert conv.messages == ()  # immuable : l'original est inchangé
    assert len(conv3.messages) == 2
    assert conv3.total_cost_usd() == 0.02


def test_chat_settings_defaults() -> None:
    settings = ChatSettings()
    assert settings.grounding_mode is ChatGroundingMode.STRICT
    assert settings.retrieval_strategy is RetrievalStrategy.AUTO
    assert settings.query_expansion_enabled is True
    assert settings.model is LLMModel.DEEPSEEK_V4_FLASH
    assert settings.thinking_enabled is False
    assert settings.top_k == 6


def test_chat_settings_with_helpers() -> None:
    settings = ChatSettings().with_grounding_mode(ChatGroundingMode.AUGMENTED)
    assert settings.grounding_mode is ChatGroundingMode.AUGMENTED
    other = settings.with_retrieval_strategy(RetrievalStrategy.LEXICAL)
    assert other.retrieval_strategy is RetrievalStrategy.LEXICAL
    assert settings.retrieval_strategy is RetrievalStrategy.AUTO  # original inchangé
