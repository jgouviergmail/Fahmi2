"""Résolution des chemins standards Windows utilisés par l'application.

Suit les conventions Windows :

- ``APPDATA`` (``%APPDATA%/Fahmi2``) pour les données utilisateur synchronisables
  (profils itinérants) : projets, secrets, prompts override, backups.
- ``LOCALAPPDATA`` (``%LOCALAPPDATA%/Fahmi2``) pour les caches volumineux
  (modèles whisper notamment).

Les chemins sont résolus une seule fois via :py:meth:`AppPaths.default` au
démarrage de l'application puis transportés en tant que dépendance immuable.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

_APP_FOLDER = "Fahmi2"
_APPDATA_ENV = "APPDATA"
_LOCALAPPDATA_ENV = "LOCALAPPDATA"
_USERPROFILE_ENV = "USERPROFILE"
_APPDATA_FALLBACK_RELATIVE = "AppData/Roaming"
_LOCALAPPDATA_FALLBACK_RELATIVE = "AppData/Local"
_SECRETS_FILENAME = "secrets.dat"
_PROJECTS_DIRNAME = "projects"
_PROMPTS_DIRNAME = "prompts"
_MODELS_DIRNAME = "models"
_BACKUPS_DIRNAME = "backups"


def _resolve_env_dir(env_var: str, fallback_relative: str) -> Path:
    """Résout une variable d'environnement Windows, avec fallback sur ``USERPROFILE``.

    Args:
        env_var: Nom de la variable d'environnement primaire (ex: ``APPDATA``).
        fallback_relative: Chemin relatif à ``USERPROFILE`` si la variable
            primaire est absente.

    Returns:
        Le ``Path`` résolu.
    """
    value = os.environ.get(env_var)
    if value:
        return Path(value)
    profile = os.environ.get(_USERPROFILE_ENV)
    if profile:
        return Path(profile) / fallback_relative
    return Path.home() / fallback_relative


@dataclass(frozen=True)
class AppPaths:
    """Conteneur immutable des chemins applicatifs résolus.

    Attributes:
        appdata: Racine ``%APPDATA%/Fahmi2`` (données utilisateur).
        localappdata: Racine ``%LOCALAPPDATA%/Fahmi2`` (caches).
    """

    appdata: Path
    localappdata: Path

    @classmethod
    def default(cls) -> AppPaths:
        """Résolution standard pour Windows (avec fallbacks).

        Returns:
            Une instance d'``AppPaths`` avec les chemins par défaut.
        """
        return cls(
            appdata=_resolve_env_dir(_APPDATA_ENV, _APPDATA_FALLBACK_RELATIVE) / _APP_FOLDER,
            localappdata=(
                _resolve_env_dir(_LOCALAPPDATA_ENV, _LOCALAPPDATA_FALLBACK_RELATIVE)
                / _APP_FOLDER
            ),
        )

    @property
    def secrets_file(self) -> Path:
        """Chemin du fichier de secrets chiffrés DPAPI."""
        return self.appdata / _SECRETS_FILENAME

    @property
    def projects_dir(self) -> Path:
        """Dossier racine des projets utilisateur."""
        return self.appdata / _PROJECTS_DIRNAME

    @property
    def prompts_override_dir(self) -> Path:
        """Dossier de surcouche des templates de prompts."""
        return self.appdata / _PROMPTS_DIRNAME

    @property
    def models_dir(self) -> Path:
        """Dossier de cache des modèles téléchargés (whisper, etc.)."""
        return self.localappdata / _MODELS_DIRNAME

    @property
    def backups_dir(self) -> Path:
        """Dossier des sauvegardes automatiques (pré-migration)."""
        return self.appdata / _BACKUPS_DIRNAME

    def ensure_dirs(self) -> None:
        """Crée tous les répertoires standards s'ils n'existent pas (idempotent)."""
        for path in (
            self.appdata,
            self.localappdata,
            self.projects_dir,
            self.prompts_override_dir,
            self.models_dir,
            self.backups_dir,
        ):
            path.mkdir(parents=True, exist_ok=True)


def resolve_bundled_ffmpeg_dir() -> Path | None:
    """Retourne le dossier contenant les binaires ffmpeg bundlés, si présent.

    Lorsque l'application est packagée par PyInstaller, ``sys._MEIPASS`` pointe
    sur le dossier d'exécution et ``sys.frozen`` est vrai. Dans ce cas les
    binaires ``ffmpeg.exe`` et ``ffprobe.exe`` se trouvent à la racine du
    bundle. En mode développement (lancement depuis source), on retourne
    ``None`` pour laisser le binaire système du PATH s'appliquer.

    Returns:
        Le dossier des binaires si bundlés, sinon ``None``.
    """
    import sys  # noqa: PLC0415 — local pour découplage de l'API publique

    if not getattr(sys, "frozen", False):
        return None
    bundle_root_str = getattr(sys, "_MEIPASS", None) or str(Path(sys.executable).parent)
    bundle_root = Path(bundle_root_str)
    ffmpeg = bundle_root / "ffmpeg.exe"
    if ffmpeg.exists():
        return bundle_root
    return None


def resolve_ffmpeg_binary_or_none() -> str | None:
    """Retourne le chemin absolu de ``ffmpeg.exe`` bundlé, ou ``None``.

    Returns:
        Chemin absolu si binaire bundlé détecté, ``None`` sinon (le PATH
        système est alors utilisé).
    """
    bundle_dir = resolve_bundled_ffmpeg_dir()
    if bundle_dir is None:
        return None
    return str(bundle_dir / "ffmpeg.exe")


def resolve_ffprobe_binary_or_none() -> str | None:
    """Retourne le chemin absolu de ``ffprobe.exe`` bundlé, ou ``None``.

    Returns:
        Chemin absolu si binaire bundlé détecté, ``None`` sinon.
    """
    bundle_dir = resolve_bundled_ffmpeg_dir()
    if bundle_dir is None:
        return None
    return str(bundle_dir / "ffprobe.exe")
