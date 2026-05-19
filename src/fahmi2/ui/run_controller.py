"""``RunController`` — orchestration du lifecycle Run côté UI.

Cette classe :

- Maintient le **projet sélectionné** dans la sidebar.
- Construit les providers réels (``STTProvider``, ``LLMProvider``,
  ``FFmpegExtractor`` bundlé) à partir des paramètres du projet et des clés
  API stockées dans le ``SecretsService``.
- Déporte l'exécution du run dans un ``QThread`` worker pour ne pas bloquer
  l'UI thread.
- Branche le ``QtEventBus`` aux mises à jour temps réel des vues (matrice,
  stats strip, logs dock).
- Gère pause / reprise / annulation via le ``PauseToken``.
"""

from __future__ import annotations

import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from PySide6.QtCore import QObject, Qt, QThread, QUrl, Signal
from PySide6.QtGui import QCursor, QDesktopServices
from PySide6.QtWidgets import QApplication, QMessageBox

from fahmi2.app.cost_estimator import CostEstimation, CostEstimator
from fahmi2.app.hardware_probe import HardwareInfo
from fahmi2.app.project_service import ProjectService
from fahmi2.app.run_orchestrator import RunOrchestrator
from fahmi2.app.secrets_service import SecretsService
from fahmi2.app.video_scanner import scan_input_folder
from fahmi2.core.config.paths import AppPaths
from fahmi2.core.errors.error_info import ErrorInfo
from fahmi2.core.errors.exceptions import Fahmi2Error
from fahmi2.core.errors.severity import Severity
from fahmi2.core.logging.event import LogEvent
from fahmi2.core.retrieval.interface import PassthroughRetriever
from fahmi2.core.retry.policy import RetryPolicy
from fahmi2.domain.enums import RunStatus, SttProvider
from fahmi2.domain.ids import ProjectId
from fahmi2.domain.project import Project
from fahmi2.domain.run import Run
from fahmi2.infra.audio.ffmpeg_extractor import FFmpegExtractor
from fahmi2.infra.llm.deepseek_adapter import DeepSeekAdapter
from fahmi2.infra.llm.interface import LLMProvider
from fahmi2.infra.prompts.loader import PromptLoader
from fahmi2.infra.storage.fs_artifacts import FsArtifactStore
from fahmi2.infra.storage.sqlite_state import SqliteState
from fahmi2.infra.stt.faster_whisper_adapter import FasterWhisperAdapter
from fahmi2.infra.stt.interface import STTProvider
from fahmi2.infra.stt.openai_whisper_adapter import OpenAIWhisperAdapter
from fahmi2.pipeline.engine import PipelineEngine
from fahmi2.pipeline.events import (
    PhaseFinished,
    PhaseStarted,
    PipelineEvent,
    RetryAttempt,
    RunFinished,
    RunStarted,
)
from fahmi2.pipeline.handlers.phase_0_stt import Phase0SttHandler
from fahmi2.pipeline.handlers.phase_1_term_extraction import (
    Phase1TermExtractionHandler,
)
from fahmi2.pipeline.handlers.phase_2_glossary_reconciliation import (
    Phase2GlossaryReconciliationHandler,
)
from fahmi2.pipeline.handlers.phase_3_reformulation import Phase3ReformulationHandler
from fahmi2.pipeline.handlers.phase_4_structuration import Phase4StructurationHandler
from fahmi2.pipeline.handlers.phase_5_consolidation import Phase5ConsolidationHandler
from fahmi2.pipeline.handlers.phase_6_translation import Phase6TranslationHandler
from fahmi2.pipeline.handlers.phase_7_coherence import Phase7CoherenceHandler
from fahmi2.pipeline.pause_token import PauseToken
from fahmi2.pipeline.phase_handler import PhaseContext
from fahmi2.pipeline.phase_registry import PhaseRegistry
from fahmi2.ui.main_window import MainWindow
from fahmi2.ui.qt_event_bus import QtEventBus
from fahmi2.ui.viewmodels.run_matrix import RunMatrixViewModel
from fahmi2.ui.viewmodels.stats_strip import StatsStripViewModel


def build_default_registry() -> PhaseRegistry:
    """Construit le ``PhaseRegistry`` standard avec les 8 handlers.

    Returns:
        Un registre prêt à l'emploi.
    """
    return PhaseRegistry(
        [
            Phase0SttHandler(),
            Phase1TermExtractionHandler(),
            Phase2GlossaryReconciliationHandler(),
            Phase3ReformulationHandler(),
            Phase4StructurationHandler(),
            Phase5ConsolidationHandler(),
            Phase6TranslationHandler(),
            Phase7CoherenceHandler(),
        ]
    )


def build_ffmpeg_from_runtime() -> FFmpegExtractor:
    """Construit un ``FFmpegExtractor`` qui utilise les binaires bundlés.

    Returns:
        Un extracteur configuré : binaires bundlés en mode packagé, ``PATH``
        système sinon.
    """
    from fahmi2.core.config.paths import (  # noqa: PLC0415 — éviter cycle
        resolve_ffmpeg_binary_or_none,
        resolve_ffprobe_binary_or_none,
    )

    return FFmpegExtractor(
        ffmpeg_binary=resolve_ffmpeg_binary_or_none(),
        ffprobe_binary=resolve_ffprobe_binary_or_none(),
    )


class _RunWorker(QObject):
    """Worker QObject exécutant ``orchestrator.execute(run, ctx)`` dans un thread."""

    finished = Signal(object)  # RunStatus
    failed = Signal(str)

    def __init__(
        self,
        *,
        orchestrator: RunOrchestrator,
        run: Run,
        ctx: PhaseContext,
    ) -> None:
        """Construit le worker.

        Args:
            orchestrator: Orchestrateur applicatif.
            run: Run à exécuter.
            ctx: Contexte d'exécution.
        """
        super().__init__()
        self._orchestrator = orchestrator
        self._run = run
        self._ctx = ctx

    def run_pipeline(self) -> None:
        """Exécute le pipeline et émet le signal final.

        Toute exception est convertie en signal ``failed`` plutôt que de
        laisser le thread crasher silencieusement.
        """
        try:
            final_status = self._orchestrator.execute(run=self._run, ctx=self._ctx)
            self.finished.emit(final_status)
        except Exception as exc:  # noqa: BLE001 — isolation worker thread
            self.failed.emit(f"{type(exc).__name__}: {exc}")


class RunController(QObject):
    """Orchestre le lifecycle d'un Run depuis l'UI Qt."""

    def __init__(
        self,
        *,
        main_window: MainWindow,
        project_service: ProjectService,
        secrets_service: SecretsService,
        hardware: HardwareInfo,
        state: SqliteState,
        app_paths: AppPaths,
    ) -> None:
        """Construit le contrôleur et branche les signaux UI.

        Args:
            main_window: Fenêtre principale.
            project_service: Service projets.
            secrets_service: Service secrets.
            hardware: Info matérielle (pour valider STT local).
            state: Stockage SQLite.
            app_paths: Chemins applicatifs (pour cache modèles).
        """
        super().__init__(main_window)
        self._main_window = main_window
        self._project_service = project_service
        self._secrets_service = secrets_service
        self._hardware = hardware
        self._state = state
        self._app_paths = app_paths

        # « projet affiché » dans le dashboard et la sidebar.
        self._current_project: Project | None = None
        # « projet du worker actif » — distinct du projet affiché : permet de
        # garder le pipeline en cours sur un projet pendant que l'utilisateur
        # parcourt d'autres projets dans la sidebar.
        self._active_worker_project_id: ProjectId | None = None
        self._current_run: Run | None = None
        self._current_pause_token: PauseToken | None = None
        self._worker: _RunWorker | None = None
        self._thread: QThread | None = None
        self._registry = build_default_registry()
        # Drapeau levé par cancel_run pour déclencher le nettoyage des
        # livrables (suppression de l'output_dir + reset du cockpit) une fois
        # que le worker confirme la fin du Run.
        self._cleanup_after_cancel_requested: bool = False

        # Branchements UI ---------------------------------------------------
        self._main_window.projects_sidebar.set_on_project_selected(
            self._on_project_selected
        )
        self._main_window.header_bar.start_requested.connect(self.start_run)
        self._main_window.header_bar.pause_requested.connect(self.pause_run)
        self._main_window.header_bar.resume_requested.connect(self.resume_run)
        self._main_window.header_bar.cancel_requested.connect(self.cancel_run)
        self._main_window.header_bar.open_output_requested.connect(
            self.open_output_folder
        )
        self._main_window.header_bar.estimate_cost_requested.connect(
            self.estimate_cost
        )

    # ------------------------------------------------------------------ project

    def _on_project_selected(self, project_id: ProjectId) -> None:
        """Slot : met à jour l'état UI à la sélection d'un projet.

        Trois cas se distinguent côté boutons d'action :

        - Le projet sélectionné est celui d'un worker actif → l'état du
          header reflète ``running`` ou ``paused`` (selon le ``PauseToken``).
        - Le projet sélectionné a déjà un Run terminé → header en
          ``finished`` (Lancer ré-actif, Pause / Annuler désactivés).
        - Autres cas (projet neuf ou sans Run) → header en ``idle``.
        """
        project = self._project_service.get_project(project_id)
        if project is None:
            return
        self._current_project = project
        self._main_window.header_bar.set_title(project.settings.name)
        self._sync_header_for_selected_project()
        # Le bouton « Ouvrir le dossier de sortie » est actif si un dossier
        # output a déjà été produit (c'est-à-dire : au moins un run a tourné).
        output_dir = self._current_output_dir()
        self._main_window.header_bar.set_open_output_enabled(
            output_dir is not None and output_dir.exists()
        )
        self._refresh_views_with_last_run()

    @property
    def current_project_id(self) -> ProjectId | None:
        """Identifiant du projet actuellement affiché dans le dashboard.

        Returns:
            ``ProjectId`` ou ``None`` si aucun projet n'est sélectionné.
        """
        return self._current_project.id if self._current_project is not None else None

    def clear_current_project(self) -> None:
        """Désélectionne le projet courant et réinitialise le cockpit.

        À appeler typiquement lorsque le projet affiché vient d'être
        supprimé : on remet le titre à un placeholder, le header en
        ``idle``, et vide la matrice / les stats. Ne touche pas au
        worker éventuellement actif (qui reste suivi via
        ``_active_worker_project_id``).
        """
        self._current_project = None
        self._current_run = None
        self._main_window.header_bar.set_title("—")
        self._main_window.header_bar.set_idle()
        self._main_window.header_bar.set_open_output_enabled(False)
        self._reset_views()

    def _sync_header_for_selected_project(self) -> None:
        """Aligne l'état des boutons du header sur la situation réelle.

        Distingue le cas où le projet sélectionné a un worker actif
        (running/paused) du cas où on regarde simplement un projet
        terminé ou neuf (idle).
        """
        if self._current_project is None:
            self._main_window.header_bar.set_idle()
            return
        if (
            self._active_worker_project_id is not None
            and self._active_worker_project_id == self._current_project.id
        ):
            token = self._current_pause_token
            if token is not None and token.is_paused():
                self._main_window.header_bar.set_paused()
            else:
                self._main_window.header_bar.set_running()
            return
        self._main_window.header_bar.set_idle()

    def _refresh_views_with_last_run(self) -> None:
        """Rafraîchit matrice + stats avec le dernier run du projet courant.

        Si le projet ne contient aucun run, on affiche une **prévisualisation**
        : liste des vidéos détectées dans le dossier d'entrée, toutes phases
        en ``PENDING``. Cela permet à l'utilisateur de valider visuellement
        le périmètre avant le premier ``Lancer`` (sans avoir à créer un Run).
        Si le dossier d'entrée est inaccessible ou vide, on retombe sur des
        vues vides.
        """
        if self._current_project is None:
            return
        last_run = self._project_service.get_last_run(self._current_project.id)
        if last_run is None:
            self._current_run = None
            self._show_preview_for_project(self._current_project)
            return
        self._current_run = last_run
        self._refresh_views(last_run)

    def _show_preview_for_project(self, project: Project) -> None:
        """Affiche une prévisualisation du Run à venir.

        Scanne le dossier d'entrée et construit un ``MatrixSnapshot`` où
        chaque vidéo détectée occupe une ligne, toutes les phases marquées
        ``PENDING``. Échec silencieux du scan → vues vides.

        Args:
            project: Projet courant.
        """
        from fahmi2.domain.enums import PhaseStatus  # noqa: PLC0415
        from fahmi2.domain.ids import RunId  # noqa: PLC0415
        from fahmi2.ui.viewmodels.run_matrix import (  # noqa: PLC0415
            MatrixCell,
            MatrixRow,
            MatrixSnapshot,
        )
        from fahmi2.ui.viewmodels.stats_strip import StatsSnapshot  # noqa: PLC0415

        try:
            videos = scan_input_folder(project.settings.input_folder)
        except Fahmi2Error:
            self._reset_views()
            return

        phases = tuple(h.phase_id for h in self._registry.ordered_handlers())
        per_video_phases = {
            h.phase_id for h in self._registry.ordered_handlers() if h.is_per_video
        }
        rows = tuple(
            MatrixRow(
                video_id=v.video_id,
                video_label=v.source_path.name,
                cells={
                    phase_id: MatrixCell(
                        phase_id=phase_id,
                        status=PhaseStatus.PENDING,
                        cost_usd=0.0,
                        retry_count=0,
                        is_batch=phase_id not in per_video_phases,
                    )
                    for phase_id in phases
                },
            )
            for v in videos
        )
        self._main_window.run_matrix.apply_snapshot(
            MatrixSnapshot(run_id=RunId.new(), phases_in_order=phases, rows=rows)
        )

        now = datetime.now(tz=UTC)
        self._main_window.stats_strip.apply_snapshot(
            StatsSnapshot(
                run_status=RunStatus.CREATED,
                videos_total=len(videos),
                videos_completed=0,
                phases_total=0,
                phases_completed=0,
                cost_usd_so_far=0.0,
                cost_ceiling_usd=project.settings.cost_ceiling_usd,
                started_at=now,
                finished_at=now,
                elapsed_seconds=0.0,
            )
        )

    def _reset_views(self) -> None:
        """Vide la matrice et la bande de stats (fallback si pas de vidéos)."""
        from fahmi2.domain.ids import RunId  # noqa: PLC0415
        from fahmi2.ui.viewmodels.run_matrix import MatrixSnapshot  # noqa: PLC0415
        from fahmi2.ui.viewmodels.stats_strip import StatsSnapshot  # noqa: PLC0415

        empty_matrix = MatrixSnapshot(
            run_id=RunId.new(), phases_in_order=(), rows=()
        )
        self._main_window.run_matrix.apply_snapshot(empty_matrix)
        now = datetime.now(tz=UTC)
        empty_stats = StatsSnapshot(
            run_status=RunStatus.CREATED,
            videos_total=0,
            videos_completed=0,
            phases_total=0,
            phases_completed=0,
            cost_usd_so_far=0.0,
            cost_ceiling_usd=None,
            started_at=now,
            finished_at=now,
            elapsed_seconds=0.0,
        )
        self._main_window.stats_strip.apply_snapshot(empty_stats)

    # ---------------------------------------------------------------- run start

    def start_run(self) -> None:
        """Crée un nouveau Run et lance son exécution dans un QThread."""
        if self._current_project is None:
            QMessageBox.warning(
                self._main_window,
                "Aucun projet sélectionné",
                "Sélectionne un projet dans la sidebar avant de lancer.",
            )
            return
        if self._thread is not None:
            QMessageBox.warning(
                self._main_window,
                "Run déjà en cours",
                "Un run est déjà en cours pour ce projet.",
            )
            return
        if not self._validate_keys(self._current_project):
            return

        try:
            orchestrator = self._build_orchestrator()
            run = orchestrator.create_run(self._current_project)
        except Fahmi2Error as exc:
            QMessageBox.critical(
                self._main_window,
                "Création du run impossible",
                f"{exc.code}\n\n{exc.user_message}",
            )
            return
        except Exception as exc:  # noqa: BLE001 — affichage UX puis stop
            QMessageBox.critical(
                self._main_window,
                "Erreur inattendue",
                f"{type(exc).__name__} : {exc}",
            )
            return

        self._current_run = run
        self._active_worker_project_id = self._current_project.id
        self._current_pause_token = PauseToken()
        event_bus = self._build_event_bus()

        try:
            stt_provider = self._build_stt_provider(self._current_project)
            llm_provider = self._build_llm_provider(self._current_project)
        except Fahmi2Error as exc:
            QMessageBox.critical(
                self._main_window,
                "Configuration des providers invalide",
                f"{exc.code}\n\n{exc.user_message}",
            )
            return

        ctx = PhaseContext(
            run=run,
            settings=run.settings_snapshot,
            workspace=run.settings_snapshot.workspace_folder,
            output_dir=run.settings_snapshot.workspace_folder / "output",
            state=self._state,
            artifacts=FsArtifactStore(),
            stt_provider=stt_provider,
            llm_provider=llm_provider,
            ffmpeg=build_ffmpeg_from_runtime(),
            retriever=PassthroughRetriever(),
            prompts=PromptLoader(override_dir=self._app_paths.prompts_override_dir),
            pause_token=self._current_pause_token,
            event_bus=event_bus,
        )

        self._main_window.header_bar.set_running()
        self._refresh_views(run)

        worker = _RunWorker(orchestrator=orchestrator, run=run, ctx=ctx)
        thread = QThread(self)
        worker.moveToThread(thread)
        thread.started.connect(worker.run_pipeline)
        worker.finished.connect(self._on_worker_finished)
        worker.failed.connect(self._on_worker_failed)
        worker.finished.connect(thread.quit)
        worker.failed.connect(thread.quit)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        self._worker = worker
        self._thread = thread
        thread.start()

    # ---------------------------------------------------------- pause / cancel

    def pause_run(self) -> None:
        """Slot : demande la pause du run en cours."""
        if self._current_pause_token is None:
            return
        self._current_pause_token.request_pause()
        self._sync_header_for_selected_project()

    def resume_run(self) -> None:
        """Slot : reprend le run en pause."""
        if self._current_pause_token is None:
            return
        self._current_pause_token.resume()
        self._sync_header_for_selected_project()

    def cancel_run(self) -> None:
        """Slot : demande l'annulation du run en cours, après confirmation.

        Demande confirmation à l'utilisateur, signale le PauseToken pour
        sortir proprement de la boucle de pipeline, et planifie le
        nettoyage post-annulation (suppression des livrables générés et
        remise à zéro du cockpit) une fois que le worker confirme la fin.
        """
        if self._current_pause_token is None:
            return
        reply = QMessageBox.question(
            self._main_window,
            "Annuler le run ?",
            (
                "Annuler le run en cours ?\n\n"
                "Le pipeline s'arrêtera à la prochaine frontière sûre. "
                "Le dossier de sortie sera ensuite **supprimé** "
                "(livrables Markdown générés jusqu'ici) et le cockpit "
                "réinitialisé.\n\n"
                "Cette action ne supprime pas les fichiers vidéo "
                "originaux ni les artefacts intermédiaires de "
                "« workspace »."
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._cleanup_after_cancel_requested = True
        self._current_pause_token.request_cancel()

    def open_output_folder(self) -> None:
        """Slot : ouvre le dossier de sortie du projet sélectionné.

        Sur Windows, déléguer à ``explorer.exe`` (commande native, non
        bloquante). Sur les autres plateformes, on s'appuie sur
        ``QDesktopServices.openUrl`` qui gère ``file://`` URIs.
        """
        output_dir = self._current_output_dir()
        if output_dir is None or not output_dir.exists():
            QMessageBox.information(
                self._main_window,
                "Aucun dossier de sortie",
                "Le dossier de sortie n'existe pas encore. Lancez d'abord "
                "un run pour ce projet.",
            )
            return
        _open_in_file_explorer(output_dir)

    def estimate_cost(self) -> None:
        """Slot : pré-estime le coût total du Run et affiche un rapport.

        Scanne le dossier d'entrée du projet, lit la durée de chaque vidéo
        via ``ffprobe`` et délègue le calcul à :py:class:`CostEstimator`.
        Le probe est exécuté sur le thread UI avec un curseur d'attente :
        pour 10 à 50 vidéos l'opération reste sous la dizaine de secondes.
        """
        if self._current_project is None:
            QMessageBox.warning(
                self._main_window,
                "Aucun projet sélectionné",
                "Sélectionne un projet dans la sidebar avant d'estimer.",
            )
            return
        settings = self._current_project.settings
        try:
            videos = scan_input_folder(settings.input_folder)
        except Fahmi2Error as exc:
            QMessageBox.warning(
                self._main_window,
                "Dossier d'entrée invalide",
                f"{exc.code}\n\n{exc.user_message}",
            )
            return

        ffmpeg = build_ffmpeg_from_runtime()
        QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
        try:
            durations = [
                ffmpeg.probe_duration_seconds(v.source_path) for v in videos
            ]
        finally:
            QApplication.restoreOverrideCursor()

        translation_langs = sum(
            1 for lang in settings.output_languages if lang is not settings.source_language
        )
        estimation = CostEstimator().estimate(
            videos_durations_seconds=durations,
            stt_provider=settings.stt_provider,
            llm_model=settings.llm_model,
            active_target_languages_count=len(settings.output_languages),
            translation_languages_count=translation_langs,
            phases_config=settings.phases_config,
        )
        _show_cost_estimation_dialog(
            self._main_window,
            project_name=settings.name,
            n_videos=len(videos),
            estimation=estimation,
            cost_ceiling_usd=settings.cost_ceiling_usd,
        )

    def _current_output_dir(self) -> Path | None:
        """Retourne le ``output_dir`` du projet sélectionné, ou ``None``.

        Returns:
            Le chemin du dossier de sortie tel que défini par
            ``settings.workspace_folder / output``, ou ``None`` si aucun
            projet n'est sélectionné.
        """
        if self._current_project is None:
            return None
        return self._current_project.settings.workspace_folder / "output"

    # ---------------------------------------------------------- end-of-run

    def _on_worker_finished(self, final_status: object) -> None:
        """Slot : run terminé normalement (statut final transmis).

        Ne met à jour le header et le dashboard que si l'utilisateur est
        toujours sur le projet du worker (sinon on respecterait pas sa
        navigation). Les artefacts (cleanup post-cancel, OUTPUT_AVAILABLE)
        sont en revanche traités systématiquement côté disque.
        """
        del final_status
        worker_was_on_current_project = (
            self._active_worker_project_id is not None
            and self._current_project is not None
            and self._active_worker_project_id == self._current_project.id
        )

        if worker_was_on_current_project:
            self._main_window.header_bar.set_finished()
            if self._current_run is not None:
                reloaded = self._project_service.get_run(self._current_run.id)
                if reloaded is not None:
                    self._current_run = reloaded
                    self._refresh_views(reloaded)

        # Annulation utilisateur : nettoyer les livrables et remettre le
        # cockpit à zéro maintenant que le worker a fini proprement.
        if self._cleanup_after_cancel_requested:
            self._cleanup_after_cancel_requested = False
            self._purge_output_dir_after_cancel()
            if worker_was_on_current_project:
                self._reset_views()
                self._main_window.header_bar.set_idle()
                self._main_window.header_bar.set_open_output_enabled(False)
            self._cleanup_thread()
            return

        # Active le bouton « Ouvrir le dossier de sortie » + ajoute une ligne
        # de log avec le chemin pour que l'utilisateur sache où aller.
        output_dir = (
            self._current_output_dir() if worker_was_on_current_project else None
        )
        if output_dir is not None and output_dir.exists():
            self._main_window.header_bar.set_open_output_enabled(True)
            self._main_window.logs_dock.append_event(
                LogEvent(
                    timestamp=datetime.now(tz=UTC),
                    severity=Severity.INFO,
                    code="OUTPUT_AVAILABLE",
                    message=f"Livrables disponibles dans : {output_dir}",
                )
            )
        self._cleanup_thread()

    def _purge_output_dir_after_cancel(self) -> None:
        """Supprime récursivement le dossier de sortie du projet courant.

        Idempotent : ne fait rien si le projet n'a pas de dossier de sortie
        ou si celui-ci n'existe pas. Toute erreur d'I/O est isolée et
        rapportée via un log warning, sans interrompre le reset du cockpit.
        """
        output_dir = self._current_output_dir()
        if output_dir is None or not output_dir.exists():
            return
        try:
            shutil.rmtree(output_dir)
        except OSError as exc:
            self._main_window.logs_dock.append_event(
                LogEvent(
                    timestamp=datetime.now(tz=UTC),
                    severity=Severity.WARNING,
                    code="CLEANUP_OUTPUT_FAILED",
                    message=(
                        f"Échec de la suppression du dossier de sortie "
                        f"après annulation : {output_dir} ({exc})"
                    ),
                )
            )
            return
        self._main_window.logs_dock.append_event(
            LogEvent(
                timestamp=datetime.now(tz=UTC),
                severity=Severity.INFO,
                code="OUTPUT_CLEANED",
                message=(
                    f"Run annulé — dossier de sortie supprimé : {output_dir}"
                ),
            )
        )

    def _on_worker_failed(self, error_message: str) -> None:
        """Slot : run terminé sur exception non gérée."""
        QMessageBox.critical(
            self._main_window,
            "Le run s'est terminé sur une erreur inattendue",
            error_message,
        )
        self._main_window.header_bar.set_finished()
        # Si l'utilisateur avait demandé une annulation, on ne purge pas
        # dans cette branche (le pipeline a planté) — on laisse l'artefact
        # tel quel pour diagnostic.
        self._cleanup_after_cancel_requested = False
        self._cleanup_thread()

    def _cleanup_thread(self) -> None:
        """Réinitialise les références au worker/thread après fin."""
        self._worker = None
        self._thread = None
        self._current_pause_token = None
        self._active_worker_project_id = None

    # ---------------------------------------------------------- providers DI

    def _build_orchestrator(self) -> RunOrchestrator:
        """Construit un ``RunOrchestrator`` configuré pour le run en cours.

        Returns:
            Un orchestrateur prêt à l'usage.
        """
        engine = PipelineEngine(
            registry=self._registry,
            retry_policy=RetryPolicy(),
        )
        return RunOrchestrator(
            state=self._state,
            engine=engine,
            project_service=self._project_service,
        )

    def _build_stt_provider(self, project: Project) -> STTProvider:
        """Instancie le ``STTProvider`` selon les settings du projet.

        Args:
            project: Projet en cours.

        Returns:
            Le provider STT.

        Raises:
            Fahmi2Error: Si une clé API requise est manquante.
        """
        from fahmi2.core.errors.exceptions import ConfigError  # noqa: PLC0415

        if project.settings.stt_provider is SttProvider.OPENAI_CLOUD:
            api_key = self._secrets_service.get_openai_api_key()
            if not api_key:
                raise ConfigError(
                    code="CONFIG.MISSING_OPENAI_KEY",
                    user_message=(
                        "Clé OpenAI manquante. Édition → Paramètres globaux."
                    ),
                    severity=Severity.ERROR,
                )
            return OpenAIWhisperAdapter(api_key=api_key)
        # Mode local
        return FasterWhisperAdapter(model_cache_dir=self._app_paths.models_dir)

    def _build_llm_provider(self, project: Project) -> LLMProvider:
        """Instancie le ``LLMProvider`` (DeepSeek) avec la clé stockée.

        Args:
            project: Projet en cours.

        Returns:
            Le provider LLM.

        Raises:
            Fahmi2Error: Si la clé DeepSeek est manquante.
        """
        del project
        from fahmi2.core.errors.exceptions import ConfigError  # noqa: PLC0415

        api_key = self._secrets_service.get_deepseek_api_key()
        if not api_key:
            raise ConfigError(
                code="CONFIG.MISSING_DEEPSEEK_KEY",
                user_message="Clé DeepSeek manquante. Édition → Paramètres globaux.",
                severity=Severity.ERROR,
            )
        return DeepSeekAdapter(api_key=api_key)

    def _validate_keys(self, project: Project) -> bool:
        """Vérifie la présence des clés requises et affiche une erreur sinon.

        Args:
            project: Projet en cours.

        Returns:
            ``True`` si toutes les clés requises sont présentes.
        """
        if not self._secrets_service.has_deepseek_key():
            QMessageBox.critical(
                self._main_window,
                "Clé DeepSeek manquante",
                "Renseigne la clé DeepSeek dans "
                "« Édition → Paramètres globaux ».",
            )
            return False
        needs_openai = project.settings.stt_provider is SttProvider.OPENAI_CLOUD
        if needs_openai and not self._secrets_service.has_openai_key():
            QMessageBox.critical(
                self._main_window,
                "Clé OpenAI manquante",
                "Le provider STT cloud nécessite une clé OpenAI. "
                "Renseigne-la dans « Édition → Paramètres globaux ».",
            )
            return False
        return True

    # ------------------------------------------------------------- event bus

    def _build_event_bus(self) -> QtEventBus:
        """Construit un ``QtEventBus`` et branche les mises à jour UI.

        Returns:
            Le bus instancié.
        """
        bus = QtEventBus(self)
        bus.event_emitted.connect(self._on_pipeline_event)
        return bus

    def _on_pipeline_event(self, event: object) -> None:
        """Slot : reçoit chaque ``PipelineEvent`` côté UI thread.

        Les logs sont **toujours** ajoutés (utiles même si l'utilisateur
        regarde un autre projet — il garde la trace de ce qui se passe).
        En revanche le rafraîchissement matrice / stats ne se déclenche
        que si le projet actuellement affiché est bien celui du worker
        actif : sinon on écraserait le dashboard d'un autre projet avec
        les données d'un Run qui ne le concerne pas.
        """
        pipeline_event = cast("PipelineEvent", event)
        self._main_window.logs_dock.append_event(_to_log_event(pipeline_event))
        if not isinstance(pipeline_event, PhaseFinished | RunFinished):
            return
        if self._current_run is None:
            return
        if (
            self._current_project is None
            or self._active_worker_project_id is None
            or self._current_project.id != self._active_worker_project_id
        ):
            return
        reloaded = self._project_service.get_run(self._current_run.id)
        if reloaded is not None:
            self._current_run = reloaded
            self._refresh_views(reloaded)

    # ----------------------------------------------------------- view refresh

    def _refresh_views(self, run: Run) -> None:
        """Met à jour matrice + stats strip à partir d'un Run.

        Args:
            run: Run à afficher.
        """
        matrix_vm = RunMatrixViewModel(state=self._state, registry=self._registry)
        stats_vm = StatsStripViewModel(state=self._state, registry=self._registry)
        self._main_window.run_matrix.apply_snapshot(matrix_vm.snapshot(run))
        self._main_window.stats_strip.apply_snapshot(stats_vm.snapshot(run))


def _to_log_event(event: PipelineEvent) -> LogEvent:
    """Convertit un ``PipelineEvent`` en ``LogEvent`` pour le LogsDock.

    Args:
        event: Événement du pipeline.

    Returns:
        Un ``LogEvent`` lisible dans le panneau de logs.
    """
    if isinstance(event, RunStarted):
        return LogEvent(
            timestamp=event.timestamp,
            severity=Severity.INFO,
            code="RUN_STARTED",
            message=f"Run {event.run_id.value[:8]}… démarré",
            run_id=event.run_id.value,
        )
    if isinstance(event, RunFinished):
        return LogEvent(
            timestamp=event.timestamp,
            severity=(
                Severity.INFO
                if event.final_status is RunStatus.COMPLETED
                else Severity.WARNING
            ),
            code="RUN_FINISHED",
            message=f"Run terminé : {event.final_status.value}",
            run_id=event.run_id.value,
        )
    if isinstance(event, PhaseStarted):
        return LogEvent(
            timestamp=event.timestamp,
            severity=Severity.INFO,
            code="PHASE_STARTED",
            message=(
                f"{event.phase_id.value}"
                + (f" vidéo {event.video_id.value[:8]}…" if event.video_id else "")
            ),
            run_id=event.run_id.value,
            phase_id=str(event.phase_id),
            video_id=event.video_id.value if event.video_id else None,
        )
    if isinstance(event, PhaseFinished):
        return LogEvent(
            timestamp=event.timestamp,
            severity=_severity_for_phase_finished(event),
            code="PHASE_FINISHED",
            message=(
                f"{event.phase_id.value} → {event.final_status.value} "
                f"(coût ${event.cost_usd:.4f})"
            ),
            run_id=event.run_id.value,
            phase_id=str(event.phase_id),
            video_id=event.video_id.value if event.video_id else None,
            extra={"cost_usd": event.cost_usd},
        )
    if isinstance(event, RetryAttempt):
        return LogEvent(
            timestamp=event.timestamp,
            severity=Severity.WARNING,
            code="RETRY_ATTEMPT",
            message=(
                f"{event.phase_id.value} retry #{event.attempt} "
                f"dans {event.delay_seconds:.1f}s ({event.error.code})"
            ),
            run_id=event.run_id.value,
            phase_id=str(event.phase_id),
            video_id=event.video_id.value if event.video_id else None,
            extra={"attempt": event.attempt},
        )
    # Fallback (n'arrive pas en pratique)
    return LogEvent(
        timestamp=datetime.now(tz=UTC),
        severity=Severity.INFO,
        code="UNKNOWN_EVENT",
        message=str(event),
    )


def _severity_for_phase_finished(event: PhaseFinished) -> Severity:
    """Détermine la sévérité d'un événement ``PhaseFinished``.

    Args:
        event: Événement.

    Returns:
        ``Severity.ERROR`` si la phase a échoué, sinon ``Severity.INFO``.
    """
    from fahmi2.domain.enums import PhaseStatus  # noqa: PLC0415

    if event.final_status is PhaseStatus.FAILED:
        return Severity.ERROR
    return Severity.INFO


def _open_in_file_explorer(path: Path) -> None:
    """Ouvre ``path`` dans l'explorateur de fichiers natif.

    Sur Windows, utilise ``explorer.exe`` qui est non bloquant. Sur les
    autres plateformes, fallback sur ``QDesktopServices.openUrl(file://)``.

    Args:
        path: Chemin du dossier à ouvrir.
    """
    if sys.platform == "win32":
        explorer = shutil.which("explorer.exe") or "explorer.exe"
        subprocess.Popen(  # noqa: S603
            [explorer, str(path)], close_fds=True
        )
        return
    QDesktopServices.openUrl(  # type: ignore[unreachable]
        QUrl.fromLocalFile(str(path))
    )


def _format_duration_label(total_seconds: float) -> str:
    """Met en forme une durée en ``H h M min`` (ou ``M min S s`` si < 1 h).

    Args:
        total_seconds: Durée totale en secondes.

    Returns:
        Libellé lisible pour le dialogue d'estimation.
    """
    total = int(max(0.0, total_seconds))
    hours, remainder = divmod(total, 3600)
    minutes, secs = divmod(remainder, 60)
    if hours:
        return f"{hours} h {minutes:02d} min"
    return f"{minutes} min {secs:02d} s"


def _show_cost_estimation_dialog(
    parent: MainWindow,
    *,
    project_name: str,
    n_videos: int,
    estimation: CostEstimation,
    cost_ceiling_usd: float | None,
) -> None:
    """Affiche un ``QMessageBox`` détaillant l'estimation de coût.

    Args:
        parent: Fenêtre parente.
        project_name: Nom du projet.
        n_videos: Nombre de vidéos détectées dans l'input.
        estimation: Résultat du ``CostEstimator``.
        cost_ceiling_usd: Plafond budget du projet, le cas échéant.
    """
    duration_label = _format_duration_label(estimation.total_audio_seconds)
    lines = [
        f"<b>Projet :</b> {project_name}",
        f"<b>Vidéos détectées :</b> {n_videos}",
        f"<b>Durée totale audio :</b> {duration_label}",
        "",
        f"<b>Coût STT :</b> ${estimation.stt_usd:.4f}",
        f"<b>Coût LLM :</b> ${estimation.llm_usd:.4f}",
        f"<b>Total estimé :</b> ${estimation.total_usd:.4f}",
    ]
    if cost_ceiling_usd is not None:
        margin = cost_ceiling_usd - estimation.total_usd
        if margin >= 0:
            lines.append(
                f"<b>Plafond :</b> ${cost_ceiling_usd:.2f} "
                f"<span style='color:#1a7f37;'>(marge ${margin:.2f})</span>"
            )
        else:
            lines.append(
                f"<b>Plafond :</b> ${cost_ceiling_usd:.2f} "
                f"<span style='color:#cf222e;'>(dépassement ${-margin:.2f})</span>"
            )
    body = (
        "<br>".join(lines)
        + "<br><br><i>Estimation indicative basée sur des heuristiques "
        "DeepSeek (≈ 150 mots/min, ≈ 1.3 tokens/mot, multiplicateurs "
        "empiriques par phase, et coût additionnel du mode thinking par "
        "phase selon le niveau de raisonnement choisi).</i>"
    )
    msg = QMessageBox(parent)
    msg.setWindowTitle("Estimation du coût")
    msg.setIcon(QMessageBox.Icon.Information)
    msg.setTextFormat(Qt.TextFormat.RichText)
    msg.setText(body)
    msg.exec()


__all__ = ["RunController", "build_default_registry", "build_ffmpeg_from_runtime"]


# Évite de polluer les imports inutilisés au top
_ = (ErrorInfo, Path)
