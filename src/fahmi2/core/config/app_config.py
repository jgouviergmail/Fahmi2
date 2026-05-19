"""Configuration globale immutable de l'application."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from fahmi2.core.config.paths import AppPaths

LogLevelName = Literal["DEBUG", "INFO", "WARNING", "ERROR"]
ThemeName = Literal["system", "light", "dark"]


@dataclass(frozen=True)
class AppConfig:
    """Configuration globale (préférences UI + chemins).

    Représente l'état persistant *côté machine de l'utilisateur* pour les
    préférences générales — pas les paramètres d'un projet, qui vivent dans
    ``ProjectSettings``.

    Attributes:
        paths: Chemins applicatifs résolus.
        ui_log_level_default: Niveau de log affiché par défaut dans l'UI.
        theme: Thème de rendu de l'application.
        last_project_id: ULID du dernier Projet ouvert (réouverture rapide).
    """

    paths: AppPaths
    ui_log_level_default: LogLevelName = "INFO"
    theme: ThemeName = "system"
    last_project_id: str | None = None
