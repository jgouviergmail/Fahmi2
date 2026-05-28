"""Service de persistance des préférences UI (apparence claire/sombre/système).

Persistance d'une simple dataclass ``UiPreferences`` dans un fichier JSON
(``%APPDATA%/Fahmi2/ui_prefs.json``). Lecture **lenient** : un fichier absent
ou corrompu repose sur les valeurs par défaut sans lever d'erreur (le
démarrage de l'application doit toujours réussir, même sur préférences
illisibles). Écriture **atomique** via fichier temporaire + remplacement
(``Path.replace`` est atomique sur Windows comme sur POSIX).

Indépendant du domaine et du pipeline : c'est une préférence purement UI.
"""

from __future__ import annotations

import json
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Final

from fahmi2.ui.theme._tokens import ThemeMode

#: Clé JSON du mode d'apparence dans ``ui_prefs.json``.
_THEME_MODE_KEY: Final[str] = "theme_mode"
#: Mode par défaut si le fichier est absent ou corrompu (lenient).
_DEFAULT_THEME_MODE: Final[ThemeMode] = ThemeMode.SYSTEM
#: Encodage du fichier JSON.
_FILE_ENCODING: Final[str] = "utf-8"
#: Préfixe du fichier temporaire utilisé pour l'écriture atomique.
_TEMP_FILE_PREFIX: Final[str] = ".ui_prefs."
#: Suffixe du fichier temporaire (utile au debug).
_TEMP_FILE_SUFFIX: Final[str] = ".tmp"


@dataclass(frozen=True)
class UiPreferences:
    """Préférences UI persistées (apparence + éventuelles extensions futures).

    Attributes:
        theme_mode: Mode d'apparence choisi par l'utilisateur. ``SYSTEM`` (défaut)
            suit le mode du système d'exploitation.
    """

    theme_mode: ThemeMode = _DEFAULT_THEME_MODE


def read_ui_preferences(path: Path) -> UiPreferences:
    """Charge les préférences UI depuis ``path`` (parsing *lenient*).

    Fichier absent, corrompu (JSON invalide), ou contenant une valeur inconnue
    pour ``theme_mode`` → retourne les défauts sans lever d'erreur. C'est un
    choix délibéré : une préférence UI ne doit jamais empêcher l'application
    de démarrer.

    Args:
        path: Chemin du fichier ``ui_prefs.json``.

    Returns:
        Les ``UiPreferences`` lues, ou les défauts si non récupérables.
    """
    if not path.exists():
        return UiPreferences()
    try:
        raw = path.read_text(encoding=_FILE_ENCODING)
        data = json.loads(raw)
    except (OSError, json.JSONDecodeError):
        return UiPreferences()
    if not isinstance(data, dict):
        return UiPreferences()
    return UiPreferences(theme_mode=_parse_theme_mode(data.get(_THEME_MODE_KEY)))


def write_ui_preferences(path: Path, prefs: UiPreferences) -> None:
    """Écrit ``prefs`` dans ``path`` de façon atomique (temp file + remplacement).

    Crée le dossier parent s'il n'existe pas. L'écriture passe par un fichier
    temporaire dans le **même répertoire** que la cible (gage d'atomicité sur
    Windows comme sur POSIX) puis appelle ``Path.replace`` pour le rendre
    visible en une seule opération.

    Args:
        path: Chemin cible du fichier JSON.
        prefs: Préférences à persister.

    Raises:
        OSError: Si l'écriture sur disque échoue (l'appelant peut choisir
            d'ignorer cette erreur — la préférence UI n'est pas critique).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {_THEME_MODE_KEY: prefs.theme_mode.value}
    serialized = json.dumps(payload, ensure_ascii=False, indent=2)
    fd, tmp_path_str = tempfile.mkstemp(
        prefix=_TEMP_FILE_PREFIX, suffix=_TEMP_FILE_SUFFIX, dir=str(path.parent)
    )
    tmp_path = Path(tmp_path_str)
    try:
        with os.fdopen(fd, "w", encoding=_FILE_ENCODING) as f:
            f.write(serialized)
        tmp_path.replace(path)
    except OSError:
        # Nettoyage best-effort du temporaire en cas d'échec.
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        raise


def _parse_theme_mode(value: object) -> ThemeMode:
    """Convertit une valeur JSON arbitraire en ``ThemeMode`` (avec repli).

    Args:
        value: Valeur lue (typiquement une chaîne, mais peut être tout type).

    Returns:
        Le ``ThemeMode`` correspondant, ou ``_DEFAULT_THEME_MODE`` si la
        valeur est absente / non reconnue.
    """
    if not isinstance(value, str):
        return _DEFAULT_THEME_MODE
    try:
        return ThemeMode(value)
    except ValueError:
        return _DEFAULT_THEME_MODE


__all__ = ["UiPreferences", "read_ui_preferences", "write_ui_preferences"]
