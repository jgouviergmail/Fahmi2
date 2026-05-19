"""Service applicatif ``ProjectService`` — CRUD projets.

Couche fine au-dessus de :py:class:`SqliteState`. Centralise la création d'un
projet (génération d'ID, horodatage), la persistance et la suppression.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fahmi2.domain.ids import ProjectId, RunId
from fahmi2.domain.project import Project, ProjectSettings
from fahmi2.domain.run import Run
from fahmi2.infra.storage.sqlite_state import SqliteState


class ProjectService:
    """Service CRUD pour les ``Project``."""

    def __init__(self, state: SqliteState) -> None:
        """Construit le service.

        Args:
            state: Accès SQLite.
        """
        self._state = state

    def create_project(self, settings: ProjectSettings) -> Project:
        """Crée et persiste un nouveau ``Project``.

        Args:
            settings: Paramètres du projet.

        Returns:
            Le ``Project`` créé.
        """
        project = Project(
            id=ProjectId.new(),
            settings=settings,
            created_at=datetime.now(tz=UTC),
        )
        self._state.upsert_project(project)
        return project

    def update_project(self, project: Project) -> None:
        """Persiste les modifications d'un projet existant.

        Args:
            project: Projet à mettre à jour.
        """
        self._state.upsert_project(project)

    def get_project(self, project_id: ProjectId) -> Project | None:
        """Récupère un projet par ``project_id``.

        Args:
            project_id: Identifiant.

        Returns:
            Le ``Project``, ou ``None`` si introuvable.
        """
        return self._state.get_project(project_id)

    def list_projects(self) -> list[Project]:
        """Liste tous les projets connus.

        Returns:
            Liste ordonnée par date de création.
        """
        return self._state.list_projects()

    def delete_project(self, project_id: ProjectId) -> None:
        """Supprime un projet (avec cascade sur ses runs).

        Args:
            project_id: Identifiant.
        """
        self._state.delete_project(project_id)

    def list_runs(self, project_id: ProjectId) -> list[Run]:
        """Liste les runs d'un projet.

        Args:
            project_id: Identifiant.

        Returns:
            Runs ordonnés par date de démarrage.
        """
        return self._state.list_runs_for_project(project_id)

    def get_last_run(self, project_id: ProjectId) -> Run | None:
        """Retourne le run le plus récent du projet (ou ``None``).

        Args:
            project_id: Identifiant.

        Returns:
            Le dernier ``Run``, ou ``None`` si aucun.
        """
        runs = self.list_runs(project_id)
        return runs[-1] if runs else None

    def get_run(self, run_id: RunId) -> Run | None:
        """Récupère un run par identifiant.

        Args:
            run_id: Identifiant.

        Returns:
            Le ``Run`` ou ``None``.
        """
        return self._state.get_run(run_id)
