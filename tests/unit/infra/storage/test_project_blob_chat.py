"""Tests de la persistance des ChatSettings dans le blob projet v2."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from fahmi2.domain.chat import ChatSettings
from fahmi2.domain.enums import ChatGroundingMode, RetrievalStrategy
from fahmi2.domain.ids import ProjectId
from fahmi2.domain.project import Project
from fahmi2.infra.storage.sqlite_state import SqliteState


def _project(chat: ChatSettings | None) -> Project:
    return Project(
        id=ProjectId.new(),
        name="P",
        workspace_folder=Path("./ws"),
        created_at=datetime.now(tz=UTC),
        chat=chat,
    )


def test_chat_settings_roundtrip(tmp_path: Path) -> None:
    state = SqliteState(tmp_path / "state.db")
    project = _project(
        ChatSettings(
            grounding_mode=ChatGroundingMode.AUGMENTED,
            retrieval_strategy=RetrievalStrategy.LEXICAL,
            top_k=9,
        )
    )
    state.upsert_project(project)
    loaded = state.get_project(project.id)
    assert loaded is not None
    assert loaded.chat is not None
    assert loaded.chat.grounding_mode is ChatGroundingMode.AUGMENTED
    assert loaded.chat.retrieval_strategy is RetrievalStrategy.LEXICAL
    assert loaded.chat.top_k == 9


def test_chat_absent_defaults_to_none(tmp_path: Path) -> None:
    state = SqliteState(tmp_path / "state.db")
    project = _project(None)
    state.upsert_project(project)
    loaded = state.get_project(project.id)
    assert loaded is not None
    assert loaded.chat is None
