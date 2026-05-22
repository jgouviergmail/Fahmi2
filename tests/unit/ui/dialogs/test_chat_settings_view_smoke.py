"""Smoke tests du dialogue de réglages du chat (pytest-qt)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fahmi2.domain.chat import ChatSettings
from fahmi2.domain.enums import ChatGroundingMode, ReasoningEffort, RetrievalStrategy
from fahmi2.ui.dialogs.chat_settings_view import ChatSettingsView


def test_defaults_roundtrip(qtbot: QtBot) -> None:
    dialog = ChatSettingsView()
    qtbot.addWidget(dialog)
    result = dialog.get_chat_settings()
    assert result.grounding_mode is ChatGroundingMode.STRICT
    assert result.retrieval_strategy is RetrievalStrategy.AUTO
    assert result.reasoning_effort is None


def test_initial_values_roundtrip(qtbot: QtBot) -> None:
    initial = ChatSettings(
        grounding_mode=ChatGroundingMode.AUGMENTED,
        retrieval_strategy=RetrievalStrategy.LEXICAL,
        query_expansion_enabled=False,
        thinking_enabled=True,
        reasoning_effort=ReasoningEffort.MAX,
        top_k=9,
    )
    dialog = ChatSettingsView(initial=initial)
    qtbot.addWidget(dialog)
    result = dialog.get_chat_settings()
    assert result.grounding_mode is ChatGroundingMode.AUGMENTED
    assert result.retrieval_strategy is RetrievalStrategy.LEXICAL
    assert result.query_expansion_enabled is False
    assert result.thinking_enabled is True
    assert result.reasoning_effort is ReasoningEffort.MAX
    assert result.top_k == 9
