"""Tests de ``app.language_controller.LanguageController``.

Couvre :

- lecture de la préférence ``language`` au démarrage ;
- persistance lors d'un changement (``set_language`` retourne ``True``) ;
- idempotence si la langue est inchangée (retourne ``False``, pas de touch
  disque) ;
- préservation de l'apparence (``theme_mode``) lors du changement de langue.

Garde-fou : chaque test restaure FR (langue source, sans traducteur) en fin
d'exécution pour ne pas polluer les tests UI qui suivent (un ``QTranslator``
installé pendant qu'un test ultérieur itère ``QApplication.allWidgets()`` peut
déclencher une corruption mémoire Windows — observé dans la pratique).
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from fahmi2.app.language_controller import LanguageController
from fahmi2.app.ui_preferences import (
    UiPreferences,
    read_ui_preferences,
    write_ui_preferences,
)
from fahmi2.i18n import AppLanguage, bundled_translations_dir, install_translator
from fahmi2.ui.theme._tokens import ThemeMode


@pytest.fixture(autouse=True)
def _restore_default_language() -> Iterator[None]:
    """Repli systématique sur FR à la fin de chaque test (cf. docstring module)."""
    yield
    app = QApplication.instance()
    if isinstance(app, QApplication):
        install_translator(app, AppLanguage.FR, bundled_translations_dir())


def test_controller_reads_initial_preference(qtbot: object, tmp_path: Path) -> None:
    """L'initialisation lit la préférence de langue sur disque."""
    del qtbot
    prefs_path = tmp_path / "ui_prefs.json"
    write_ui_preferences(prefs_path, UiPreferences(language=AppLanguage.EN))

    app = QApplication.instance()
    assert isinstance(app, QApplication)
    controller = LanguageController(app, prefs_path)
    assert controller.language is AppLanguage.EN


def test_controller_defaults_to_fr_when_file_missing(
    qtbot: object, tmp_path: Path
) -> None:
    """Sans fichier de préférence, la langue par défaut est FR (source)."""
    del qtbot
    prefs_path = tmp_path / "ui_prefs.json"
    app = QApplication.instance()
    assert isinstance(app, QApplication)
    controller = LanguageController(app, prefs_path)
    assert controller.language is AppLanguage.FR


def test_set_language_persists_to_disk(qtbot: object, tmp_path: Path) -> None:
    """``set_language`` écrit la nouvelle préférence sur disque et retourne True."""
    del qtbot
    prefs_path = tmp_path / "ui_prefs.json"
    app = QApplication.instance()
    assert isinstance(app, QApplication)
    controller = LanguageController(app, prefs_path)
    assert controller.set_language(AppLanguage.EN) is True
    assert read_ui_preferences(prefs_path).language is AppLanguage.EN
    assert controller.language is AppLanguage.EN


def test_set_language_idempotent_skips_when_same(
    qtbot: object, tmp_path: Path
) -> None:
    """``set_language`` retourne ``False`` et ne touche pas au disque si égal."""
    del qtbot
    prefs_path = tmp_path / "ui_prefs.json"
    write_ui_preferences(prefs_path, UiPreferences(language=AppLanguage.EN))
    app = QApplication.instance()
    assert isinstance(app, QApplication)
    controller = LanguageController(app, prefs_path)
    mtime_before = prefs_path.stat().st_mtime_ns
    assert controller.set_language(AppLanguage.EN) is False
    mtime_after = prefs_path.stat().st_mtime_ns
    assert mtime_after == mtime_before


def test_set_language_preserves_theme_mode(qtbot: object, tmp_path: Path) -> None:
    """Changer la langue ne doit pas écraser la préférence d'apparence.

    Régression potentielle : si ``set_language`` reconstruit un
    ``UiPreferences`` sans relire le ``theme_mode`` courant, l'apparence
    repasserait silencieusement en ``SYSTEM`` (le défaut) au prochain
    démarrage. On vérifie explicitement que le mode persiste.
    """
    del qtbot
    prefs_path = tmp_path / "ui_prefs.json"
    write_ui_preferences(
        prefs_path,
        UiPreferences(theme_mode=ThemeMode.DARK, language=AppLanguage.FR),
    )
    app = QApplication.instance()
    assert isinstance(app, QApplication)
    controller = LanguageController(app, prefs_path)
    assert controller.set_language(AppLanguage.EN) is True
    final = read_ui_preferences(prefs_path)
    assert final.theme_mode is ThemeMode.DARK
    assert final.language is AppLanguage.EN
