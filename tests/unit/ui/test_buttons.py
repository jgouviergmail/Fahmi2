"""Tests du helper de boutons stylés par rôle (pytest-qt)."""

from __future__ import annotations

from PySide6.QtWidgets import QWidget
from pytestqt.qtbot import QtBot

from fahmi2.ui._buttons import BUTTON_ROLE_PRIMARY, make_role_button


def test_make_role_button_sets_role_and_text(qtbot: QtBot) -> None:
    parent = QWidget()
    qtbot.addWidget(parent)
    button = make_role_button(parent, "OK", role=BUTTON_ROLE_PRIMARY)
    assert button.property("role") == "primary"
    assert button.text() == "OK"
