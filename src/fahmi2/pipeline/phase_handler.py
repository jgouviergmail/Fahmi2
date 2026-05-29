"""Interface ``PhaseHandler`` et ``PhaseContext`` (injection de dépendances).

Chaque phase du pipeline (0..7) est implémentée par une sous-classe de
``PhaseHandler``. Le ``PhaseContext`` regroupe toutes les dépendances injectées
(state SQLite, artifacts FS, providers STT/LLM, pause token, event bus,
workspace) pour limiter le couplage aux interfaces et faciliter les tests.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path

from fahmi2.core.concurrency.pause_token import PauseToken
from fahmi2.core.retrieval.interface import GlossaryRetriever
from fahmi2.domain.enums import PhaseId
from fahmi2.domain.generation import GenerationSettings
from fahmi2.domain.phase import PhaseExecution
from fahmi2.domain.run import Run
from fahmi2.domain.source import SourceExecution
from fahmi2.infra.audio.ffmpeg_extractor import FFmpegExtractor
from fahmi2.infra.ingestion.dispatcher import IngestionDispatcher
from fahmi2.infra.llm.interface import LLMProvider
from fahmi2.infra.prompts.loader import PromptLoader
from fahmi2.infra.storage.fs_artifacts import FsArtifactStore
from fahmi2.infra.storage.sqlite_state import SqliteState
from fahmi2.infra.stt.interface import STTProvider
from fahmi2.pipeline.event_bus import EventBus
from fahmi2.pipeline.events import PipelineEvent


@dataclass(frozen=True)
class PhaseContext:
    """Dépendances injectées à un ``PhaseHandler``.

    Attributes:
        run: Run en cours.
        settings: Snapshot des ``GenerationSettings`` du projet.
        workspace: Dossier de travail du run (artefacts intermédiaires).
        output_dir: Dossier des livrables finaux.
        state: Accès SQLite à l'état du pipeline.
        artifacts: Helper d'écriture atomique d'artefacts FS.
        stt_provider: Provider STT à utiliser pour la phase 0.
        llm_provider: Provider LLM utilisé par les phases 1..7.
        ffmpeg: Extracteur ``ffmpeg``.
        ingestion: Dispatcher d'ingestion (phase 0 : source → transcription).
        retriever: Retriever du glossaire pour les phases 3, 4, 5, 6, 7.
        prompts: Loader de templates de prompts (défauts bundlés + override).
        pause_token: Jeton coopératif pause/cancel.
        event_bus: Bus d'événements (peut être ``None`` pour les tests).
    """

    run: Run
    settings: GenerationSettings
    workspace: Path
    output_dir: Path
    state: SqliteState
    artifacts: FsArtifactStore
    stt_provider: STTProvider
    llm_provider: LLMProvider
    ffmpeg: FFmpegExtractor
    ingestion: IngestionDispatcher
    retriever: GlossaryRetriever
    prompts: PromptLoader
    pause_token: PauseToken
    event_bus: EventBus[PipelineEvent]


class PhaseHandler(ABC):
    """Base abstraite d'un handler de phase."""

    @property
    @abstractmethod
    def phase_id(self) -> PhaseId:
        """Identifiant de la phase implémentée."""

    @property
    @abstractmethod
    def is_per_source(self) -> bool:
        """Indique si la phase tourne par source (``True``) ou en batch (``False``)."""

    def max_parallel_workers(self, ctx: PhaseContext) -> int:
        """Nombre d'unités per-source à traiter en parallèle pour cette phase.

        Défaut : ``1`` (séquentiel). Les phases dont les unités per-source sont
        indépendantes et I/O-bound surchargent cette méthode pour autoriser un
        pool borné (cf. ``GenerationSettings.parallelism``). Ignoré pour les
        phases batch (``is_per_source`` faux).

        Args:
            ctx: Contexte d'exécution (accès aux réglages).

        Returns:
            Le nombre maximal de workers (>= 1).
        """
        del ctx
        return 1

    @abstractmethod
    def execute(
        self,
        ctx: PhaseContext,
        *,
        source: SourceExecution | None,
    ) -> PhaseExecution:
        """Exécute la phase pour le contexte donné.

        Args:
            ctx: Contexte d'exécution.
            source: Source ciblée (``None`` pour les phases batch).

        Returns:
            ``PhaseExecution`` finale avec ``status``, ``artifact_path``,
            ``cost_usd``, ``started_at``, ``finished_at``.

        Raises:
            Fahmi2Error: Toute exception levée doit être typée (sous-classe de
                ``Fahmi2Error``). Le moteur la capturera pour la retry policy.
        """
