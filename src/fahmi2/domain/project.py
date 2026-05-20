"""Entité ``Project`` — identité minimale (nom + emplacement) + réglages par fonctionnalité.

Un ``Project`` ne porte que son **nom** et son **emplacement** (``workspace_folder``,
fixé à la création et immuable). Les paramètres métier vivent dans des blocs de
réglages dédiés par fonctionnalité — ici ``generation`` (cf. ``domain.generation``).
``generation`` vaut ``None`` tant que la fonctionnalité n'est pas configurée.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from fahmi2.domain.generation import GenerationSettings
from fahmi2.domain.ids import ProjectId, RunId


@dataclass(frozen=True)
class Project:
    """Projet utilisateur persistant avec son historique de runs.

    Attributes:
        id: Identifiant stable du projet.
        name: Nom utilisateur du projet.
        workspace_folder: Emplacement de travail (artefacts/sortie), immuable
            après création.
        created_at: Date de création.
        last_run_at: Date du dernier run terminé (``None`` si jamais lancé).
        runs: Historique des ULID de Run associés au projet.
        generation: Réglages de la fonctionnalité Génération, ou ``None`` tant
            qu'elle n'est pas configurée.
    """

    id: ProjectId
    name: str
    workspace_folder: Path
    created_at: datetime
    last_run_at: datetime | None = None
    runs: tuple[RunId, ...] = ()
    generation: GenerationSettings | None = None
