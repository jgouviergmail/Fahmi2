"""``PedagogyController`` — orchestration de l'onglet Supports pédagogiques.

Parallèle au ``GenerationController`` (mais sans STT/ffmpeg ni matrice DB) :

- Maintient le projet sélectionné et rafraîchit le bandeau d'état (fraîcheur).
- Ouvre le dialogue de réglages et persiste ``Project.pedagogy``.
- Estime le coût (``PedagogyCostEstimator``).
- Déporte la génération dans un ``QThread`` worker (``SupportsOrchestrator``),
  bridge les ``PedagogyEvent`` vers la vue de progression + le dock de logs.
- Gère pause / reprise / annulation via le ``PauseToken``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import assert_never, cast

from PySide6.QtCore import QCoreApplication, QObject, QThread, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QMessageBox,
    QWidget,
)

from fahmi2.app.pedagogy_cost_estimator import (
    PedagogyCostEstimation,
    PedagogyCostEstimator,
)
from fahmi2.app.pedagogy_export import (
    export_pedagogy_documents,
    export_pedagogy_to_apkg,
)
from fahmi2.app.project_service import ProjectService
from fahmi2.app.secrets_service import SecretsService
from fahmi2.app.supports_orchestrator import SupportsOrchestrator
from fahmi2.core.config.paths import AppPaths
from fahmi2.core.errors.exceptions import Fahmi2Error
from fahmi2.core.errors.severity import Severity
from fahmi2.core.logging.event import LogEvent
from fahmi2.core.retry.policy import RetryPolicy
from fahmi2.domain.enums import ExportFormat, Language, PhaseStatus, RunStatus
from fahmi2.domain.generation import (
    GENERATION_OUTPUT_SUBDIR,
    GENERATION_WORKSPACE_SUBDIR,
)
from fahmi2.domain.ids import ProjectId
from fahmi2.domain.pedagogy import PEDAGOGY_WORKSPACE_SUBDIR
from fahmi2.domain.project import Project
from fahmi2.infra.llm.deepseek_adapter import DeepSeekAdapter
from fahmi2.infra.prompts.loader import PromptLoader
from fahmi2.infra.storage.fs_artifacts import FsArtifactStore
from fahmi2.infra.storage.sqlite_state import SqliteState
from fahmi2.pedagogy.artifact_reader import read_generated_costs
from fahmi2.pedagogy.events import (
    PedagogyEvent,
    SupportFinished,
    SupportGenerationFinished,
    SupportGenerationStarted,
    SupportRetryAttempt,
    SupportStarted,
)
from fahmi2.pedagogy.run_state import read_run_state
from fahmi2.pedagogy.sources import load_chapters
from fahmi2.pedagogy.support_registry import SupportGeneratorRegistry
from fahmi2.pipeline.pause_token import PauseToken
from fahmi2.ui._export_ui import choose_export_format, run_document_export
from fahmi2.ui._file_explorer import open_in_file_explorer
from fahmi2.ui._fs import remove_feature_dir
from fahmi2.ui.dialogs.pedagogy_settings_view import PedagogySettingsView
from fahmi2.ui.pedagogy_labels import export_labels, support_label
from fahmi2.ui.qt_event_bus import PedagogyQtEventBus
from fahmi2.ui.viewmodels.pedagogy_progress import PedagogyProgressViewModel
from fahmi2.ui.viewmodels.pedagogy_state import PedagogyStateViewModel
from fahmi2.ui.widgets.logs_dock import LogsDock
from fahmi2.ui.widgets.pedagogy_progress_view import PedagogyProgressView
from fahmi2.ui.widgets.project_header_bar import ProjectHeaderBar

_APKG_SUFFIX = ".apkg"
_APKG_FILTER = "Paquets Anki (*.apkg)"
#: Plafond de coût atteint : statut renvoyé par l'orchestrateur.
_MSG_CEILING_REACHED = (
    "Plafond de coût atteint — génération interrompue (supports restants non "
    "générés)."
)


class _PedagogyWorker(QObject):
    """Worker QObject exécutant ``orchestrator.generate`` dans un thread."""

    finished = Signal(object)  # RunStatus
    failed = Signal(str)

    def __init__(
        self,
        *,
        orchestrator: SupportsOrchestrator,
        project: Project,
        pause_token: PauseToken,
        event_bus: PedagogyQtEventBus,
    ) -> None:
        """Construit le worker.

        Args:
            orchestrator: Orchestrateur de supports.
            project: Projet à traiter.
            pause_token: Jeton de pause/annulation.
            event_bus: Bus d'événements pédagogie (Qt).
        """
        super().__init__()
        self._orchestrator = orchestrator
        self._project = project
        self._pause_token = pause_token
        self._event_bus = event_bus

    def run_generation(self) -> None:
        """Exécute la génération et émet le signal final.

        Toute exception est convertie en signal ``failed`` plutôt que de laisser
        le thread crasher silencieusement.
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


class PedagogyController(QObject):
    """Orchestre la génération des supports depuis l'onglet pédagogique."""

    #: Émis quand le statut de la génération change (démarrage / fin / échec /
    #: réinitialisation), pour rafraîchir les icônes de la sidebar.
    run_state_changed = Signal()

    def __init__(
        self,
        *,
        header_bar: ProjectHeaderBar,
        progress_view: PedagogyProgressView,
        logs_dock: LogsDock,
        window: QWidget,
        project_service: ProjectService,
        secrets_service: SecretsService,
        state: SqliteState,
        app_paths: AppPaths,
        registry: SupportGeneratorRegistry,
    ) -> None:
        """Construit le contrôleur et branche les signaux du cockpit pédagogie.

        Args:
            header_bar: Barre d'actions.
            progress_view: Vue bandeau + table de progression.
            logs_dock: Dock de logs partagé.
            window: Fenêtre parente (parent des dialogues).
            project_service: Service projets.
            secrets_service: Service secrets (clé DeepSeek).
            state: Stockage SQLite.
            app_paths: Chemins applicatifs (override des prompts).
            registry: Registre des générateurs de supports.
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
        self._registry = registry

        self._current_project: Project | None = None
        self._active_worker_project_id: ProjectId | None = None
        self._current_pause_token: PauseToken | None = None
        self._worker: _PedagogyWorker | None = None
        self._thread: QThread | None = None
        self._progress_vm = PedagogyProgressViewModel()
        self._state_vm = PedagogyStateViewModel(project_service=project_service)

        self._header_bar.settings_requested.connect(self.open_pedagogy_settings)
        self._header_bar.estimate_cost_requested.connect(self.estimate_cost)
        self._header_bar.start_requested.connect(self.generate)
        self._header_bar.pause_requested.connect(self.pause)
        self._header_bar.resume_requested.connect(self.resume)
        self._header_bar.cancel_requested.connect(self.cancel)
        self._header_bar.open_output_requested.connect(self.open_folder)
        self._header_bar.export_requested.connect(self._on_export_requested)
        self._header_bar.reset_requested.connect(self.reset_pedagogy)

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
        self._header_bar.set_open_output_enabled(self._pedagogy_dir(project).exists())
        self._refresh_state()
        self._show_progress_for_selected_project(project)

    def _show_progress_for_selected_project(self, project: Project) -> None:
        """Affiche l'état des supports du projet sélectionné.

        Aligne le comportement sur le dashboard Génération : si un worker est actif
        sur ce projet, affiche sa progression live ; sinon, si la pédagogie est
        configurée, reconstruit l'**état de la dernière exécution** depuis le disque
        (supports déjà générés en « terminé » + coût, les autres en attente) ; sinon
        une grille vide.

        Args:
            project: Projet sélectionné.
        """
        if self._worker_on_current_project():
            vm = self._progress_vm
        else:
            vm = PedagogyProgressViewModel()
            if project.pedagogy is not None:
                pedagogy_dir = self._pedagogy_dir(project)
                costs = read_generated_costs(
                    pedagogy_dir,
                    project.pedagogy.selected_supports,
                    project.pedagogy.languages,
                )
                run_state = read_run_state(pedagogy_dir)
                vm.load_persisted(
                    supports=tuple(project.pedagogy.selected_supports),
                    languages=project.pedagogy.languages,
                    generated_costs=costs,
                    cost_ceiling_usd=project.pedagogy.cost_ceiling_usd,
                    overall_status=run_state.status if run_state else None,
                    started_at=run_state.started_at if run_state else None,
                    finished_at=run_state.finished_at if run_state else None,
                )
        self._progress_view.apply_snapshot(
            vm.cost_matrix_snapshot(), vm.stats_snapshot()
        )

    @property
    def current_project_id(self) -> ProjectId | None:
        """Identifiant du projet affiché, ou ``None``.

        Returns:
            ``ProjectId`` ou ``None``.
        """
        return self._current_project.id if self._current_project is not None else None

    def clear_current_project(self) -> None:
        """Désélectionne le projet courant et réinitialise le cockpit pédagogique.

        À appeler quand le projet affiché vient d'être supprimé : évite de
        conserver une référence obsolète (et de ressusciter le projet en base via
        ``update_project``). Ne touche pas à un worker éventuellement actif.
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

    def open_pedagogy_settings(self) -> None:
        """Ouvre le dialogue de réglages et persiste ``Project.pedagogy``."""
        if self._current_project is None:
            QMessageBox.warning(
                self._window,
                QCoreApplication.translate(
                    "PedagogyController", "Aucun projet sélectionné"
                ),
                QCoreApplication.translate(
                    "PedagogyController",
                    "Sélectionne un projet dans la sidebar avant de configurer.",
                ),
            )
            return
        project = self._current_project
        dialog = PedagogySettingsView(
            parent=self._window,
            available_languages=self._available_languages(project),
            initial=project.pedagogy,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        pedagogy = dialog.get_pedagogy_settings()
        if pedagogy is None:
            return
        self._project_service.update_project(project.with_pedagogy(pedagogy))
        self.on_project_selected(project.id)

    # -------------------------------------------------------------- estimate

    def estimate_cost(self) -> None:
        """Estime le coût des supports sélectionnés et affiche un rapport."""
        project = self._current_project
        if project is None or project.pedagogy is None:
            QMessageBox.information(
                self._window,
                QCoreApplication.translate(
                    "PedagogyController", "Supports non configurés"
                ),
                QCoreApplication.translate(
                    "PedagogyController",
                    "Configurez d'abord les supports pédagogiques (⚙ Réglages).",
                ),
            )
            return
        pedagogy = project.pedagogy
        generation_output_dir = self._generation_output_dir(project)
        chapters_by_language = {
            language: load_chapters(generation_output_dir, language)
            for language in pedagogy.languages
        }
        estimation = PedagogyCostEstimator().estimate(
            pedagogy=pedagogy, chapters_by_language=chapters_by_language
        )
        _show_pedagogy_cost_dialog(
            self._window,
            project_name=project.name,
            estimation=estimation,
            cost_ceiling_usd=pedagogy.cost_ceiling_usd,
        )

    # -------------------------------------------------------------- generate

    def generate(self) -> None:
        """Lance la génération des supports dans un ``QThread`` worker."""
        project = self._current_project
        if project is None:
            QMessageBox.warning(
                self._window,
                QCoreApplication.translate(
                    "PedagogyController", "Aucun projet sélectionné"
                ),
                QCoreApplication.translate(
                    "PedagogyController",
                    "Sélectionne un projet dans la sidebar avant de générer.",
                ),
            )
            return
        if self._thread is not None:
            QMessageBox.warning(
                self._window,
                QCoreApplication.translate(
                    "PedagogyController", "Génération déjà en cours"
                ),
                QCoreApplication.translate(
                    "PedagogyController",
                    "Une génération de supports est déjà en cours.",
                ),
            )
            return
        if not self._validate(project):
            return
        assert project.pedagogy is not None

        api_key = self._secrets_service.get_deepseek_api_key()
        assert api_key is not None  # garanti par _validate
        orchestrator = SupportsOrchestrator(
            registry=self._registry,
            artifacts=FsArtifactStore(),
            llm_provider=DeepSeekAdapter(api_key=api_key),
            prompts=PromptLoader(override_dir=self._app_paths.prompts_override_dir),
            retry_policy=RetryPolicy(),
        )

        self._current_pause_token = PauseToken()
        self._active_worker_project_id = project.id
        self._progress_vm.reset(
            supports=tuple(project.pedagogy.selected_supports),
            languages=project.pedagogy.languages,
            cost_ceiling_usd=project.pedagogy.cost_ceiling_usd,
        )
        self._progress_view.apply_snapshot(
            self._progress_vm.cost_matrix_snapshot(),
            self._progress_vm.stats_snapshot(),
        )

        event_bus = PedagogyQtEventBus(self)
        event_bus.event_emitted.connect(self._on_event)

        worker = _PedagogyWorker(
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
        """Ouvre le dossier ``pedagogy`` du projet sélectionné."""
        if self._current_project is None:
            return
        pedagogy_dir = self._pedagogy_dir(self._current_project)
        if not pedagogy_dir.exists():
            QMessageBox.information(
                self._window,
                QCoreApplication.translate(
                    "PedagogyController", "Aucun dossier de supports"
                ),
                QCoreApplication.translate(
                    "PedagogyController",
                    "Aucun support n'a encore été généré pour ce projet.",
                ),
            )
            return
        open_in_file_explorer(pedagogy_dir)

    def reset_pedagogy(self) -> None:
        """Slot : supprime tous les supports générés (dossier ``pedagogy/``).

        Demande confirmation, refuse pendant une génération, puis efface le dossier
        des supports (artefacts + manifeste + état d'exécution). Réaffiche un
        dashboard vide et notifie la sidebar.
        """
        project = self._current_project
        if project is None:
            QMessageBox.warning(
                self._window,
                QCoreApplication.translate(
                    "PedagogyController", "Aucun projet sélectionné"
                ),
                QCoreApplication.translate(
                    "PedagogyController",
                    "Sélectionne un projet dans la sidebar avant de réinitialiser.",
                ),
            )
            return
        if self._thread is not None:
            QMessageBox.warning(
                self._window,
                QCoreApplication.translate(
                    "PedagogyController", "Génération en cours"
                ),
                QCoreApplication.translate(
                    "PedagogyController",
                    "Impossible de réinitialiser pendant une génération. "
                    "Annule-la d'abord.",
                ),
            )
            return
        reply = QMessageBox.question(
            self._window,
            QCoreApplication.translate(
                "PedagogyController", "Réinitialiser les supports ?"
            ),
            QCoreApplication.translate(
                "PedagogyController",
                "Réinitialiser les supports pédagogiques de « {name} » ?\n\n"
                "Tous les supports générés, leurs exports intermédiaires et "
                "l'état d'exécution seront supprimés. "
                "Cette action est irréversible.",
            ).format(name=project.name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        remove_feature_dir(
            self._logs_dock, self._pedagogy_dir(project), label="pédagogie"
        )
        self._logs_dock.append_event(
            LogEvent(
                timestamp=datetime.now(tz=UTC),
                severity=Severity.INFO,
                code="PEDAGOGY_RESET",
                message=f"Supports pédagogiques réinitialisés pour « {project.name} ».",
            )
        )
        self._header_bar.set_open_output_enabled(False)
        self._refresh_state()
        self._show_progress_for_selected_project(project)
        self.run_state_changed.emit()

    def export_apkg(self) -> None:
        """Exporte les supports générés vers un paquet Anki ``.apkg``."""
        project = self._current_project
        if project is None:
            QMessageBox.warning(
                self._window,
                QCoreApplication.translate(
                    "PedagogyController", "Aucun projet sélectionné"
                ),
                QCoreApplication.translate(
                    "PedagogyController",
                    "Sélectionne un projet dans la sidebar avant d'exporter.",
                ),
            )
            return
        path_str, _ = QFileDialog.getSaveFileName(
            self._window,
            QCoreApplication.translate("PedagogyController", "Exporter vers Anki"),
            f"{project.name}{_APKG_SUFFIX}",
            _APKG_FILTER,
        )
        if not path_str:
            return
        try:
            result = export_pedagogy_to_apkg(project, output_path=Path(path_str))
        except Fahmi2Error as exc:
            QMessageBox.critical(
                self._window,
                QCoreApplication.translate("PedagogyController", "Export impossible"),
                f"{exc.code}\n\n{exc.user_message}",
            )
            return
        except Exception as exc:  # noqa: BLE001 — affichage UX puis stop
            QMessageBox.critical(
                self._window,
                QCoreApplication.translate("PedagogyController", "Erreur inattendue"),
                f"{type(exc).__name__} : {exc}",
            )
            return
        if result.note_count == 0:
            QMessageBox.information(
                self._window,
                QCoreApplication.translate(
                    "PedagogyController", "Aucun support exportable"
                ),
                QCoreApplication.translate(
                    "PedagogyController",
                    "Aucune carte Anki à exporter (flashcards, cloze ou QCM requis). "
                    "Générez d'abord des supports exportables.",
                ),
            )
            return
        self._logs_dock.append_event(
            LogEvent(
                timestamp=datetime.now(tz=UTC),
                severity=Severity.INFO,
                code="PEDAGOGY_EXPORTED",
                message=(
                    f"{result.note_count} carte(s) Anki exportée(s) vers "
                    f"{result.output_path}"
                ),
            )
        )
        QMessageBox.information(
            self._window,
            QCoreApplication.translate("PedagogyController", "Export terminé"),
            QCoreApplication.translate(
                "PedagogyController",
                "{count} carte(s) Anki exportée(s) vers :\n{path}",
            ).format(count=result.note_count, path=result.output_path),
        )

    def _on_export_requested(self) -> None:
        """Propose les formats d'export configurés et exécute l'export choisi.

        APKG est routé vers ``export_apkg`` ; les formats documentaires
        (Markdown / PDF / HTML) passent par le helper partagé.
        """
        project = self._current_project
        if project is None:
            QMessageBox.warning(
                self._window,
                QCoreApplication.translate(
                    "PedagogyController", "Aucun projet sélectionné"
                ),
                QCoreApplication.translate(
                    "PedagogyController",
                    "Sélectionne un projet dans la sidebar avant d'exporter.",
                ),
            )
            return
        if project.pedagogy is None:
            QMessageBox.information(
                self._window,
                QCoreApplication.translate(
                    "PedagogyController", "Supports non configurés"
                ),
                QCoreApplication.translate(
                    "PedagogyController",
                    "Configurez d'abord les supports pédagogiques (⚙ Réglages).",
                ),
            )
            return
        labels = export_labels()
        fmt = choose_export_format(
            window=self._window,
            configured_formats=project.pedagogy.export_formats,
            label_by_format=labels,
        )
        if fmt is None:
            return
        if fmt is ExportFormat.APKG:
            self.export_apkg()
            return
        run_document_export(
            window=self._window,
            logs_dock=self._logs_dock,
            label=labels[fmt],
            exporter=lambda d: export_pedagogy_documents(
                project, output_dir=d, fmt=fmt
            ),
        )

    # ------------------------------------------------------------- end-of-run

    def _on_event(self, event: object) -> None:
        """Slot : reçoit chaque ``PedagogyEvent`` côté UI thread.

        Args:
            event: Événement pédagogie.
        """
        pedagogy_event = cast("PedagogyEvent", event)
        self._logs_dock.append_event(_pedagogy_event_to_log(pedagogy_event))
        if not self._worker_on_current_project():
            return
        self._progress_vm.apply_event(pedagogy_event)
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
                    self._pedagogy_dir(self._current_project).exists()
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
                code="PEDAGOGY_WORKER_FAILED",
                message=(
                    "Le worker de génération des supports s'est terminé sur une "
                    f"exception non gérée : {error_message}"
                ),
                extra={"raw_error": error_message},
            )
        )
        QMessageBox.critical(
            self._window,
            QCoreApplication.translate(
                "PedagogyController",
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
        # Fin de génération (succès / échec / annulation / plafond) : rafraîchir
        # les icônes de statut de la sidebar.
        self.run_state_changed.emit()

    # -------------------------------------------------------------- helpers

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
                "Clé DeepSeek manquante",
                "Renseigne la clé DeepSeek dans « Édition → Paramètres globaux ».",
            )
            return False
        if project.pedagogy is None:
            QMessageBox.critical(
                self._window,
                "Supports non configurés",
                "Configurez d'abord les supports pédagogiques (⚙ Réglages).",
            )
            return False
        info = self._state_vm.compute(project)
        if not info.can_generate:
            QMessageBox.information(
                self._window, "Génération impossible", info.message
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

    def _available_languages(self, project: Project) -> tuple[Language, ...]:
        """Langues proposées : toutes les langues supportées.

        Les supports sont produits par LLM dans la langue cible quelle que soit la
        langue du document source ; l'orchestrateur résout une langue de contenu
        (doc consolidé existant) indépendamment de la langue choisie. Le choix
        n'est donc pas restreint à ce que la génération a produit.

        Args:
            project: Projet courant (inutilisé : indépendant de la génération).

        Returns:
            Toutes les langues supportées.
        """
        del project
        return tuple(Language)

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
    def _pedagogy_dir(project: Project) -> Path:
        """Dossier des supports pédagogiques du projet.

        Args:
            project: Projet.

        Returns:
            ``<emplacement>/pedagogy``.
        """
        return project.workspace_folder / PEDAGOGY_WORKSPACE_SUBDIR


def _pedagogy_event_to_log(event: PedagogyEvent) -> LogEvent:
    """Convertit un ``PedagogyEvent`` en ``LogEvent`` pour le LogsDock.

    Args:
        event: Événement pédagogie.

    Returns:
        Un ``LogEvent`` lisible dans le panneau de logs.
    """
    if isinstance(event, SupportGenerationStarted):
        return LogEvent(
            timestamp=event.timestamp,
            severity=Severity.INFO,
            code="PEDAGOGY_STARTED",
            message="Génération des supports démarrée",
        )
    if isinstance(event, SupportStarted):
        return LogEvent(
            timestamp=event.timestamp,
            severity=Severity.INFO,
            code="PEDAGOGY_SUPPORT_STARTED",
            message=f"{support_label(event.support_type)} ({event.language.value})…",
        )
    if isinstance(event, SupportRetryAttempt):
        return LogEvent(
            timestamp=event.timestamp,
            severity=Severity.WARNING,
            code="PEDAGOGY_RETRY",
            message=(
                f"{support_label(event.support_type)} retry #{event.attempt} "
                f"dans {event.delay_seconds:.1f}s "
                f"({event.error.code} : {event.error.user_message})"
            ),
            extra={"attempt": event.attempt, "error_code": event.error.code},
        )
    if isinstance(event, SupportFinished):
        severity = (
            Severity.ERROR if event.status is PhaseStatus.FAILED else Severity.INFO
        )
        message = (
            f"{support_label(event.support_type)} ({event.language.value}) → "
            f"{event.status.value} (coût ${event.cost_usd:.4f})"
        )
        extra: dict[str, object] = {"cost_usd": event.cost_usd}
        if event.error is not None:
            message = f"{message}\n    └─ {event.error.code} : {event.error.user_message}"
            extra["error_code"] = event.error.code
        return LogEvent(
            timestamp=event.timestamp,
            severity=severity,
            code="PEDAGOGY_SUPPORT_FINISHED",
            message=message,
            extra=extra,
        )
    if isinstance(event, SupportGenerationFinished):
        ceiling_note = (
            f" — {_MSG_CEILING_REACHED}"
            if event.status is RunStatus.PAUSED
            else ""
        )
        return LogEvent(
            timestamp=event.timestamp,
            severity=(
                Severity.INFO
                if event.status is RunStatus.COMPLETED
                else Severity.WARNING
            ),
            code="PEDAGOGY_FINISHED",
            message=(
                f"Génération des supports terminée : {event.status.value} "
                f"(coût total ${event.total_cost_usd:.4f}){ceiling_note}"
            ),
        )
    assert_never(event)


def _show_pedagogy_cost_dialog(
    parent: QWidget,
    *,
    project_name: str,
    estimation: PedagogyCostEstimation,
    cost_ceiling_usd: float | None,
) -> None:
    """Affiche un ``QMessageBox`` détaillant l'estimation de coût pédagogie.

    Args:
        parent: Fenêtre parente.
        project_name: Nom du projet.
        estimation: Résultat du ``PedagogyCostEstimator``.
        cost_ceiling_usd: Plafond budget éventuel.
    """
    from fahmi2.ui.cost_estimate_dialog import show_cost_estimate  # noqa: PLC0415

    header = [
        f"<b>Projet :</b> {project_name}",
        f"<b>Chapitres (toutes langues) :</b> {estimation.chapters_total}",
    ]
    breakdown = [
        (support_label(support), estimation.per_support_usd[support])
        for support in SupportGeneratorRegistry.canonical_order()
        if support in estimation.per_support_usd
    ]
    show_cost_estimate(
        parent,
        title="Estimation du coût des supports",
        header_lines=header,
        breakdown=breakdown,
        total_usd=estimation.total_usd,
        low_usd=estimation.low_usd,
        high_usd=estimation.high_usd,
        cost_ceiling_usd=cost_ceiling_usd,
    )


__all__ = ["PedagogyController"]
