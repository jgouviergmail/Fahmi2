"""Persistance des conversations du chat (JSON sous ``<workspace>/chat/``).

Sérialisation domaine ↔ JSON, écriture atomique via ``FsArtifactStore``. Une
conversation = un fichier ``conversations/{conversation_id}.json``, relisible hors
session active.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from fahmi2.domain.chat import ChatMessage, ChatRole, Citation, Conversation
from fahmi2.domain.enums import Language
from fahmi2.domain.ids import ConversationId
from fahmi2.infra.storage.fs_artifacts import FsArtifactStore

_CONVERSATIONS_SUBDIR = "conversations"
_FILE_SUFFIX = ".json"
_ENCODING_UTF8 = "utf-8"
_ROLE_ASSISTANT: ChatRole = "assistant"


def _iso_or_none(value: datetime | None) -> str | None:
    """Sérialise un datetime en ISO, ou ``None``."""
    return value.isoformat() if value is not None else None


def _datetime_or_none(value: Any) -> datetime | None:  # noqa: ANN401
    """Désérialise un ISO en datetime, ou ``None``."""
    return datetime.fromisoformat(str(value)) if value else None


def _serialize_citation(citation: Citation) -> dict[str, Any]:
    return {
        "chapter_title": citation.chapter_title,
        "section_title": citation.section_title,
        "anchor": citation.anchor,
        "snippet": citation.snippet,
    }


def _serialize_message(message: ChatMessage) -> dict[str, Any]:
    return {
        "role": message.role,
        "content": message.content,
        "citations": [_serialize_citation(c) for c in message.citations],
        "cost_usd": message.cost_usd,
        "prompt_tokens": message.prompt_tokens,
        "completion_tokens": message.completion_tokens,
        "created_at": _iso_or_none(message.created_at),
    }


def _deserialize_message(payload: dict[str, Any]) -> ChatMessage:
    role: ChatRole = (
        _ROLE_ASSISTANT if payload["role"] == _ROLE_ASSISTANT else "user"
    )
    citations = tuple(
        Citation(
            chapter_title=str(c["chapter_title"]),
            section_title=str(c["section_title"]),
            anchor=str(c["anchor"]),
            snippet=str(c["snippet"]),
        )
        for c in payload.get("citations", [])
    )
    return ChatMessage(
        role=role,
        content=str(payload["content"]),
        citations=citations,
        cost_usd=float(payload.get("cost_usd", 0.0)),
        prompt_tokens=int(payload.get("prompt_tokens", 0)),
        completion_tokens=int(payload.get("completion_tokens", 0)),
        created_at=_datetime_or_none(payload.get("created_at")),
    )


class ChatConversationStore:
    """CRUD fichiers des conversations d'un projet."""

    def __init__(self, *, artifacts: FsArtifactStore, chat_dir: Path) -> None:
        """Construit le store.

        Args:
            artifacts: Store d'écriture atomique.
            chat_dir: Dossier ``<workspace>/chat`` de la fonctionnalité.
        """
        self._artifacts = artifacts
        self._dir = chat_dir / _CONVERSATIONS_SUBDIR

    def save(self, conversation: Conversation) -> None:
        """Persiste une conversation (écrase si elle existe).

        Args:
            conversation: Conversation à enregistrer.
        """
        payload: dict[str, Any] = {
            "conversation_id": conversation.conversation_id.value,
            "title": conversation.title,
            "language": str(conversation.language),
            "messages": [_serialize_message(m) for m in conversation.messages],
            "created_at": _iso_or_none(conversation.created_at),
            "updated_at": _iso_or_none(conversation.updated_at),
        }
        self._artifacts.write_json_atomic(
            self._path(conversation.conversation_id), payload
        )

    def load(self, conversation_id: ConversationId) -> Conversation | None:
        """Charge une conversation, ou ``None`` si absente.

        Args:
            conversation_id: Identifiant.

        Returns:
            La ``Conversation``, ou ``None``.
        """
        path = self._path(conversation_id)
        if not path.exists():
            return None
        return self._from_payload(json.loads(path.read_text(encoding=_ENCODING_UTF8)))

    def list_all(self) -> tuple[Conversation, ...]:
        """Liste toutes les conversations du projet (triées par nom de fichier).

        Returns:
            Tuple de conversations (vide si aucune).
        """
        if not self._dir.exists():
            return ()
        return tuple(
            self._from_payload(json.loads(path.read_text(encoding=_ENCODING_UTF8)))
            for path in sorted(self._dir.glob(f"*{_FILE_SUFFIX}"))
        )

    def delete(self, conversation_id: ConversationId) -> None:
        """Supprime une conversation (idempotent).

        Args:
            conversation_id: Identifiant.
        """
        path = self._path(conversation_id)
        if path.exists():
            path.unlink()

    def _path(self, conversation_id: ConversationId) -> Path:
        return self._dir / f"{conversation_id.value}{_FILE_SUFFIX}"

    @staticmethod
    def _from_payload(payload: dict[str, Any]) -> Conversation:
        return Conversation(
            conversation_id=ConversationId(value=str(payload["conversation_id"])),
            title=str(payload["title"]),
            language=Language(str(payload["language"])),
            messages=tuple(
                _deserialize_message(m) for m in payload.get("messages", [])
            ),
            created_at=_datetime_or_none(payload.get("created_at")),
            updated_at=_datetime_or_none(payload.get("updated_at")),
        )
