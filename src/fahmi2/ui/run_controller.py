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

from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import QMessageBox

from fahmi2.app.hardware_probe import HardwareInfo
from fahmi2.app.project_service import ProjectService
from fahmi2.app.run_orchestrator import RunOrchestrator
from fahmi2.app.secrets_service import SecretsService
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

        self._current_project: Project | None = None
        self._current_run: Run | None = None
        self._current_pause_token: PauseToken | None = None
        self._worker: _RunWorker | None = None
        self._thread: QThread | None = None
        self._registry = build_default_registry()

        # Branchements UI ---------------------------------------------------
        self._main_window.projects_sidebar.set_on_project_selected(
            self._on_project_selected
        )
        self._main_window.header_bar.start_requested.connect(self.start_run)
        self._main_window.header_bar.pause_requested.connect(self.pause_run)
        self._main_window.header_bar.resume_requested.connect(self.resume_run)
        self._main_window.header_bar.cancel_requested.connect(self.cancel_run)

    # ------------------------------------------------------------------ project

    def _on_project_selected(self, project_id: ProjectId) -> None:
        """Slot : met à jour l'état UI à la sélection d'un projet."""
        project = self._project_service.get_project(project_id)
        if project is None:
            return
        self._current_project = project
        self._main_window.header_bar.set_title(project.settings.name)
        self._main_window.header_bar.set_idle()
        self._refresh_views_with_last_run()

    def _refresh_views_with_last_run(self) -> None:
        """Rafraîchit matrice + stats avec le dernier run du projet courant."""
        if self._current_project is None:
            return
        last_run = self._project_service.get_last_run(self._current_project.id)
        if last_run is None:
            return
        self._current_run = last_run
        self._refresh_views(last_run)

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
        self._main_window.header_bar.set_paused()

    def resume_run(self) -> None:
        """Slot : reprend le run en pause."""
        if self._current_pause_token is None:
            return
        self._current_pause_token.resume()
        self._main_window.header_bar.set_running()

    def cancel_run(self) -> None:
        """Slot : demande l'annulation du run en cours."""
        if self._current_pause_token is None:
            return
        self._current_pause_token.request_cancel()

    # ---------------------------------------------------------- end-of-run

    def _on_worker_finished(self, final_status: object) -> None:
        """Slot : run terminé normalement (statut final transmis)."""
        del final_status
        self._main_window.header_bar.set_finished()
        if self._current_run is not None:
            reloaded = self._project_service.get_run(self._current_run.id)
            if reloaded is not None:
                self._current_run = reloaded
                self._refresh_views(reloaded)
        self._cleanup_thread()

    def _on_worker_failed(self, error_message: str) -> None:
        """Slot : run terminé sur exception non gérée."""
        QMessageBox.critical(
            self._main_window,
            "Le run s'est terminé sur une erreur inattendue",
            error_message,
        )
        self._main_window.header_bar.set_finished()
        self._cleanup_thread()

    def _cleanup_thread(self) -> None:
        """Réinitialise les références au worker/thread après fin."""
        self._worker = None
        self._thread = None
        self._current_pause_token = None

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
        """Slot : reçoit chaque ``PipelineEvent`` côté UI thread."""
        pipeline_event = cast("PipelineEvent", event)
        self._main_window.logs_dock.append_event(_to_log_event(pipeline_event))
        if isinstance(pipeline_event, PhaseFinished | RunFinished):
            if self._current_run is not None:
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


__all__ = ["RunController", "build_default_registry", "build_ffmpeg_from_runtime"]


# Évite de polluer les imports inutilisés au top
_ = (ErrorInfo, Path)
