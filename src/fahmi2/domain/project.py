"""Entité ``Project`` — identité minimale (nom + emplacement) + réglages par fonctionnalité.

Un ``Project`` ne porte que son **nom** et son **emplacement** (``workspace_folder``,
fixé à la création et immuable). Les paramètres métier vivent dans des blocs de
réglages dédiés **par fonctionnalité** — ``generation`` (cf. ``domain.generation``),
``pedagogy`` (cf. ``domain.pedagogy``) et ``chat`` (cf. ``domain.chat``) — chacun
valant ``None`` tant que sa fonctionnalité n'est pas configurée.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime
from pathlib import Path

from fahmi2.domain.chat import ChatSettings
from fahmi2.domain.generation import GenerationSettings
from fahmi2.domain.ids import ProjectId, RunId
from fahmi2.domain.pedagogy import PedagogySettings
from fahmi2.domain.visuals import VisualsSettings


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
        pedagogy: Réglages de la fonctionnalité Supports pédagogiques, ou ``None``
            tant qu'elle n'est pas configurée.
        chat: Réglages de la fonctionnalité Dialogue (chat), ou ``None`` tant
            qu'elle n'est pas configurée.
        visuals: Réglages de la fonctionnalité Visualisations, ou ``None`` tant
            qu'elle n'est pas configurée.
    """

    id: ProjectId
    name: str
    workspace_folder: Path
    created_at: datetime
    last_run_at: datetime | None = None
    runs: tuple[RunId, ...] = ()
    generation: GenerationSettings | None = None
    pedagogy: PedagogySettings | None = None
    chat: ChatSettings | None = None
    visuals: VisualsSettings | None = None

    def with_visuals(self, visuals: VisualsSettings | None) -> Project:
        """Retourne une copie avec de nouveaux réglages Visualisations.

        Args:
            visuals: Réglages Visualisations, ou ``None``.

        Returns:
            Nouvelle instance immuable (autres réglages préservés).
        """
        return replace(self, visuals=visuals)

    def with_name(self, name: str) -> Project:
        """Retourne une copie avec un nouveau ``name``.

        Args:
            name: Nouveau nom du projet.

        Returns:
            Nouvelle instance immuable (autres champs préservés).
        """
        return replace(self, name=name)

    def with_generation(self, generation: GenerationSettings | None) -> Project:
        """Retourne une copie avec de nouveaux réglages de génération.

        Args:
            generation: Réglages de génération, ou ``None``.

        Returns:
            Nouvelle instance immuable (notamment ``pedagogy`` préservé).
        """
        return replace(self, generation=generation)

    def with_pedagogy(self, pedagogy: PedagogySettings | None) -> Project:
        """Retourne une copie avec de nouveaux réglages Supports pédagogiques.

        Args:
            pedagogy: Réglages pédagogie, ou ``None``.

        Returns:
            Nouvelle instance immuable (notamment ``generation`` préservé).
        """
        return replace(self, pedagogy=pedagogy)

    def with_chat(self, chat: ChatSettings | None) -> Project:
        """Retourne une copie avec de nouveaux réglages Dialogue (chat).

        Args:
            chat: Réglages chat, ou ``None``.

        Returns:
            Nouvelle instance immuable (autres réglages préservés).
        """
        return replace(self, chat=chat)
