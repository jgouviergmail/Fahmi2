"""``VisualsController` — orchestration de l'onglet Visualisations.

Parallèle au ``PedagogyController`` (orchestrateur léger, pas de ``PipelineEngine``) :

- Maintient le projet sélectionné et rafraîchit le bandeau d'état (fraîcheur).
- Ouvre le dialogue de réglages et persiste ``Project.visuals``.
- Estime le coût (``VisualsCostEstimator``).
- Déporte la génération dans un ``QThread`` worker (``VisualsOrchestrator``), bridge les
  ``VisualsEvent`` vers la vue de progression + le dock de logs.
- Gère pause / reprise / annulation via le ``PauseToken``.

Les livrables sont des pages HTML autonomes (``visuals/output/*.html``) ; « Dossier de
sortie » ouvre le dossier ``visuals`` (les pages s'ouvrent par double-clic).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QObject, QThread, Signal
from PySide6.QtWidgets import QDialog, QMessageBox, QWidget

from fahmi2.app.project_service import ProjectService
from fahmi2.app.secrets_service import SecretsService
from fahmi2.app.visuals_cost_estimator import (
    VisualsCostEstimation,
    VisualsCostEstimator,
)
from fahmi2.app.visuals_orchestrator import VisualsOrchestrator
from fahmi2.core.concurrency.pause_token import PauseToken
from fahmi2.core.config.paths import AppPaths
from fahmi2.core.errors.severity import Severity
from fahmi2.core.logging.event import LogEvent
from fahmi2.core.retry.policy import RetryPolicy
from fahmi2.domain.enums import Language, PhaseStatus, RunStatus
from fahmi2.domain.generation import (
    GENERATION_OUTPUT_SUBDIR,
    GENERATION_WORKSPACE_SUBDIR,
)
from fahmi2.domain.ids import ProjectId
from fahmi2.domain.project import Project
from fahmi2.domain.visuals import (
    VISUALS_OUTPUT_SUBDIR,
    VISUALS_WORKSPACE_SUBDIR,
    VisualsSettings,
)
from fahmi2.infra.embeddings.openai_adapter import OpenAIEmbeddingProvider
from fahmi2.infra.llm.deepseek_adapter import DeepSeekAdapter
from fahmi2.infra.prompts.loader import PromptLoader
from fahmi2.infra.storage.feature_run_state import read_run_state
from fahmi2.infra.storage.fs_artifacts import FsArtifactStore
from fahmi2.infra.storage.sqlite_state import SqliteState
from fahmi2.ui._file_explorer import open_in_file_explorer
from fahmi2.ui._fs import remove_feature_dir
from fahmi2.ui.dialogs.visuals_settings_view import VisualsSettingsView
from fahmi2.ui.qt_event_bus import VisualsQtEventBus
from fahmi2.ui.viewmodels.visuals_progress import VisualsProgressViewModel
from fahmi2.ui.viewmodels.visuals_state import VisualsStateViewModel
from fahmi2.ui.visuals_labels import VisualsDeliverable
from fahmi2.ui.widgets.logs_dock import LogsDock
from fahmi2.ui.widgets.project_header_bar import ProjectHeaderBar
from fahmi2.ui.widgets.visuals_progress_view import VisualsProgressView
from fahmi2.visuals.events import (
    VisualsEvent,
    VisualsGenerationFinished,
    VisualsGenerationStarted,
    VisualsLanguageFinished,
    VisualsLanguageStarted,
    VisualsRetryAttempt,
)
from fahmi2.visuals.sources import (
    available_visuals_languages,
    load_text_units,
    outputs_present,
    structure_language,
)

#: Plafond de coût atteint : note ajoutée au log de fin (statut ``PAUSED``).
_MSG_CEILING_REACHED = (
    "Plafond de coût atteint — génération interrompue (langues restantes non "
    "produites)."
)


def _enabled_deliverables(visuals: VisualsSettings) -> tuple[VisualsDeliverable, ...]:
    """Livrables activés, dans l'ordre d'affichage (carte puis diagrammes).

    Args:
        visuals: Réglages Visualisations.

    Returns:
        Le tuple des livrables activés.
    """
    deliverables: list[VisualsDeliverable] = []
    if visuals.produce_knowledge_map:
        deliverables.append(VisualsDeliverable.KNOWLEDGE_MAP)
    if visuals.produce_diagrams:
        deliverables.append(VisualsDeliverable.DIAGRAMS)
    return tuple(deliverables)


class _VisualsWorker(QObject):
    """Worker QObject exécutant ``orchestrator.generate`` dans un thread."""

    finished = Signal(object)  # RunStatus
    failed = Signal(str)

    def __init__(
        self,
        *,
        orchestrator: VisualsOrchestrator,
        project: Project,
        pause_token: PauseToken,
        event_bus: VisualsQtEventBus,
    ) -> None:
        """Construit le worker.

        Args:
            orchestrator: Orchestrateur des visualisations.
            project: Projet à traiter.
            pause_token: Jeton de pause/annulation.
            event_bus: Bus d'événements Visualisations (Qt).
        """
        super().__init__()
        self._orchestrator = orchestrator
        self._project = project
        self._pause_token = pause_token
        self._event_bus = event_bus

    def run_generation(self) -> None:
        """Exécute la génération et émet le signal final.

        Toute exception est convertie en signal ``failed`` plutôt que de laisser le
        thread crasher silencieusement.
        """
        try:
            status = self._orchestrator.generate(
                self._project,
                pause_token=self._pause_token,
                event_bus=self._event_bus,
            )
            self.finished.emit(status)
        except Exception as exc:  # noqa: BLE001 — isolation worker thread
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class VisualsController(QObject):
    """Orchestre la génération des visualisations depuis l'onglet Visualisations."""

    #: Émis quand le statut de la génération change (démarrage / fin / échec /
    #: réinitialisation), pour rafraîchir les icônes de la sidebar.
    run_state_changed = Signal()

    def __init__(
        self,
        *,
        header_bar: ProjectHeaderBar,
        progress_view: VisualsProgressView,
        logs_dock: LogsDock,
        window: QWidget,
        project_service: ProjectService,
        secrets_service: SecretsService,
        state: SqliteState,
        app_paths: AppPaths,
    ) -> None:
        """Construit le contrôleur et branche les signaux du cockpit.

        Args:
            header_bar: Barre d'actions.
            progress_view: Vue bandeau + matrice de progression.
            logs_dock: Dock de logs partagé.
            window: Fenêtre parente (parent des dialogues).
            project_service: Service projets.
            secrets_service: Service secrets (clés DeepSeek / OpenAI).
            state: Stockage SQLite.
            app_paths: Chemins applicatifs (override des prompts).
        """
        super().__init__(window)
        self._header_bar = header_bar
        self._progress_view = progress_view
        self._logs_dock = logs_dock
        self._window = window
        self._project_service = project_service
        self._secrets_service = secrets_service
        self._state = state
        self._app_paths = app_paths

        self._current_project: Project | None = None
        self._active_worker_project_id: ProjectId | None = None
        self._current_pause_token: PauseToken | None = None
        self._worker: _VisualsWorker | None = None
        self._thread: QThread | None = None
        self._progress_vm = VisualsProgressViewModel()
        self._state_vm = VisualsStateViewModel(project_service=project_service)

        self._header_bar.settings_requested.connect(self.open_visuals_settings)
        self._header_bar.estimate_cost_requested.connect(self.estimate_cost)
        self._header_bar.start_requested.connect(self.generate)
        self._header_bar.pause_requested.connect(self.pause)
        self._header_bar.resume_requested.connect(self.resume)
        self._header_bar.cancel_requested.connect(self.cancel)
        self._header_bar.open_output_requested.connect(self.open_folder)
        self._header_bar.reset_requested.connect(self.reset_visuals)

    # ------------------------------------------------------------------ project

    def on_project_selected(self, project_id: ProjectId) -> None:
        """Met à jour l'état UI à la sélection d'un projet.

        Args:
            project_id: Projet sélectionné.
        """
        project = self._project_service.get_project(project_id)
        if project is None:
            return
        self._current_project = project
        self._sync_header_for_selected_project()
        self._header_bar.set_open_output_enabled(self._visuals_dir(project).exists())
        self._refresh_state()
        self._show_progress_for_selected_project(project)

    def _show_progress_for_selected_project(self, project: Project) -> None:
        """Affiche l'état des visualisations du projet sélectionné.

        Si un worker est actif sur ce projet, affiche sa progression live ; sinon, si
        les visualisations sont configurées, reconstruit l'**état de la dernière
        exécution** depuis le disque (langues déjà produites en « terminé » + coût et
        statut du ``run_state``) ; sinon une grille vide.

        Args:
            project: Projet sélectionné.
        """
        if self._worker_on_current_project():
            vm = self._progress_vm
        else:
            vm = VisualsProgressViewModel()
            if project.visuals is not None:
                self._load_persisted_progress(vm, project, project.visuals)
        self._progress_view.apply_snapshot(
            vm.cost_matrix_snapshot(), vm.stats_snapshot()
        )

    def _load_persisted_progress(
        self,
        vm: VisualsProgressViewModel,
        project: Project,
        visuals: VisualsSettings,
    ) -> None:
        """Reconstruit la progression depuis le disque (langues produites + état).

        Args:
            vm: ViewModel de progression à remplir.
            project: Projet sélectionné.
            visuals: Réglages Visualisations.
        """
        output_dir = self._generation_output_dir(project)
        visuals_dir = self._visuals_dir(project)
        out_dir = visuals_dir / VISUALS_OUTPUT_SUBDIR
        languages = available_visuals_languages(output_dir)
        generated = [
            language
            for language in languages
            if outputs_present(out_dir, language, visuals)
        ]
        run_state = read_run_state(visuals_dir)
        vm.load_persisted(
            deliverables=_enabled_deliverables(visuals),
            languages=tuple(languages),
            generated_languages=generated,
            total_cost_usd=run_state.total_cost_usd if run_state else 0.0,
            cost_ceiling_usd=visuals.cost_ceiling_usd,
            overall_status=run_state.status if run_state else None,
            started_at=run_state.started_at if run_state else None,
            finished_at=run_state.finished_at if run_state else None,
        )

    @property
    def current_project_id(self) -> ProjectId | None:
        """Identifiant du projet affiché, ou ``None``.

        Returns:
            ``ProjectId`` ou ``None``.
        """
        return self._current_project.id if self._current_project is not None else None

    def clear_current_project(self) -> None:
        """Désélectionne le projet courant et réinitialise le cockpit.

        À appeler quand le projet affiché vient d'être supprimé : évite de conserver une
        référence obsolète. Ne touche pas à un worker éventuellement actif.
        """
        self._current_project = None
        self._header_bar.set_idle()
        self._header_bar.set_open_output_enabled(False)
        self._progress_view.clear()

    def _sync_header_for_selected_project(self) -> None:
        """Aligne les boutons du header sur l'activité du worker."""
        if self._current_project is None:
            self._header_bar.set_idle()
            return
        if self._active_worker_project_id == self._current_project.id:
            token = self._current_pause_token
            if token is not None and token.is_paused():
                self._header_bar.set_paused()
            else:
                self._header_bar.set_running()
            return
        self._header_bar.set_idle()

    def _refresh_state(self) -> None:
        """Recalcule l'état de fraîcheur et met à jour le bandeau."""
        if self._current_project is None:
            return
        info = self._state_vm.compute(self._current_project)
        self._progress_view.set_state(info)

    # -------------------------------------------------------------- settings

    def open_visuals_settings(self) -> None:
        """Ouvre le dialogue de réglages et persiste ``Project.visuals``."""
        if self._current_project is None:
            self._warn_no_project(
                QCoreApplication.translate(
                    "VisualsController",
                    "Sélectionne un projet dans la sidebar avant de configurer.",
                )
            )
            return
        project = self._current_project
        dialog = VisualsSettingsView(parent=self._window, initial=project.visuals)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        visuals = dialog.get_visuals_settings()
        if visuals is None:
            return
        self._project_service.update_project(project.with_visuals(visuals))
        self.on_project_selected(project.id)

    # -------------------------------------------------------------- estimate

    def estimate_cost(self) -> None:
        """Estime le coût des visualisations et affiche un rapport."""
        project = self._current_project
        if project is None or project.visuals is None:
            QMessageBox.information(
                self._window,
                QCoreApplication.translate(
                    "VisualsController", "Visualisations non configurées"
                ),
                QCoreApplication.translate(
                    "VisualsController",
                    "Configurez d'abord les visualisations (⚙ Réglages).",
                ),
            )
            return
        visuals = project.visuals
        output_dir = self._generation_output_dir(project)
        languages = available_visuals_languages(output_dir)
        source = (
            project.generation.source_language
            if project.generation is not None
            else None
        )
        struct_lang = structure_language(source, languages)
        units = (
            load_text_units(output_dir, struct_lang)
            if struct_lang is not None
            else ()
        )
        estimation = VisualsCostEstimator().estimate(
            visuals=visuals,
            structure_units=units,
            language_count=len(languages),
        )
        _show_visuals_cost_dialog(
            self._window,
            project_name=project.name,
            estimation=estimation,
            structure_language=struct_lang,
            language_count=len(languages),
            cost_ceiling_usd=visuals.cost_ceiling_usd,
        )

    # -------------------------------------------------------------- generate

    def generate(self) -> None:
        """Lance la génération des visualisations dans un ``QThread`` worker."""
        project = self._current_project
        if project is None:
            self._warn_no_project(
                QCoreApplication.translate(
                    "VisualsController",
                    "Sélectionne un projet dans la sidebar avant de générer.",
                )
            )
            return
        if self._thread is not None:
            QMessageBox.warning(
                self._window,
                QCoreApplication.translate(
                    "VisualsController", "Génération déjà en cours"
                ),
                QCoreApplication.translate(
                    "VisualsController",
                    "Une génération de visualisations est déjà en cours.",
                ),
            )
            return
        if not self._validate(project):
            return
        assert project.visuals is not None  # noqa: S101 — garanti par _validate

        orchestrator = self._build_orchestrator()
        self._current_pause_token = PauseToken()
        self._active_worker_project_id = project.id
        languages = available_visuals_languages(self._generation_output_dir(project))
        self._progress_vm.reset(
            deliverables=_enabled_deliverables(project.visuals),
            languages=tuple(languages),
            cost_ceiling_usd=project.visuals.cost_ceiling_usd,
        )
        self._progress_view.apply_snapshot(
            self._progress_vm.cost_matrix_snapshot(),
            self._progress_vm.stats_snapshot(),
        )

        event_bus = VisualsQtEventBus(self)
        event_bus.event_emitted.connect(self._on_event)
        worker = _VisualsWorker(
            orchestrator=orchestrator,
            project=project,
            pause_token=self._current_pause_token,
            event_bus=event_bus,
        )
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run_generation)
        worker.finished.connect(self._on_worker_finished)
        worker.failed.connect(self._on_worker_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self._worker = worker
        self._thread = thread
        self._header_bar.set_running()
        thread.start()
        self.run_state_changed.emit()

    def _build_orchestrator(self) -> VisualsOrchestrator:
        """Construit l'orchestrateur (LLM DeepSeek + embeddings OpenAI si dispo).

        Returns:
            Un ``VisualsOrchestrator`` câblé. Le fournisseur d'embeddings est ``None``
            en l'absence de clé OpenAI (fallback AUTO par normalisation des libellés).
        """
        api_key = self._secrets_service.get_deepseek_api_key()
        assert api_key is not None  # noqa: S101 — garanti par _validate
        openai_key = self._secrets_service.get_openai_api_key()
        embedding_provider = (
            OpenAIEmbeddingProvider(api_key=openai_key)
            if openai_key is not None
            else None
        )
        return VisualsOrchestrator(
            artifacts=FsArtifactStore(),
            llm_provider=DeepSeekAdapter(api_key=api_key),
            prompts=PromptLoader(override_dir=self._app_paths.prompts_override_dir),
            retry_policy=RetryPolicy(),
            embedding_provider=embedding_provider,
        )

    def pause(self) -> None:
        """Demande la pause de la génération en cours."""
        if self._current_pause_token is None:
            return
        self._current_pause_token.request_pause()
        self._sync_header_for_selected_project()

    def resume(self) -> None:
        """Reprend la génération en pause."""
        if self._current_pause_token is None:
            return
        self._current_pause_token.resume()
        self._sync_header_for_selected_project()

    def cancel(self) -> None:
        """Demande l'annulation de la génération en cours."""
        if self._current_pause_token is None:
            return
        self._current_pause_token.request_cancel()

    def open_folder(self) -> None:
        """Ouvre le dossier ``visuals`` du projet sélectionné."""
        if self._current_project is None:
            return
        visuals_dir = self._visuals_dir(self._current_project)
        if not visuals_dir.exists():
            QMessageBox.information(
                self._window,
                QCoreApplication.translate(
                    "VisualsController", "Aucun dossier de visualisations"
                ),
                QCoreApplication.translate(
                    "VisualsController",
                    "Aucune visualisation n'a encore été produite pour ce projet.",
                ),
            )
            return
        open_in_file_explorer(visuals_dir)

    def reset_visuals(self) -> None:
        """Slot : supprime toutes les visualisations produites (dossier ``visuals/``).

        Demande confirmation, refuse pendant une génération, puis efface le dossier
        (livrables HTML + manifeste + état d'exécution). Réaffiche un dashboard vide et
        notifie la sidebar.
        """
        project = self._current_project
        if project is None:
            self._warn_no_project(
                QCoreApplication.translate(
                    "VisualsController",
                    "Sélectionne un projet dans la sidebar avant de réinitialiser.",
                )
            )
            return
        if self._thread is not None:
            QMessageBox.warning(
                self._window,
                QCoreApplication.translate("VisualsController", "Génération en cours"),
                QCoreApplication.translate(
                    "VisualsController",
                    "Impossible de réinitialiser pendant une génération. "
                    "Annule-la d'abord.",
                ),
            )
            return
        reply = QMessageBox.question(
            self._window,
            QCoreApplication.translate(
                "VisualsController", "Réinitialiser les visualisations ?"
            ),
            QCoreApplication.translate(
                "VisualsController",
                "Réinitialiser les visualisations de « {name} » ?\n\n"
                "Toutes les pages produites et l'état d'exécution seront supprimés. "
                "Cette action est irréversible.",
            ).format(name=project.name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        remove_feature_dir(
            self._logs_dock, self._visuals_dir(project), label="visualisations"
        )
        self._logs_dock.append_event(
            LogEvent(
                timestamp=datetime.now(tz=UTC),
                severity=Severity.INFO,
                code="VISUALS_RESET",
                message=f"Visualisations réinitialisées pour « {project.name} ».",
            )
        )
        self._header_bar.set_open_output_enabled(False)
        self._refresh_state()
        self._show_progress_for_selected_project(project)
        self.run_state_changed.emit()

    # ------------------------------------------------------------- end-of-run

    def _on_event(self, event: object) -> None:
        """Slot : reçoit chaque ``VisualsEvent`` côté UI thread.

        Args:
            event: Événement Visualisations.
        """
        if not isinstance(event, VisualsEvent):
            return
        self._logs_dock.append_event(_visuals_event_to_log(event))
        if not self._worker_on_current_project():
            return
        self._progress_vm.apply_event(event)
        self._progress_view.apply_snapshot(
            self._progress_vm.cost_matrix_snapshot(),
            self._progress_vm.stats_snapshot(),
        )

    def _on_worker_finished(self, final_status: object) -> None:
        """Slot : génération terminée normalement.

        Args:
            final_status: Statut final (``RunStatus``).
        """
        del final_status
        if self._worker_on_current_project():
            self._header_bar.set_finished()
            self._refresh_state()
            if self._current_project is not None:
                self._header_bar.set_open_output_enabled(
                    self._visuals_dir(self._current_project).exists()
                )
        self._cleanup_thread()

    def _on_worker_failed(self, error_message: str) -> None:
        """Slot : génération terminée sur exception non gérée.

        Args:
            error_message: Message d'erreur.
        """
        self._logs_dock.append_event(
            LogEvent(
                timestamp=datetime.now(tz=UTC),
                severity=Severity.FATAL,
                code="VISUALS_WORKER_FAILED",
                message=(
                    "Le worker de génération des visualisations s'est terminé sur une "
                    f"exception non gérée : {error_message}"
                ),
                extra={"raw_error": error_message},
            )
        )
        QMessageBox.critical(
            self._window,
            QCoreApplication.translate(
                "VisualsController",
                "La génération s'est terminée sur une erreur inattendue",
            ),
            error_message,
        )
        if self._worker_on_current_project():
            self._header_bar.set_finished()
        self._cleanup_thread()

    def _cleanup_thread(self) -> None:
        """Réinitialise les références au worker/thread après fin."""
        self._worker = None
        self._thread = None
        self._current_pause_token = None
        self._active_worker_project_id = None
        self.run_state_changed.emit()

    # -------------------------------------------------------------- helpers

    def _warn_no_project(self, message: str) -> None:
        """Affiche un avertissement « aucun projet sélectionné ».

        Args:
            message: Corps du message (action concernée).
        """
        QMessageBox.warning(
            self._window,
            QCoreApplication.translate(
                "VisualsController", "Aucun projet sélectionné"
            ),
            message,
        )

    def _validate(self, project: Project) -> bool:
        """Vérifie les prérequis de génération et affiche une erreur sinon.

        Args:
            project: Projet courant.

        Returns:
            ``True`` si la génération peut démarrer.
        """
        if not self._secrets_service.has_deepseek_key():
            QMessageBox.critical(
                self._window,
                QCoreApplication.translate(
                    "VisualsController", "Clé DeepSeek manquante"
                ),
                QCoreApplication.translate(
                    "VisualsController",
                    "Renseigne la clé DeepSeek dans « Édition → Paramètres globaux ».",
                ),
            )
            return False
        if project.visuals is None:
            QMessageBox.critical(
                self._window,
                QCoreApplication.translate(
                    "VisualsController", "Visualisations non configurées"
                ),
                QCoreApplication.translate(
                    "VisualsController",
                    "Configurez d'abord les visualisations (⚙ Réglages).",
                ),
            )
            return False
        info = self._state_vm.compute(project)
        if not info.can_generate:
            QMessageBox.information(
                self._window,
                QCoreApplication.translate(
                    "VisualsController", "Génération impossible"
                ),
                info.message,
            )
            return False
        return True

    def _worker_on_current_project(self) -> bool:
        """Indique si le projet affiché est celui du worker actif.

        Returns:
            ``True`` si les deux coïncident.
        """
        return (
            self._current_project is not None
            and self._active_worker_project_id is not None
            and self._current_project.id == self._active_worker_project_id
        )

    @staticmethod
    def _generation_output_dir(project: Project) -> Path:
        """Dossier des livrables de génération du projet.

        Args:
            project: Projet.

        Returns:
            ``<emplacement>/generation/output``.
        """
        return (
            project.workspace_folder
            / GENERATION_WORKSPACE_SUBDIR
            / GENERATION_OUTPUT_SUBDIR
        )

    @staticmethod
    def _visuals_dir(project: Project) -> Path:
        """Dossier de la fonctionnalité Visualisations du projet.

        Args:
            project: Projet.

        Returns:
            ``<emplacement>/visuals``.
        """
        return project.workspace_folder / VISUALS_WORKSPACE_SUBDIR


def _visuals_event_to_log(event: VisualsEvent) -> LogEvent:
    """Convertit un ``VisualsEvent`` en ``LogEvent`` pour le LogsDock.

    Args:
        event: Événement Visualisations.

    Returns:
        Un ``LogEvent`` lisible dans le panneau de logs.
    """
    if isinstance(event, VisualsGenerationStarted):
        return LogEvent(
            timestamp=event.timestamp,
            severity=Severity.INFO,
            code="VISUALS_STARTED",
            message="Génération des visualisations démarrée",
        )
    if isinstance(event, VisualsLanguageStarted):
        return LogEvent(
            timestamp=event.timestamp,
            severity=Severity.INFO,
            code="VISUALS_LANGUAGE_STARTED",
            message=f"Visualisations ({event.language.value})…",
        )
    if isinstance(event, VisualsRetryAttempt):
        return LogEvent(
            timestamp=event.timestamp,
            severity=Severity.WARNING,
            code="VISUALS_RETRY",
            message=(
                f"{event.stage} ({event.language.value}) retry #{event.attempt} "
                f"dans {event.delay_seconds:.1f}s "
                f"({event.error.code} : {event.error.user_message})"
            ),
            extra={"attempt": event.attempt, "error_code": event.error.code},
        )
    if isinstance(event, VisualsLanguageFinished):
        severity = (
            Severity.ERROR if event.status is PhaseStatus.FAILED else Severity.INFO
        )
        message = (
            f"Visualisations ({event.language.value}) → "
            f"{event.status.value} (coût ${event.cost_usd:.4f})"
        )
        extra: dict[str, object] = {"cost_usd": event.cost_usd}
        if event.error is not None:
            message = f"{message}\n    └─ {event.error.code} : {event.error.user_message}"
            extra["error_code"] = event.error.code
        return LogEvent(
            timestamp=event.timestamp,
            severity=severity,
            code="VISUALS_LANGUAGE_FINISHED",
            message=message,
            extra=extra,
        )
    if isinstance(event, VisualsGenerationFinished):
        ceiling_note = (
            f" — {_MSG_CEILING_REACHED}" if event.status is RunStatus.PAUSED else ""
        )
        return LogEvent(
            timestamp=event.timestamp,
            severity=(
                Severity.INFO
                if event.status is RunStatus.COMPLETED
                else Severity.WARNING
            ),
            code="VISUALS_FINISHED",
            message=(
                f"Génération des visualisations terminée : {event.status.value} "
                f"(coût total ${event.total_cost_usd:.4f}){ceiling_note}"
            ),
        )
    return LogEvent(
        timestamp=event.timestamp,
        severity=Severity.INFO,
        code="VISUALS_EVENT",
        message=type(event).__name__,
    )


def _show_visuals_cost_dialog(
    parent: QWidget,
    *,
    project_name: str,
    estimation: VisualsCostEstimation,
    structure_language: Language | None,
    language_count: int,
    cost_ceiling_usd: float | None,
) -> None:
    """Affiche le dialogue détaillant l'estimation de coût des visualisations.

    Args:
        parent: Fenêtre parente.
        project_name: Nom du projet.
        estimation: Résultat du ``VisualsCostEstimator``.
        structure_language: Langue d'extraction de la structure (``None`` si aucune).
        language_count: Nombre de langues latines disponibles.
        cost_ceiling_usd: Plafond budget éventuel.
    """
    from fahmi2.ui.cost_estimate_dialog import show_cost_estimate  # noqa: PLC0415

    struct_label = (
        structure_language.value if structure_language is not None else "—"
    )
    header = [
        QCoreApplication.translate("VisualsController", "<b>Projet :</b> {name}").format(
            name=project_name
        ),
        QCoreApplication.translate(
            "VisualsController", "<b>Langue de structure :</b> {lang}"
        ).format(lang=struct_label),
        QCoreApplication.translate(
            "VisualsController", "<b>Langues latines :</b> {count}"
        ).format(count=language_count),
        QCoreApplication.translate(
            "VisualsController", "<b>Unités de texte :</b> {count}"
        ).format(count=estimation.units_total),
    ]
    breakdown = [
        (
            QCoreApplication.translate("VisualsController", "Carte des connaissances"),
            estimation.knowledge_map_usd,
        ),
        (
            QCoreApplication.translate("VisualsController", "Diagrammes"),
            estimation.diagrams_usd,
        ),
        (
            QCoreApplication.translate(
                "VisualsController", "Traduction des libellés"
            ),
            estimation.translation_usd,
        ),
    ]
    show_cost_estimate(
        parent,
        title=QCoreApplication.translate(
            "VisualsController", "Estimation du coût des visualisations"
        ),
        header_lines=header,
        breakdown=breakdown,
        total_usd=estimation.total_usd,
        low_usd=estimation.low_usd,
        high_usd=estimation.high_usd,
        cost_ceiling_usd=cost_ceiling_usd,
    )


__all__ = ["VisualsController"]
