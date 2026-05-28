"""Tests de ``app.theme_controller.ThemeController``.

Couvre le cycle de vie : lecture de préférence au démarrage, application
immédiate, persistance lors d'un changement, idempotence si le mode est
inchangé.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QApplication

from fahmi2.app.theme_controller import ThemeController
from fahmi2.app.ui_preferences import (
    UiPreferences,
    read_ui_preferences,
    write_ui_preferences,
)
from fahmi2.ui.theme._tokens import (
    DARK_TOKENS,
    LIGHT_TOKENS,
    ThemeMode,
    current_palette,
    set_current_palette,
)


def test_controller_reads_initial_preference_and_applies(
    qtbot: object, tmp_path: Path
) -> None:
    """L'initialisation lit la préférence sur disque et applique le mode lu."""
    del qtbot
    prefs_path = tmp_path / "ui_prefs.json"
    write_ui_preferences(prefs_path, UiPreferences(theme_mode=ThemeMode.DARK))

    app = QApplication.instance()
    assert isinstance(app, QApplication)
    controller = ThemeController(app, prefs_path)
    try:
        assert controller.mode is ThemeMode.DARK
        # ``apply_theme(DARK)`` a aussi mis la palette sombre en palette active.
        assert current_palette() is DARK_TOKENS
    finally:
        # Restauration pour ne pas polluer les autres tests.
        controller.set_mode(ThemeMode.LIGHT)
        set_current_palette(LIGHT_TOKENS)


def test_set_mode_persists_to_disk(qtbot: object, tmp_path: Path) -> None:
    """``set_mode`` écrit la nouvelle préférence sur disque."""
    del qtbot
    prefs_path = tmp_path / "ui_prefs.json"
    app = QApplication.instance()
    assert isinstance(app, QApplication)
    controller = ThemeController(app, prefs_path)
    try:
        controller.set_mode(ThemeMode.DARK)
        assert read_ui_preferences(prefs_path).theme_mode is ThemeMode.DARK
        controller.set_mode(ThemeMode.LIGHT)
        assert read_ui_preferences(prefs_path).theme_mode is ThemeMode.LIGHT
    finally:
        set_current_palette(LIGHT_TOKENS)


def test_set_mode_idempotent_skips_when_same(qtbot: object, tmp_path: Path) -> None:
    """``set_mode`` ne réécrit pas la préférence si le mode est inchangé."""
    del qtbot
    prefs_path = tmp_path / "ui_prefs.json"
    app = QApplication.instance()
    assert isinstance(app, QApplication)
    controller = ThemeController(app, prefs_path)
    try:
        controller.set_mode(ThemeMode.DARK)
        mtime_before = prefs_path.stat().st_mtime_ns
        # Tente le même mode : on ne ré-écrit pas.
        controller.set_mode(ThemeMode.DARK)
        mtime_after = prefs_path.stat().st_mtime_ns
        assert mtime_after == mtime_before
    finally:
        controller.set_mode(ThemeMode.LIGHT)
        set_current_palette(LIGHT_TOKENS)


def test_set_mode_updates_current_palette(qtbot: object, tmp_path: Path) -> None:
    """Un changement de mode actualise la palette active."""
    del qtbot
    prefs_path = tmp_path / "ui_prefs.json"
    app = QApplication.instance()
    assert isinstance(app, QApplication)
    controller = ThemeController(app, prefs_path)
    try:
        controller.set_mode(ThemeMode.LIGHT)
        assert current_palette() is LIGHT_TOKENS
        controller.set_mode(ThemeMode.DARK)
        assert current_palette() is DARK_TOKENS
    finally:
        controller.set_mode(ThemeMode.LIGHT)
        set_current_palette(LIGHT_TOKENS)
