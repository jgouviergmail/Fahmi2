"""Tests du dialogue minimal ``NewProjectDialog`` (nom + emplacement)."""

from __future__ import annotations

from pathlib import Path

import pytest
from pytestqt.qtbot import QtBot

from fahmi2.ui.dialogs.new_project_dialog import NewProjectDialog


def test_create_mode_returns_name_and_workspace(qtbot: QtBot) -> None:
    dialog = NewProjectDialog()
    qtbot.addWidget(dialog)
    dialog._name_input.setText("Cours de macro")  # noqa: SLF001
    dialog._workspace_input.setText("D:/Projets/Macro")  # noqa: SLF001
    dialog._on_accept()  # noqa: SLF001
    assert dialog.get_name() == "Cours de macro"
    assert dialog.get_workspace_folder() == Path("D:/Projets/Macro")


def test_create_mode_requires_both_fields(
    qtbot: QtBot, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        "fahmi2.ui.dialogs.new_project_dialog.QMessageBox.warning",
        lambda *a, **k: None,
    )
    dialog = NewProjectDialog()
    qtbot.addWidget(dialog)
    dialog._name_input.setText("Sans emplacement")  # noqa: SLF001
    dialog._on_accept()  # noqa: SLF001
    assert dialog.get_name() is None


def test_edit_mode_makes_workspace_read_only(qtbot: QtBot) -> None:
    dialog = NewProjectDialog(initial_name="Existant", initial_workspace=Path("D:/WS"))
    qtbot.addWidget(dialog)
    assert dialog._workspace_input.isReadOnly()  # noqa: SLF001
    assert dialog._name_input.text() == "Existant"  # noqa: SLF001
