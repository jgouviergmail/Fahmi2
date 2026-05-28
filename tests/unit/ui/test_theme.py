"""Tests du module ``ui.theme`` : ``ThemeMode``, ``apply_theme``, ``resolve_mode``."""

from __future__ import annotations

import pytest
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QFrame, QGraphicsDropShadowEffect

from fahmi2.ui._components import (
    CARD_OBJECT_NAME,
    install_shadow,
)
from fahmi2.ui.theme import (
    ThemeMode,
    apply_theme,
    load_theme_qss,
    load_theme_qss_for,
    resolve_mode,
)
from fahmi2.ui.theme._tokens import (
    DARK_TOKENS,
    LIGHT_TOKENS,
    current_palette,
    palette_for,
    set_current_palette,
)


def test_theme_mode_enum_values() -> None:
    """``ThemeMode`` expose les trois valeurs attendues."""
    assert ThemeMode.SYSTEM.value == "system"
    assert ThemeMode.LIGHT.value == "light"
    assert ThemeMode.DARK.value == "dark"


def test_load_theme_qss_returns_light_for_backcompat() -> None:
    """``load_theme_qss`` retourne le QSS clair (back-compat historique)."""
    qss = load_theme_qss()
    assert isinstance(qss, str)
    assert len(qss) > 100
    # Marqueurs de l'ancien thème, conservés pour back-compat
    assert "#statCard" in qss
    assert "#projectHeaderBar" in qss


def test_load_theme_qss_for_returns_light_or_dark() -> None:
    """``load_theme_qss_for`` charge le bon QSS selon le mode résolu."""
    light = load_theme_qss_for(ThemeMode.LIGHT)
    dark = load_theme_qss_for(ThemeMode.DARK)
    assert light != dark
    # Marqueurs distinctifs : couleurs de fond globales différentes
    assert "#f5f7fb" in light  # token --bg clair
    assert "#11151c" in dark  # token --bg sombre


def test_load_theme_qss_for_rejects_system() -> None:
    """``load_theme_qss_for(SYSTEM)`` lève ``ValueError`` (non résolu)."""
    with pytest.raises(ValueError):
        load_theme_qss_for(ThemeMode.SYSTEM)


def test_palette_for_returns_light_or_dark() -> None:
    """``palette_for`` retourne la palette correspondante."""
    assert palette_for(ThemeMode.LIGHT) is LIGHT_TOKENS
    assert palette_for(ThemeMode.DARK) is DARK_TOKENS


def test_palette_for_rejects_system() -> None:
    """``palette_for(SYSTEM)`` lève ``ValueError`` (non résolu)."""
    with pytest.raises(ValueError):
        palette_for(ThemeMode.SYSTEM)


def test_resolve_mode_passes_through_light_and_dark(qtbot: object) -> None:
    """``LIGHT`` et ``DARK`` ne sont pas résolus (renvoyés tels quels)."""
    del qtbot  # le fixture force l'instanciation de QApplication
    assert resolve_mode(ThemeMode.LIGHT) is ThemeMode.LIGHT
    assert resolve_mode(ThemeMode.DARK) is ThemeMode.DARK


def test_resolve_mode_system_returns_light_or_dark(qtbot: object) -> None:
    """``SYSTEM`` est résolu en ``LIGHT`` ou ``DARK`` (jamais ``SYSTEM``)."""
    del qtbot
    resolved = resolve_mode(ThemeMode.SYSTEM)
    assert resolved in (ThemeMode.LIGHT, ThemeMode.DARK)


def test_apply_theme_sets_current_palette_to_light(qtbot: object) -> None:
    """``apply_theme(LIGHT)`` met la palette claire en palette active."""
    del qtbot
    app = QApplication.instance()
    assert isinstance(app, QApplication)
    apply_theme(app, ThemeMode.LIGHT)
    assert current_palette() is LIGHT_TOKENS


def test_apply_theme_sets_current_palette_to_dark(qtbot: object) -> None:
    """``apply_theme(DARK)`` met la palette sombre en palette active."""
    del qtbot
    app = QApplication.instance()
    assert isinstance(app, QApplication)
    apply_theme(app, ThemeMode.DARK)
    assert current_palette() is DARK_TOKENS
    # Restauration pour ne pas polluer les autres tests
    apply_theme(app, ThemeMode.LIGHT)


def test_apply_theme_reapplies_card_shadows(qtbot: object) -> None:
    """``apply_theme`` ré-installe l'ombre sur les cartes existantes.

    Après bascule de thème, une carte créée avant doit voir son effet d'ombre
    actualisé (la couleur d'ombre dépend de la palette active).
    """
    del qtbot
    app = QApplication.instance()
    assert isinstance(app, QApplication)
    apply_theme(app, ThemeMode.LIGHT)
    card = QFrame()
    card.setObjectName(CARD_OBJECT_NAME)
    install_shadow(card)
    effect_before = card.graphicsEffect()
    assert isinstance(effect_before, QGraphicsDropShadowEffect)
    color_before = QColor(effect_before.color())
    apply_theme(app, ThemeMode.DARK)
    effect_after = card.graphicsEffect()
    assert isinstance(effect_after, QGraphicsDropShadowEffect)
    color_after = QColor(effect_after.color())
    # La couleur d'ombre du dark doit différer du light.
    assert (
        color_before.red(),
        color_before.green(),
        color_before.blue(),
        color_before.alpha(),
    ) != (
        color_after.red(),
        color_after.green(),
        color_after.blue(),
        color_after.alpha(),
    )
    # Restauration de l'état global
    apply_theme(app, ThemeMode.LIGHT)
    set_current_palette(LIGHT_TOKENS)
