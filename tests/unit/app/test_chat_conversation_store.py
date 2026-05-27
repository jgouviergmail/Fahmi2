"""Tests de la persistance des conversations du chat."""

from __future__ import annotations

import json
from pathlib import Path

from fahmi2.app.chat_conversation_store import ChatConversationStore
from fahmi2.domain.chat import ChatMessage, Citation, Conversation
from fahmi2.domain.enums import Language
from fahmi2.domain.ids import ConversationId
from fahmi2.infra.storage.fs_artifacts import FsArtifactStore


def _store(tmp_path: Path) -> ChatConversationStore:
    return ChatConversationStore(artifacts=FsArtifactStore(), chat_dir=tmp_path)


def _conversation() -> Conversation:
    return Conversation(
        conversation_id=ConversationId.new(),
        title="Le PIB",
        language=Language.FR,
        messages=(
            ChatMessage(role="user", content="Qu'est-ce que le PIB ?"),
            ChatMessage(
                role="assistant",
                content="Le PIB [§1].",
                citations=(
                    Citation(
                        number=1,
                        chapter_title="Éco",
                        section_title="PIB",
                        anchor="pib",
                        snippet="Le produit intérieur brut…",
                    ),
                ),
                cost_usd=0.02,
            ),
        ),
    )


def test_save_then_load_roundtrip(tmp_path: Path) -> None:
    store = _store(tmp_path)
    conv = _conversation()
    store.save(conv)
    loaded = store.load(conv.conversation_id)
    assert loaded is not None
    assert loaded.title == "Le PIB"
    assert len(loaded.messages) == 2
    assert loaded.messages[1].cost_usd == 0.02
    assert loaded.messages[1].citations[0].anchor == "pib"


def test_load_legacy_citation_without_number_falls_back_to_position(
    tmp_path: Path,
) -> None:
    store = _store(tmp_path)
    conv = _conversation()
    store.save(conv)
    # Simule un fichier antérieur : retire la clé "number" des citations.
    path = tmp_path / "conversations" / f"{conv.conversation_id.value}.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    for message in payload["messages"]:
        for citation in message["citations"]:
            citation.pop("number", None)
    path.write_text(json.dumps(payload), encoding="utf-8")
    loaded = store.load(conv.conversation_id)
    assert loaded is not None
    assert loaded.messages[1].citations[0].number == 1  # 1er = position 1


def test_list_and_delete(tmp_path: Path) -> None:
    store = _store(tmp_path)
    conv = _conversation()
    store.save(conv)
    assert [c.conversation_id for c in store.list_all()] == [conv.conversation_id]
    store.delete(conv.conversation_id)
    assert store.list_all() == ()
    assert store.load(conv.conversation_id) is None
