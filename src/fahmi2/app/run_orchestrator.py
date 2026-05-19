"""``RunOrchestrator`` — service applicatif pilotant le lifecycle d'un Run.

Cette couche distingue la responsabilité métier (créer un Run, snapshotter
les settings, persister, communiquer avec l'UI via ``EventBus``) du moteur
d'exécution pur (:py:class:`~fahmi2.pipeline.engine.PipelineEngine`).

Le ``RunOrchestrator`` expose des opérations *synchrones* :

- ``create_run`` : génère un Run avec sa liste de vidéos scannées, persiste
  l'ensemble (Project + Run + VideoExecutions).
- ``execute`` : appelle le moteur (``PipelineEngine.execute``) et met à jour
  l'état final du Run en SQLite.
- ``request_pause``/``request_cancel``/``resume`` : délègue au ``PauseToken``
  injecté.

Le déport asynchrone vers un ``QThread`` (UI) sera fait par la couche UI
(Plan 08) qui appellera ``execute`` depuis un worker.
"""

from __future__ import annotations

from datetime import UTC, datetime

from fahmi2.app.project_service import ProjectService
from fahmi2.app.video_scanner import scan_input_folder
from fahmi2.domain.enums import RunStatus
from fahmi2.domain.ids import ProjectId, RunId
from fahmi2.domain.project import Project
from fahmi2.domain.run import Run
from fahmi2.domain.state_machine import validate_transition_run
from fahmi2.infra.storage.sqlite_state import SqliteState
from fahmi2.pipeline.engine import PipelineEngine
from fahmi2.pipeline.pause_token import PauseToken
from fahmi2.pipeline.phase_handler import PhaseContext

# Statuts pour lesquels le dernier Run d'un projet est considéré comme
# « inachevé » et donc reprenable au prochain clic ``Lancer``. Les Runs
# terminés (COMPLETED) ou explicitement annulés (CANCELLED) ne sont
# jamais repris : un nouveau Run vierge est créé à la place.
_RESUMABLE_RUN_STATUSES: frozenset[RunStatus] = frozenset(
    {RunStatus.FAILED, RunStatus.PAUSED, RunStatus.RUNNING}
)


class RunOrchestrator:
    """Pilote le lifecycle d'un Run et coordonne avec le ``PipelineEngine``."""

    def __init__(
        self,
        *,
        state: SqliteState,
        engine: PipelineEngine,
        project_service: ProjectService,
    ) -> None:
        """Construit l'orchestrateur.

        Args:
            state: Stockage SQLite.
            engine: Moteur d'exécution du pipeline.
            project_service: Service projets (relectures + mises à jour).
        """
        self._state = state
        self._engine = engine
        self._project_service = project_service

    def create_run(self, project: Project) -> Run:
        """Crée un nouveau ``Run`` pour un projet et persiste l'ensemble.

        Args:
            project: Projet propriétaire.

        Returns:
            Le ``Run`` créé (à l'état ``CREATED``).

        Raises:
            StorageError: Si le dossier d'entrée est inaccessible.
            ConfigError: Si aucun fichier vidéo supporté n'est trouvé.
        """
        videos = scan_input_folder(project.settings.input_folder)
        run = Run(
            id=RunId.new(),
            project_id=project.id,
            started_at=datetime.now(tz=UTC),
            status=RunStatus.CREATED,
            settings_snapshot=project.settings,
            videos=tuple(videos),
        )
        self._state.upsert_run(run)
        return run

    def resume_or_create_run(self, project: Project) -> tuple[Run, bool]:
        """Crée un nouveau Run, ou reprend le dernier Run inachevé du projet.

        Politique : on **reprend** le dernier Run s'il est dans un état
        considéré comme reprenable :

        - ``FAILED`` : une phase a échoué, l'utilisateur veut reprendre où
          ça s'est arrêté. Les phases ``SUCCEEDED`` seront skippées par
          le ``PipelineEngine``, la phase ``FAILED`` sera réessayée.
        - ``PAUSED`` : crash applicatif pendant une pause utilisateur, ou
          fermeture volontaire de l'app avec un run en pause. Idem :
          reprise transparente.
        - ``RUNNING`` : crash app pendant un Run actif (statut resté
          coincé en RUNNING dans la DB). On considère que c'est
          reprenable.

        Sinon (``CANCELLED`` / ``COMPLETED`` / pas de Run du tout) on
        crée un nouveau Run vierge avec un nouveau ``RunId`` et un
        re-scan du dossier d'entrée.

        Args:
            project: Projet propriétaire.

        Returns:
            ``(run, is_resumed)`` où ``is_resumed`` vaut ``True`` si on
            a repris un Run existant.

        Raises:
            StorageError: Si le scan d'un nouveau Run échoue.
            ConfigError: Si le dossier d'entrée est vide pour un nouveau Run.
        """
        existing_runs = self._state.list_runs_for_project(project.id)
        if existing_runs:
            latest = existing_runs[-1]
            if latest.status in _RESUMABLE_RUN_STATUSES:
                return latest, True
        return self.create_run(project), False

    def execute(self, *, run: Run, ctx: PhaseContext) -> RunStatus:
        """Exécute le pipeline pour un Run et persiste le statut final.

        Args:
            run: Run à exécuter (doit être ``CREATED`` ou ``PAUSED``).
            ctx: Contexte d'exécution complet (déjà construit par l'UI).

        Returns:
            Le ``RunStatus`` final.
        """
        validate_transition_run(run.status, RunStatus.RUNNING)
        running_run = run.with_status(RunStatus.RUNNING)
        self._state.upsert_run(running_run)

        final_status = self._engine.execute(ctx)

        finished_run = running_run.with_status(final_status).with_finished_at(
            datetime.now(tz=UTC)
        )
        self._state.upsert_run(finished_run)

        project = self._project_service.get_project(running_run.project_id)
        if project is not None:
            self._project_service.update_project(
                Project(
                    id=project.id,
                    settings=project.settings,
                    created_at=project.created_at,
                    last_run_at=finished_run.finished_at,
                    runs=(*project.runs, finished_run.id),
                )
            )
        return final_status

    @staticmethod
    def request_pause(pause_token: PauseToken) -> None:
        """Demande une pause via le ``PauseToken``.

        Args:
            pause_token: Token actif du run en cours.
        """
        pause_token.request_pause()

    @staticmethod
    def resume(pause_token: PauseToken) -> None:
        """Lève la pause via le ``PauseToken``.

        Args:
            pause_token: Token actif.
        """
        pause_token.resume()

    @staticmethod
    def request_cancel(pause_token: PauseToken) -> None:
        """Demande l'annulation via le ``PauseToken``.

        Args:
            pause_token: Token actif.
        """
        pause_token.request_cancel()

    def get_run(self, run_id: RunId) -> Run | None:
        """Récupère un Run par identifiant (depuis SQLite).

        Args:
            run_id: Identifiant.

        Returns:
            Le ``Run`` ou ``None``.
        """
        return self._state.get_run(run_id)

    def list_runs(self, project_id: ProjectId) -> list[Run]:
        """Liste les runs d'un projet.

        Args:
            project_id: Identifiant.

        Returns:
            Runs ordonnés.
        """
        return self._state.list_runs_for_project(project_id)
