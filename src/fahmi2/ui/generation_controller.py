"""``GenerationController`` — orchestration du lifecycle Run de l'onglet Génération.

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
from datetime import UTC, datetime
from pathlib import Path
from typing import cast

from PySide6.QtCore import QCoreApplication, QObject, Qt, QThread, Signal
from PySide6.QtGui import QCursor
from PySide6.QtWidgets import QApplication, QDialog, QMessageBox, QWidget

from fahmi2.app._cost_common import (
    TEXT_BYTES_PER_TOKEN,
    estimated_slide_count,
)
from fahmi2.app.cost_estimator import CostEstimation, CostEstimator, SourceWeight
from fahmi2.app.generation_export import export_generation_documents
from fahmi2.app.hardware_probe import HardwareInfo
from fahmi2.app.input_sources import build_input_sources
from fahmi2.app.project_service import ProjectService
from fahmi2.app.run_orchestrator import RunOrchestrator
from fahmi2.app.secrets_service import SecretsService
from fahmi2.core.concurrency.pause_token import PauseToken
from fahmi2.core.config.paths import AppPaths, resolve_ytdlp_binary_or_none
from fahmi2.core.errors.error_info import ErrorInfo
from fahmi2.core.errors.exceptions import Fahmi2Error
from fahmi2.core.errors.severity import Severity
from fahmi2.core.logging.event import LogEvent
from fahmi2.core.retrieval.interface import PassthroughRetriever
from fahmi2.core.retry.policy import RetryPolicy
from fahmi2.domain.enums import PhaseId, RunStatus, SourceKind, SttProvider
from fahmi2.domain.generation import (
    GENERATION_OUTPUT_SUBDIR,
    GENERATION_WORKSPACE_SUBDIR,
    GenerationSettings,
)
from fahmi2.domain.ids import ProjectId
from fahmi2.domain.project import Project
from fahmi2.domain.run import Run
from fahmi2.domain.source import SourceExecution
from fahmi2.infra.audio.cloud_audio_preparer import CloudAudioPreparer
from fahmi2.infra.audio.ffmpeg_extractor import FFmpegExtractor
from fahmi2.infra.ingestion.dispatcher import build_default_ingestion_dispatcher
from fahmi2.infra.ingestion.youtube_downloader import YoutubeDownloader, YtDlpDownloader
from fahmi2.infra.llm.deepseek_adapter import DeepSeekAdapter
from fahmi2.infra.llm.interface import LLMProvider
from fahmi2.infra.prompts.loader import PromptLoader
from fahmi2.infra.storage.fs_artifacts import FsArtifactStore
from fahmi2.infra.storage.sqlite_state import SqliteState
from fahmi2.infra.stt.faster_whisper_adapter import FasterWhisperAdapter
from fahmi2.infra.stt.interface import STTProvider
from fahmi2.infra.stt.openai_whisper_adapter import OpenAIWhisperAdapter
from fahmi2.infra.video.frame_extractor import SlideFrameExtractor
from fahmi2.infra.vision.openai_vision import OpenAIVisionAdapter
from fahmi2.infra.vision.slide_analyzer import SlideAnalyzer
from fahmi2.pipeline.engine import PipelineEngine
from fahmi2.pipeline.events import (
    PhaseFinished,
    PhaseStarted,
    PipelineEvent,
    RetryAttempt,
    RunFinished,
    RunStarted,
    SlideDetectionWarning,
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
from fahmi2.pipeline.phase_handler import PhaseContext
from fahmi2.pipeline.phase_registry import PhaseRegistry
from fahmi2.ui._export_ui import choose_export_format, run_document_export
from fahmi2.ui._file_explorer import open_in_file_explorer
from fahmi2.ui._fs import remove_feature_dir
from fahmi2.ui.dialogs.generation_settings_view import GenerationSettingsView
from fahmi2.ui.pedagogy_labels import export_labels
from fahmi2.ui.qt_event_bus import QtEventBus
from fahmi2.ui.viewmodels.run_matrix import RunMatrixViewModel
from fahmi2.ui.viewmodels.stats_strip import StatsStripViewModel
from fahmi2.ui.widgets.cost_matrix_view import EMPTY_COST_MATRIX, CostMatrixView
from fahmi2.ui.widgets.logs_dock import LogsDock
from fahmi2.ui.widgets.project_header_bar import ProjectHeaderBar
from fahmi2.ui.widgets.stats_strip import StatsStripWidget


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


def build_stt_provider(
    *,
    settings: GenerationSettings,
    openai_api_key: str | None,
    models_dir: Path,
) -> STTProvider:
    """Construit le ``STTProvider`` selon les réglages (testable sans Qt).

    Args:
        settings: Réglages de génération (porteur de ``stt_provider``).
        openai_api_key: Clé OpenAI (requise en mode cloud).
        models_dir: Dossier de cache des modèles (mode local).

    Returns:
        Le provider STT. En mode cloud, l'adapter est muni d'un
        ``CloudAudioPreparer`` (binaires ffmpeg bundlés) pour respecter la limite
        des 25 Mo d'OpenAI Whisper.

    Raises:
        ConfigError: Si la clé OpenAI manque en mode cloud.
    """
    from fahmi2.core.config.paths import (  # noqa: PLC0415 — éviter cycle
        resolve_ffmpeg_binary_or_none,
        resolve_ffprobe_binary_or_none,
    )
    from fahmi2.core.errors.exceptions import ConfigError  # noqa: PLC0415

    if settings.stt_provider is SttProvider.OPENAI_CLOUD:
        if not openai_api_key:
            raise ConfigError(
                code="CONFIG.MISSING_OPENAI_KEY",
                user_message="Clé OpenAI manquante. Édition → Paramètres globaux.",
                severity=Severity.ERROR,
            )
        return OpenAIWhisperAdapter(
            api_key=openai_api_key,
            preparer=CloudAudioPreparer(
                ffmpeg_binary=resolve_ffmpeg_binary_or_none(),
                ffprobe_binary=resolve_ffprobe_binary_or_none(),
            ),
            model=str(settings.stt_cloud_model),
        )
    return FasterWhisperAdapter(
        model_cache_dir=models_dir, model=str(settings.stt_local_model)
    )


def _source_weight(
    source: SourceExecution,
    ffmpeg: FFmpegExtractor,
    settings: GenerationSettings,
    youtube_downloader: YoutubeDownloader,
) -> SourceWeight:
    """Construit le poids de coût d'une source (durée audio ou tokens texte).

    Args:
        source: Source à peser.
        ffmpeg: Extracteur (sonde la durée des médias locaux).
        settings: Réglages (drapeau ``reformulate_documents``).
        youtube_downloader: Sonde la durée d'une source YouTube (réseau).

    Returns:
        Le ``SourceWeight`` correspondant. Pour un document, les tokens sont
        estimés depuis la taille du fichier (heuristique pré-run grossière ; le
        texte réel n'est extrait qu'en phase 0). Pour YouTube, la durée provient
        de la métadonnée yt-dlp (``0`` si le réseau est indisponible).
    """
    kind = source.source.kind
    if kind is SourceKind.YOUTUBE:
        duration = youtube_downloader.probe_duration(source.source.location)
        return SourceWeight(
            audio_seconds=duration,
            text_tokens=0.0,
            slide_count=_estimated_slide_count(source, duration, settings),
        )
    if kind is SourceKind.DOCUMENT:
        size_bytes = source.source.as_path.stat().st_size
        return SourceWeight(
            audio_seconds=0.0,
            text_tokens=size_bytes / TEXT_BYTES_PER_TOKEN,
            reformulated=settings.reformulate_documents,
        )
    duration = ffmpeg.probe_duration_seconds(source.source.as_path)
    return SourceWeight(
        audio_seconds=duration,
        text_tokens=0.0,
        slide_count=_estimated_slide_count(source, duration, settings),
    )


def _estimated_slide_count(
    source: SourceExecution, audio_seconds: float, settings: GenerationSettings
) -> float:
    """Nombre de slides estimé pour l'option « analyser les slides ».

    Args:
        source: Source évaluée.
        audio_seconds: Durée audio estimée de la source.
        settings: Réglages (liste des sources flaggées).

    Returns:
        Le nombre estimé (cf. ``_cost_common.estimated_slide_count``) si la
        source est flaggée, 0 sinon (audio et documents ne sont jamais
        flaggés côté UI).
    """
    if source.source.order_key() not in settings.slides_sources:
        return 0.0
    return estimated_slide_count(audio_seconds)


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


class GenerationController(QObject):
    """Orchestre le lifecycle d'un Run depuis l'onglet Génération."""

    #: Émis quand le statut du run change (démarrage / fin / échec / réinit.),
    #: pour rafraîchir les icônes de la sidebar.
    run_state_changed = Signal()

    def __init__(
        self,
        *,
        header_bar: ProjectHeaderBar,
        stats_strip: StatsStripWidget,
        run_matrix: CostMatrixView,
        logs_dock: LogsDock,
        window: QWidget,
        project_service: ProjectService,
        secrets_service: SecretsService,
        hardware: HardwareInfo,
        state: SqliteState,
        app_paths: AppPaths,
    ) -> None:
        """Construit le contrôleur et branche les signaux du cockpit Génération.

        Args:
            header_bar: Barre de titre + actions du cockpit.
            stats_strip: Bande de statistiques.
            run_matrix: Matrice sources × phases.
            logs_dock: Dock de logs partagé (alimenté par cet onglet quand actif).
            window: Fenêtre parente, utilisée comme parent des dialogues modaux.
            project_service: Service projets.
            secrets_service: Service secrets.
            hardware: Info matérielle (pour valider STT local).
            state: Stockage SQLite.
            app_paths: Chemins applicatifs (pour cache modèles).
        """
        super().__init__(window)
        self._header_bar = header_bar
        self._stats_strip = stats_strip
        self._run_matrix = run_matrix
        self._logs_dock = logs_dock
        self._window = window
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

        # Branchements UI (la sélection de projet est dispatchée par MainWindow
        # vers ``on_project_selected``).
        self._header_bar.start_requested.connect(self.start_run)
        self._header_bar.pause_requested.connect(self.pause_run)
        self._header_bar.resume_requested.connect(self.resume_run)
        self._header_bar.cancel_requested.connect(self.cancel_run)
        self._header_bar.open_output_requested.connect(self.open_output_folder)
        self._header_bar.estimate_cost_requested.connect(self.estimate_cost)
        self._header_bar.settings_requested.connect(self.open_generation_settings)
        self._header_bar.reset_requested.connect(self.reset_generation)
        self._header_bar.export_requested.connect(self.export_documents)

    # ------------------------------------------------------------------ project

    def on_project_selected(self, project_id: ProjectId) -> None:
        """Met à jour l'état UI à la sélection d'un projet (appelé par l'onglet).

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
        self._sync_header_for_selected_project()
        # Le bouton « Ouvrir le dossier de sortie » est actif si un dossier
        # output a déjà été produit (c'est-à-dire : au moins un run a tourné).
        output_dir = self._current_output_dir()
        self._header_bar.set_open_output_enabled(
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
        self._header_bar.set_idle()
        self._header_bar.set_open_output_enabled(False)
        self._reset_views()

    def _sync_header_for_selected_project(self) -> None:
        """Aligne l'état des boutons du header sur la situation réelle.

        Distingue le cas où le projet sélectionné a un worker actif
        (running/paused) du cas où on regarde simplement un projet
        terminé ou neuf (idle).
        """
        if self._current_project is None:
            self._header_bar.set_idle()
            return
        if (
            self._active_worker_project_id is not None
            and self._active_worker_project_id == self._current_project.id
        ):
            token = self._current_pause_token
            if token is not None and token.is_paused():
                self._header_bar.set_paused()
            else:
                self._header_bar.set_running()
            return
        self._header_bar.set_idle()

    def _refresh_views_with_last_run(self) -> None:
        """Rafraîchit matrice + stats avec le dernier run du projet courant.

        Si le projet ne contient aucun run, on affiche une **prévisualisation**
        : liste des sources détectées dans le dossier d'entrée, toutes phases
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

        Scanne le dossier d'entrée et construit un ``CostMatrixSnapshot`` de
        prévisualisation (une ligne par source détectée, toutes phases ``PENDING``)
        via ``RunMatrixViewModel.preview_cost_matrix``. Échec silencieux du scan →
        vues vides.

        Args:
            project: Projet courant.
        """
        from fahmi2.ui.viewmodels.stats_strip import StatsSnapshot  # noqa: PLC0415

        if project.generation is None:
            self._reset_views()
            return
        try:
            sources = build_input_sources(project.generation)
        except Fahmi2Error:
            self._reset_views()
            return

        matrix_vm = RunMatrixViewModel(state=self._state, registry=self._registry)
        self._run_matrix.apply_snapshot(matrix_vm.preview_cost_matrix(tuple(sources)))

        now = datetime.now(tz=UTC)
        self._stats_strip.apply_snapshot(
            StatsSnapshot(
                run_status=RunStatus.CREATED,
                sources_total=len(sources),
                sources_completed=0,
                phases_total=0,
                phases_completed=0,
                cost_usd_so_far=0.0,
                cost_ceiling_usd=project.generation.cost_ceiling_usd,
                started_at=now,
                finished_at=now,
                elapsed_seconds=0.0,
                languages=project.generation.output_languages,
            )
        )

    def _reset_views(self) -> None:
        """Vide la matrice et la bande de stats (fallback si pas de sources)."""
        from fahmi2.ui.viewmodels.stats_strip import StatsSnapshot  # noqa: PLC0415

        self._run_matrix.apply_snapshot(EMPTY_COST_MATRIX)
        now = datetime.now(tz=UTC)
        empty_stats = StatsSnapshot(
            run_status=RunStatus.CREATED,
            sources_total=0,
            sources_completed=0,
            phases_total=0,
            phases_completed=0,
            cost_usd_so_far=0.0,
            cost_ceiling_usd=None,
            started_at=now,
            finished_at=now,
            elapsed_seconds=0.0,
            languages=(),
        )
        self._stats_strip.apply_snapshot(empty_stats)

    # ---------------------------------------------------------------- run start

    def start_run(self) -> None:
        """Crée un nouveau Run et lance son exécution dans un QThread."""
        if self._current_project is None:
            QMessageBox.warning(
                self._window,
                QCoreApplication.translate(
                    "GenerationController", "Aucun projet sélectionné"
                ),
                QCoreApplication.translate(
                    "GenerationController",
                    "Sélectionne un projet dans la sidebar avant de lancer.",
                ),
            )
            return
        if self._thread is not None:
            QMessageBox.warning(
                self._window,
                QCoreApplication.translate(
                    "GenerationController", "Run déjà en cours"
                ),
                QCoreApplication.translate(
                    "GenerationController",
                    "Un run est déjà en cours pour ce projet.",
                ),
            )
            return
        if not self._validate_keys(self._current_project):
            return

        try:
            orchestrator = self._build_orchestrator()
            run, is_resumed = orchestrator.resume_or_create_run(
                self._current_project
            )
        except Fahmi2Error as exc:
            QMessageBox.critical(
                self._window,
                QCoreApplication.translate(
                    "GenerationController", "Création du run impossible"
                ),
                f"{exc.code}\n\n{exc.user_message}",
            )
            return
        except Exception as exc:  # noqa: BLE001 — affichage UX puis stop
            QMessageBox.critical(
                self._window,
                QCoreApplication.translate(
                    "GenerationController", "Erreur inattendue"
                ),
                f"{type(exc).__name__} : {exc}",
            )
            return

        if is_resumed:
            self._logs_dock.append_event(
                LogEvent(
                    timestamp=datetime.now(tz=UTC),
                    severity=Severity.INFO,
                    code="RUN_RESUMED",
                    message=(
                        f"Reprise du Run {run.id.value[:8]}… "
                        f"(statut précédent : {run.status.value}). Les phases "
                        "déjà terminées seront passées en SKIPPED."
                    ),
                    run_id=run.id.value,
                )
            )

        self._current_run = run
        self._active_worker_project_id = self._current_project.id
        self._current_pause_token = PauseToken()
        event_bus = self._build_event_bus()

        try:
            stt_provider = self._build_stt_provider(self._current_project)
            llm_provider = self._build_llm_provider(self._current_project)
        except Fahmi2Error as exc:
            QMessageBox.critical(
                self._window,
                QCoreApplication.translate(
                    "GenerationController", "Configuration des providers invalide"
                ),
                f"{exc.code}\n\n{exc.user_message}",
            )
            return

        assert self._current_project is not None
        gen_workspace = (
            self._current_project.workspace_folder / GENERATION_WORKSPACE_SUBDIR
        )
        ctx = PhaseContext(
            run=run,
            settings=run.settings_snapshot,
            workspace=gen_workspace,
            output_dir=gen_workspace / GENERATION_OUTPUT_SUBDIR,
            state=self._state,
            artifacts=FsArtifactStore(),
            stt_provider=stt_provider,
            llm_provider=llm_provider,
            ffmpeg=build_ffmpeg_from_runtime(),
            ingestion=build_default_ingestion_dispatcher(),
            retriever=PassthroughRetriever(),
            prompts=PromptLoader(override_dir=self._app_paths.prompts_override_dir),
            pause_token=self._current_pause_token,
            event_bus=event_bus,
            slide_analyzer=self._build_slide_analyzer(self._current_project),
        )

        self._header_bar.set_running()
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
        self.run_state_changed.emit()

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
            self._window,
            QCoreApplication.translate("GenerationController", "Annuler le run ?"),
            QCoreApplication.translate(
                "GenerationController",
                "Annuler le run en cours ?\n\n"
                "Le pipeline s'arrêtera à la prochaine frontière sûre. "
                "Le dossier de sortie sera ensuite **supprimé** "
                "(livrables Markdown générés jusqu'ici) et le cockpit "
                "réinitialisé.\n\n"
                "Cette action ne supprime pas les fichiers source "
                "originaux ni les artefacts intermédiaires de "
                "« workspace ».",
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._cleanup_after_cancel_requested = True
        self._current_pause_token.request_cancel()

    def export_documents(self) -> None:
        """Slot : exporte les livrables de génération (consolidé + glossaire).

        Propose les formats configurés (``GenerationSettings.export_formats``),
        puis écrit, dans le dossier choisi, un fichier par document et par langue
        au format retenu (Markdown / PDF / HTML).
        """
        project = self._current_project
        if project is None:
            QMessageBox.warning(
                self._window,
                QCoreApplication.translate(
                    "GenerationController", "Aucun projet sélectionné"
                ),
                QCoreApplication.translate(
                    "GenerationController",
                    "Sélectionne un projet dans la sidebar avant d'exporter.",
                ),
            )
            return
        if project.generation is None:
            QMessageBox.information(
                self._window,
                QCoreApplication.translate(
                    "GenerationController", "Génération non configurée"
                ),
                QCoreApplication.translate(
                    "GenerationController",
                    "Configurez d'abord la génération (⚙ Réglages).",
                ),
            )
            return
        labels = export_labels()
        fmt = choose_export_format(
            window=self._window,
            configured_formats=project.generation.export_formats,
            label_by_format=labels,
        )
        if fmt is None:
            return
        run_document_export(
            window=self._window,
            logs_dock=self._logs_dock,
            label=labels[fmt],
            exporter=lambda d: export_generation_documents(
                project, output_dir=d, fmt=fmt
            ),
        )

    def open_output_folder(self) -> None:
        """Slot : ouvre le dossier de sortie du projet sélectionné.

        Sur Windows, déléguer à ``explorer.exe`` (commande native, non
        bloquante). Sur les autres plateformes, on s'appuie sur
        ``QDesktopServices.openUrl`` qui gère ``file://`` URIs.
        """
        output_dir = self._current_output_dir()
        if output_dir is None or not output_dir.exists():
            QMessageBox.information(
                self._window,
                QCoreApplication.translate(
                    "GenerationController", "Aucun dossier de sortie"
                ),
                QCoreApplication.translate(
                    "GenerationController",
                    "Le dossier de sortie n'existe pas encore. "
                    "Lancez d'abord un run pour ce projet.",
                ),
            )
            return
        open_in_file_explorer(output_dir)

    def estimate_cost(self) -> None:
        """Slot : pré-estime le coût total du Run et affiche un rapport.

        Scanne le dossier d'entrée du projet, lit la durée de chaque source
        via ``ffprobe`` et délègue le calcul à :py:class:`CostEstimator`.
        Le probe est exécuté sur le thread UI avec un curseur d'attente :
        pour 10 à 50 sources l'opération reste sous la dizaine de secondes.
        """
        if self._current_project is None:
            QMessageBox.warning(
                self._window,
                QCoreApplication.translate(
                    "GenerationController", "Aucun projet sélectionné"
                ),
                QCoreApplication.translate(
                    "GenerationController",
                    "Sélectionne un projet dans la sidebar avant d'estimer.",
                ),
            )
            return
        if self._current_project.generation is None:
            QMessageBox.information(
                self._window,
                QCoreApplication.translate(
                    "GenerationController", "Génération non configurée"
                ),
                QCoreApplication.translate(
                    "GenerationController",
                    "Configurez d'abord les réglages de génération de ce projet.",
                ),
            )
            return
        settings = self._current_project.generation
        try:
            sources = build_input_sources(settings)
        except Fahmi2Error as exc:
            QMessageBox.warning(
                self._window,
                QCoreApplication.translate(
                    "GenerationController", "Dossier d'entrée invalide"
                ),
                f"{exc.code}\n\n{exc.user_message}",
            )
            return

        ffmpeg = build_ffmpeg_from_runtime()
        youtube_downloader = YtDlpDownloader(
            ytdlp_binary=resolve_ytdlp_binary_or_none()
        )
        QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
        try:
            weights = [
                _source_weight(s, ffmpeg, settings, youtube_downloader)
                for s in sources
            ]
        finally:
            QApplication.restoreOverrideCursor()

        translation_langs = sum(
            1 for lang in settings.output_languages if lang is not settings.source_language
        )
        estimation = CostEstimator().estimate(
            source_weights=weights,
            stt_provider=settings.stt_provider,
            llm_model=settings.llm_model,
            stt_cloud_model=settings.stt_cloud_model,
            active_target_languages_count=len(settings.output_languages),
            translation_languages_count=translation_langs,
            phases_config=settings.phases_config,
            consolidation_mode=settings.consolidation_mode,
            vision_model=settings.vision_model,
        )
        _show_cost_estimation_dialog(
            self._window,
            project_name=self._current_project.name,
            n_sources=len(sources),
            estimation=estimation,
            cost_ceiling_usd=settings.cost_ceiling_usd,
        )

    def open_generation_settings(self) -> None:
        """Ouvre la vue de réglages de génération et persiste le résultat.

        Si aucun projet n'est sélectionné, affiche un avertissement. Sinon ouvre
        ``GenerationSettingsView`` (pré-rempli si déjà configuré), persiste le
        ``GenerationSettings`` mis à jour sur le projet et rafraîchit le cockpit.
        """
        if self._current_project is None:
            QMessageBox.warning(
                self._window,
                QCoreApplication.translate(
                    "GenerationController", "Aucun projet sélectionné"
                ),
                QCoreApplication.translate(
                    "GenerationController",
                    "Sélectionne un projet dans la sidebar avant de configurer la "
                    "génération.",
                ),
            )
            return
        project = self._current_project
        dialog = GenerationSettingsView(
            self._hardware, parent=self._window, initial=project.generation
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        generation = dialog.get_generation_settings()
        if generation is None:
            return
        self._project_service.update_project(project.with_generation(generation))
        self.on_project_selected(project.id)

    def _current_output_dir(self) -> Path | None:
        """Retourne le ``output_dir`` du projet sélectionné, ou ``None``.

        Returns:
            Le chemin du dossier de sortie tel que défini par
            ``settings.workspace_folder / output``, ou ``None`` si aucun
            projet n'est sélectionné.
        """
        if self._current_project is None:
            return None
        return (
            self._current_project.workspace_folder
            / GENERATION_WORKSPACE_SUBDIR
            / GENERATION_OUTPUT_SUBDIR
        )

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
            self._header_bar.set_finished()
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
                self._header_bar.set_idle()
                self._header_bar.set_open_output_enabled(False)
            self._cleanup_thread()
            return

        # Active le bouton « Ouvrir le dossier de sortie » + ajoute une ligne
        # de log avec le chemin pour que l'utilisateur sache où aller.
        output_dir = (
            self._current_output_dir() if worker_was_on_current_project else None
        )
        if output_dir is not None and output_dir.exists():
            self._header_bar.set_open_output_enabled(True)
            self._logs_dock.append_event(
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
            self._logs_dock.append_event(
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
        self._logs_dock.append_event(
            LogEvent(
                timestamp=datetime.now(tz=UTC),
                severity=Severity.INFO,
                code="OUTPUT_CLEANED",
                message=(
                    f"Run annulé — dossier de sortie supprimé : {output_dir}"
                ),
            )
        )

    def reset_generation(self) -> None:
        """Slot : supprime tout ce qui a été généré (runs en base + disque).

        Demande confirmation, refuse pendant un run, puis efface l'historique des
        runs du projet et le dossier de travail ``generation/``. Réinitialise le
        cockpit et notifie la sidebar.
        """
        project = self._current_project
        if project is None:
            QMessageBox.warning(
                self._window,
                QCoreApplication.translate(
                    "GenerationController", "Aucun projet sélectionné"
                ),
                QCoreApplication.translate(
                    "GenerationController",
                    "Sélectionne un projet dans la sidebar avant de réinitialiser.",
                ),
            )
            return
        if self._thread is not None:
            QMessageBox.warning(
                self._window,
                QCoreApplication.translate("GenerationController", "Run en cours"),
                QCoreApplication.translate(
                    "GenerationController",
                    "Impossible de réinitialiser pendant un run. Annule-le d'abord.",
                ),
            )
            return
        reply = QMessageBox.question(
            self._window,
            QCoreApplication.translate(
                "GenerationController", "Réinitialiser la génération ?"
            ),
            QCoreApplication.translate(
                "GenerationController",
                "Réinitialiser la génération de « {name} » ?\n\n"
                "Tous les livrables produits (transcriptions, glossaire, documents) "
                "et l'historique des runs en base seront supprimés. Le dossier "
                "d'entrée n'est pas touché. Cette action est irréversible.",
            ).format(name=project.name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return
        self._state.delete_runs_for_project(project.id)
        remove_feature_dir(
            self._logs_dock,
            project.workspace_folder / GENERATION_WORKSPACE_SUBDIR,
            label="génération",
        )
        self._current_run = None
        self._reset_views()
        self._header_bar.set_idle()
        self._header_bar.set_open_output_enabled(False)
        self._logs_dock.append_event(
            LogEvent(
                timestamp=datetime.now(tz=UTC),
                severity=Severity.INFO,
                code="GENERATION_RESET",
                message=f"Génération réinitialisée pour « {project.name} ».",
            )
        )
        self.run_state_changed.emit()

    def _on_worker_failed(self, error_message: str) -> None:
        """Slot : run terminé sur exception non gérée.

        On logge le détail de l'erreur dans le panneau Logs (visible et
        archivé dans ``events.jsonl``) et on affiche aussi un dialogue
        critique pour que l'utilisateur soit notifié de manière non
        ambiguë.
        """
        self._logs_dock.append_event(
            LogEvent(
                timestamp=datetime.now(tz=UTC),
                severity=Severity.FATAL,
                code="WORKER_FAILED",
                message=(
                    "Le worker du pipeline s'est terminé sur une exception "
                    f"non gérée : {error_message}"
                ),
                extra={"raw_error": error_message},
            )
        )
        QMessageBox.critical(
            self._window,
            QCoreApplication.translate(
                "GenerationController", "Le run s'est terminé sur une erreur inattendue"
            ),
            error_message,
        )
        self._header_bar.set_finished()
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
        # Le run vient de se terminer (succès / échec / annulation) : rafraîchir
        # les icônes de statut de la sidebar.
        self.run_state_changed.emit()

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

        if project.generation is None:
            raise ConfigError(
                code="CONFIG.GENERATION_NOT_CONFIGURED",
                user_message="La génération n'est pas configurée pour ce projet.",
                severity=Severity.ERROR,
            )
        return build_stt_provider(
            settings=project.generation,
            openai_api_key=self._secrets_service.get_openai_api_key(),
            models_dir=self._app_paths.models_dir,
        )

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
                self._window,
                QCoreApplication.translate(
                    "GenerationController", "Clé DeepSeek manquante"
                ),
                QCoreApplication.translate(
                    "GenerationController",
                    "Renseigne la clé DeepSeek dans "
                    "« Édition → Paramètres globaux ».",
                ),
            )
            return False
        if project.generation is None:
            QMessageBox.critical(
                self._window,
                QCoreApplication.translate(
                    "GenerationController", "Génération non configurée"
                ),
                QCoreApplication.translate(
                    "GenerationController",
                    "Configurez d'abord les réglages de génération de ce projet.",
                ),
            )
            return False
        needs_openai = (
            project.generation.stt_provider is SttProvider.OPENAI_CLOUD
            or bool(project.generation.effective_slides_sources())
        )
        if needs_openai and not self._secrets_service.has_openai_key():
            QMessageBox.critical(
                self._window,
                QCoreApplication.translate(
                    "GenerationController", "Clé OpenAI manquante"
                ),
                QCoreApplication.translate(
                    "GenerationController",
                    "Le STT cloud et l'analyse des slides nécessitent une clé "
                    "OpenAI. Renseigne-la dans « Édition → Paramètres globaux ».",
                ),
            )
            return False
        return True

    def _build_slide_analyzer(self, project: Project) -> SlideAnalyzer | None:
        """Construit l'analyseur de slides si l'option est activée.

        Args:
            project: Projet en cours (settings génération non ``None``).

        Returns:
            La façade configurée, ou ``None`` si aucune source n'a l'option
            (ou si la clé OpenAI est absente — cas déjà bloqué par
            ``_validate_keys``).
        """
        from fahmi2.core.config.paths import (  # noqa: PLC0415 — éviter cycle
            resolve_ffmpeg_binary_or_none,
        )

        settings = project.generation
        if settings is None or not settings.effective_slides_sources():
            return None
        api_key = self._secrets_service.get_openai_api_key()
        if api_key is None:
            return None
        vision = OpenAIVisionAdapter(
            api_key=api_key,
            prompts=PromptLoader(override_dir=self._app_paths.prompts_override_dir),
            model=str(settings.vision_model),
        )
        return SlideAnalyzer(
            frame_extractor=SlideFrameExtractor(
                ffmpeg_binary=resolve_ffmpeg_binary_or_none()
            ),
            vision_provider=vision,
            llm_workers=settings.parallelism.llm_workers,
            pause_token=self._current_pause_token,
            delete_frames_after=settings.delete_frames_after_analysis,
        )

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
        self._logs_dock.append_event(_to_log_event(pipeline_event))
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
        self._run_matrix.apply_snapshot(matrix_vm.cost_matrix_snapshot(run))
        self._stats_strip.apply_snapshot(stats_vm.snapshot(run))


def _to_log_event(event: PipelineEvent) -> LogEvent:  # noqa: PLR0911
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
                + (f" source {event.source_id.value[:8]}…" if event.source_id else "")
            ),
            run_id=event.run_id.value,
            phase_id=str(event.phase_id),
            source_id=event.source_id.value if event.source_id else None,
        )
    if isinstance(event, PhaseFinished):
        base_message = (
            f"{event.phase_id.value} → {event.final_status.value} "
            f"(coût ${event.cost_usd:.4f})"
        )
        if event.error is not None:
            # Phase en échec : on annexe le détail au message lisible et on
            # remonte les technical_details + traceback dans ``extra`` pour
            # le fichier JSONL.
            base_message = (
                f"{base_message}\n"
                f"    └─ {event.error.code} : {event.error.user_message}"
            )
            tech = _format_technical_details(event.error.technical_details)
            if tech:
                base_message = f"{base_message}\n    └─ détails : {tech}"
            extra: dict[str, object] = {
                "cost_usd": event.cost_usd,
                "error_code": event.error.code,
                "error_user_message": event.error.user_message,
                "error_technical_details": dict(event.error.technical_details),
            }
            if event.error.traceback:
                extra["error_traceback"] = event.error.traceback
        else:
            extra = {"cost_usd": event.cost_usd}
        return LogEvent(
            timestamp=event.timestamp,
            severity=_severity_for_phase_finished(event),
            code="PHASE_FINISHED",
            message=base_message,
            run_id=event.run_id.value,
            phase_id=str(event.phase_id),
            source_id=event.source_id.value if event.source_id else None,
            extra=extra,
        )
    if isinstance(event, SlideDetectionWarning):
        return LogEvent(
            timestamp=event.timestamp,
            severity=Severity.WARNING,
            code="SLIDES_DETECTION_UNSTABLE",
            message=(
                f"Détection de slides instable pour la source "
                f"{event.source_id.value[:8]}… : {event.dropped_groups} "
                f"image(s) ignorée(s) par les plafonds (coût borné ; contenu "
                f"de slides potentiellement incomplet)."
            ),
            run_id=event.run_id.value,
            source_id=event.source_id.value,
            extra={"dropped_groups": event.dropped_groups},
        )
    if isinstance(event, RetryAttempt):
        return LogEvent(
            timestamp=event.timestamp,
            severity=Severity.WARNING,
            code="RETRY_ATTEMPT",
            message=(
                f"{event.phase_id.value} retry #{event.attempt} "
                f"dans {event.delay_seconds:.1f}s "
                f"({event.error.code} : {event.error.user_message})"
            ),
            run_id=event.run_id.value,
            phase_id=str(event.phase_id),
            source_id=event.source_id.value if event.source_id else None,
            extra={
                "attempt": event.attempt,
                "error_code": event.error.code,
                "error_user_message": event.error.user_message,
                "error_technical_details": dict(event.error.technical_details),
            },
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


_TECHNICAL_DETAIL_MAX_LEN = 200
_TECHNICAL_DETAIL_TRUNCATE_LEN = 197


def _format_technical_details(details: dict[str, object]) -> str:
    """Met en forme les ``technical_details`` d'un ``ErrorInfo`` pour les logs.

    Représentation compacte ``k1=v1 k2=v2`` ; les valeurs trop longues
    sont tronquées (le détail complet reste accessible dans le fichier
    JSONL via ``error_technical_details``).

    Args:
        details: Mapping des détails techniques.

    Returns:
        Chaîne compacte ou ``""`` si vide.
    """
    if not details:
        return ""
    parts: list[str] = []
    for key, value in details.items():
        text = str(value)
        if len(text) > _TECHNICAL_DETAIL_MAX_LEN:
            text = text[:_TECHNICAL_DETAIL_TRUNCATE_LEN] + "…"
        parts.append(f"{key}={text}")
    return " ".join(parts)


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


_PHASE_ESTIMATE_LABELS: dict[PhaseId, str] = {
    PhaseId.STT: "0 · STT",
    PhaseId.TERM_EXTRACTION: "1 · Extraction termes",
    PhaseId.GLOSSARY_RECONCILIATION: "2 · Réconciliation glossaire",
    PhaseId.REFORMULATION: "3 · Reformulation",
    PhaseId.STRUCTURATION: "4 · Structuration",
    PhaseId.CONSOLIDATION: "5 · Consolidation",
    PhaseId.TRANSLATION: "6 · Traduction",
    PhaseId.COHERENCE: "7 · Cohérence",
}


def _show_cost_estimation_dialog(
    parent: QWidget,
    *,
    project_name: str,
    n_sources: int,
    estimation: CostEstimation,
    cost_ceiling_usd: float | None,
) -> None:
    """Affiche le dialogue d'estimation (décomposition par phase + fourchette).

    Args:
        parent: Fenêtre parente.
        project_name: Nom du projet.
        n_sources: Nombre de sources détectées dans l'input.
        estimation: Résultat du ``CostEstimator``.
        cost_ceiling_usd: Plafond budget du projet, le cas échéant.
    """
    from fahmi2.ui.cost_estimate_dialog import show_cost_estimate  # noqa: PLC0415

    duration_label = _format_duration_label(estimation.total_audio_seconds)
    header = [
        f"<b>Projet :</b> {project_name}",
        f"<b>Sources détectées :</b> {n_sources}",
        f"<b>Durée totale audio :</b> {duration_label}",
    ]
    breakdown = [
        (_PHASE_ESTIMATE_LABELS.get(phase_id, phase_id.value), cost)
        for phase_id, cost in estimation.per_phase_usd.items()
    ]
    show_cost_estimate(
        parent,
        title="Estimation du coût",
        header_lines=header,
        breakdown=breakdown,
        total_usd=estimation.total_usd,
        low_usd=estimation.low_usd,
        high_usd=estimation.high_usd,
        cost_ceiling_usd=cost_ceiling_usd,
    )


__all__ = [
    "GenerationController",
    "build_default_registry",
    "build_ffmpeg_from_runtime",
]


# Évite de polluer les imports inutilisés au top
_ = (ErrorInfo, Path)
