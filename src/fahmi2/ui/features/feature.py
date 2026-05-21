"""Contrats de l'abstraction « fonctionnalité » : ``FeatureId`` et ``FeatureTab``.

Chaque fonctionnalité de l'application (Génération, Supports pédagogiques, …) est
exposée comme un onglet implémentant ``FeatureTab``. Ajouter une fonctionnalité
revient à créer un ``FeatureTab`` et à l'enregistrer dans le ``FeatureRegistry`` —
sans modifier ``MainWindow`` ni l'entité ``Project``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from enum import StrEnum

from PySide6.QtWidgets import QWidget

from fahmi2.domain.ids import ProjectId


class FeatureId(StrEnum):
    """Identifiants stables des fonctionnalités exposées en onglets."""

    GENERATION = "generation"
    PEDAGOGY = "pedagogy"


class FeatureTab(ABC):
    """Contrat d'un onglet de fonctionnalité.

    Une implémentation construit son propre widget et, le cas échéant, son
    contrôleur. ``on_project_selected`` est appelée par ``MainWindow`` à chaque
    changement de projet dans la sidebar ; l'implémentation par défaut est un
    no-op (les onglets qui n'en ont pas besoin n'ont rien à écrire).
    """

    @property
    @abstractmethod
    def feature_id(self) -> FeatureId:
        """Identifiant de la fonctionnalité."""

    @property
    @abstractmethod
    def title(self) -> str:
        """Libellé de l'onglet."""

    @property
    @abstractmethod
    def widget(self) -> QWidget:
        """Widget racine affiché dans l'onglet."""

    def on_project_selected(self, project_id: ProjectId | None) -> None:  # noqa: B027
        """Réagit à la sélection d'un projet dans la sidebar.

        Crochet optionnel : implémentation par défaut volontairement vide (no-op),
        pour que les onglets sans logique de sélection n'aient rien à écrire.

        Args:
            project_id: Projet sélectionné, ou ``None`` si désélection.
        """

    def on_project_deleted(self, project_id: ProjectId) -> None:  # noqa: B027
        """Réagit à la suppression d'un projet.

        Crochet optionnel (no-op par défaut) : un onglet qui affiche ce projet
        doit réinitialiser son état pour ne pas conserver une référence obsolète
        (cf. ``MainWindow.notify_project_deleted``).

        Args:
            project_id: Projet supprimé.
        """
