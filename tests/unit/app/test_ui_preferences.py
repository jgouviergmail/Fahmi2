"""Tests du service ``app.ui_preferences`` (lecture/écriture des préférences UI)."""

from __future__ import annotations

from pathlib import Path

from fahmi2.app.ui_preferences import (
    UiPreferences,
    read_ui_preferences,
    write_ui_preferences,
)
from fahmi2.i18n import AppLanguage
from fahmi2.ui.theme._tokens import ThemeMode


def test_read_returns_defaults_when_file_missing(tmp_path: Path) -> None:
    """Si le fichier n'existe pas, on retourne les défauts (mode SYSTEM + FR)."""
    prefs = read_ui_preferences(tmp_path / "ui_prefs.json")
    assert prefs.theme_mode is ThemeMode.SYSTEM
    assert prefs.language is AppLanguage.FR


def test_read_returns_defaults_when_json_invalid(tmp_path: Path) -> None:
    """Si le fichier est un JSON invalide, on retourne les défauts (lenient)."""
    path = tmp_path / "ui_prefs.json"
    path.write_text("not a json", encoding="utf-8")
    prefs = read_ui_preferences(path)
    assert prefs.theme_mode is ThemeMode.SYSTEM
    assert prefs.language is AppLanguage.FR


def test_read_returns_defaults_when_root_not_dict(tmp_path: Path) -> None:
    """Si le JSON racine n'est pas un dictionnaire, on retourne les défauts."""
    path = tmp_path / "ui_prefs.json"
    path.write_text("[1, 2, 3]", encoding="utf-8")
    prefs = read_ui_preferences(path)
    assert prefs.theme_mode is ThemeMode.SYSTEM
    assert prefs.language is AppLanguage.FR


def test_read_returns_defaults_on_unknown_theme_mode(tmp_path: Path) -> None:
    """Une valeur inconnue de ``theme_mode`` est ignorée (repli SYSTEM)."""
    path = tmp_path / "ui_prefs.json"
    path.write_text('{"theme_mode": "neon"}', encoding="utf-8")
    prefs = read_ui_preferences(path)
    assert prefs.theme_mode is ThemeMode.SYSTEM


def test_read_returns_defaults_when_theme_mode_not_string(tmp_path: Path) -> None:
    """Une valeur de ``theme_mode`` non textuelle tombe sur les défauts."""
    path = tmp_path / "ui_prefs.json"
    path.write_text('{"theme_mode": 42}', encoding="utf-8")
    prefs = read_ui_preferences(path)
    assert prefs.theme_mode is ThemeMode.SYSTEM


def test_read_returns_defaults_on_unknown_language(tmp_path: Path) -> None:
    """Une valeur inconnue de ``language`` est ignorée (repli FR)."""
    path = tmp_path / "ui_prefs.json"
    path.write_text('{"language": "klingon"}', encoding="utf-8")
    prefs = read_ui_preferences(path)
    assert prefs.language is AppLanguage.FR


def test_read_returns_defaults_when_language_not_string(tmp_path: Path) -> None:
    """Une valeur de ``language`` non textuelle tombe sur les défauts."""
    path = tmp_path / "ui_prefs.json"
    path.write_text('{"language": 42}', encoding="utf-8")
    prefs = read_ui_preferences(path)
    assert prefs.language is AppLanguage.FR


def test_read_legacy_file_without_language_field(tmp_path: Path) -> None:
    """Un fichier antérieur à l'ajout de ``language`` reste lu (rétro-compatible).

    Les utilisateurs existants ont un ``ui_prefs.json`` sans clé ``language`` —
    on doit retomber sur ``FR`` (langue source) sans rien casser.
    """
    path = tmp_path / "ui_prefs.json"
    path.write_text('{"theme_mode": "dark"}', encoding="utf-8")
    prefs = read_ui_preferences(path)
    assert prefs.theme_mode is ThemeMode.DARK
    assert prefs.language is AppLanguage.FR


def test_write_and_read_roundtrip_for_each_mode(tmp_path: Path) -> None:
    """Écriture puis lecture rétablit le même mode pour chaque ``ThemeMode``."""
    path = tmp_path / "ui_prefs.json"
    for mode in (ThemeMode.SYSTEM, ThemeMode.LIGHT, ThemeMode.DARK):
        write_ui_preferences(path, UiPreferences(theme_mode=mode))
        assert read_ui_preferences(path).theme_mode is mode


def test_write_and_read_roundtrip_for_each_language(tmp_path: Path) -> None:
    """Écriture puis lecture rétablit la langue pour chaque ``AppLanguage``."""
    path = tmp_path / "ui_prefs.json"
    for lang in AppLanguage:
        write_ui_preferences(path, UiPreferences(language=lang))
        assert read_ui_preferences(path).language is lang


def test_write_preserves_both_fields(tmp_path: Path) -> None:
    """Écrire un mix (sombre + EN) puis lire restitue les deux préférences."""
    path = tmp_path / "ui_prefs.json"
    write_ui_preferences(
        path,
        UiPreferences(theme_mode=ThemeMode.DARK, language=AppLanguage.EN),
    )
    loaded = read_ui_preferences(path)
    assert loaded.theme_mode is ThemeMode.DARK
    assert loaded.language is AppLanguage.EN


def test_write_creates_parent_directory(tmp_path: Path) -> None:
    """Le dossier parent est créé automatiquement si nécessaire."""
    path = tmp_path / "subdir" / "ui_prefs.json"
    assert not path.parent.exists()
    write_ui_preferences(path, UiPreferences(theme_mode=ThemeMode.DARK))
    assert path.exists()
    assert read_ui_preferences(path).theme_mode is ThemeMode.DARK


def test_write_is_atomic_temp_then_replace(tmp_path: Path) -> None:
    """Aucun fichier temporaire ne reste après une écriture réussie.

    Les fichiers temporaires utilisés pour l'écriture atomique commencent par
    ``.ui_prefs.``. Le dossier ne doit en contenir aucun à la fin.
    """
    path = tmp_path / "ui_prefs.json"
    write_ui_preferences(path, UiPreferences(theme_mode=ThemeMode.LIGHT))
    leftovers = [p.name for p in tmp_path.iterdir() if p.name.startswith(".ui_prefs.")]
    assert leftovers == []


def test_ui_preferences_defaults_to_system_mode() -> None:
    """Le dataclass ``UiPreferences`` par défaut est en mode ``SYSTEM`` + FR."""
    assert UiPreferences().theme_mode is ThemeMode.SYSTEM
    assert UiPreferences().language is AppLanguage.FR
