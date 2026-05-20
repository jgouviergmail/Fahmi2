"""Tests du composant master-detail ``SettingsView``."""

from __future__ import annotations

from PySide6.QtWidgets import QLabel
from pytestqt.qtbot import QtBot

from fahmi2.ui.widgets.settings_view import SettingsView


def test_settings_view_lists_categories_and_switches(qtbot: QtBot) -> None:
    page_a = QLabel("A")
    page_b = QLabel("B")
    view = SettingsView([("Cat A", page_a), ("Cat B", page_b)])
    qtbot.addWidget(view)

    assert view.category_count() == 2
    assert view.current_index() == 0

    view.set_current_index(1)
    assert view.current_index() == 1


def test_settings_view_empty_is_safe(qtbot: QtBot) -> None:
    view = SettingsView([])
    qtbot.addWidget(view)
    assert view.category_count() == 0
    assert view.current_index() == -1
