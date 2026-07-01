"""Façade ``SlideAnalyzer`` : frames (ffmpeg) → analyse vision → slides.

Compose ``SlideFrameExtractor`` et ``SlideVisionProvider`` : extraction des
frames représentatives, analyse vision **parallélisée** (``map_bounded``
borné par ``llm_workers``, ordre préservé, honore le ``PauseToken``), retry
par appel (``core/retry``), nettoyage best-effort des frames. Les coûts et
avertissements sont mémorisés **par source** (thread-safe) pour l'attribution
per-source de la phase 0.
"""

from __future__ import annotations

import shutil
import threading
from dataclasses import dataclass
from pathlib import Path

from fahmi2.core.concurrency import map_bounded
from fahmi2.core.concurrency.pause_token import PauseToken
from fahmi2.core.retry.classification import default_classify
from fahmi2.core.retry.policy import RetryPolicy
from fahmi2.core.retry.runner import with_retry
from fahmi2.domain.enums import Language
from fahmi2.infra.video.frame_extractor import SlideFrame, SlideFrameExtractor
from fahmi2.infra.vision.interface import (
    AnalyzedSlide,
    SlideAnalysis,
    SlideVisionProvider,
)

_FRAMES_SUBDIR = "frames"


@dataclass(frozen=True)
class SlideAnalysisReport:
    """Résultat de l'analyse des slides d'une vidéo.

    Attributes:
        slides: Slides analysées, horodatées, ordonnées temporellement.
        cost_usd: Coût vision total de cette vidéo (USD).
        dropped_groups: Slides ignorées par les plafonds (détection instable).
    """

    slides: tuple[AnalyzedSlide, ...]
    cost_usd: float
    dropped_groups: int


class SlideAnalyzer:
    """Analyse les slides d'une vidéo (extraction + vision parallélisée)."""

    def __init__(
        self,
        *,
        frame_extractor: SlideFrameExtractor,
        vision_provider: SlideVisionProvider,
        llm_workers: int,
        pause_token: PauseToken | None = None,
        retry_policy: RetryPolicy | None = None,
    ) -> None:
        """Construit la façade.

        Args:
            frame_extractor: Extracteur de frames de slides (ffmpeg).
            vision_provider: Fournisseur d'analyse vision.
            llm_workers: Concurrence maximale des appels vision (>= 1).
            pause_token: Jeton coopératif pause/annulation du run.
            retry_policy: Politique de retry des appels vision (défaut :
                ``RetryPolicy()``).
        """
        self._frame_extractor = frame_extractor
        self._vision = vision_provider
        self._llm_workers = max(1, llm_workers)
        self._pause_token = pause_token
        self._retry_policy = retry_policy or RetryPolicy()
        self._lock = threading.Lock()
        self._costs_by_source: dict[str, float] = {}
        self._dropped_by_source: dict[str, int] = {}

    def analyze(
        self,
        video_path: Path,
        source_id: str,
        *,
        workspace: Path,
        language: Language,
        duration_seconds: float,
    ) -> SlideAnalysisReport:
        """Extrait puis analyse les slides de ``video_path``.

        Args:
            video_path: Vidéo source.
            source_id: Identifiant de la source (nom du sous-dossier frames et
                clé d'attribution du coût).
            workspace: Dossier de travail du run.
            language: Langue de sortie de l'analyse (détectée par le STT).
            duration_seconds: Durée de la vidéo.

        Returns:
            Le ``SlideAnalysisReport`` (slides + coût + slides ignorées).

        Raises:
            FFmpegError: Échec de l'échantillonnage.
            VisionError: Échec d'analyse après épuisement des retries.
        """
        frames_dir = workspace / _FRAMES_SUBDIR / source_id
        try:
            extraction = self._frame_extractor.extract(
                video_path, frames_dir, duration_seconds=duration_seconds
            )

            def _analyze_one(frame: SlideFrame) -> SlideAnalysis:
                return with_retry(
                    lambda: self._vision.analyze_slide(
                        frame.image_path, language=language
                    ),
                    policy=self._retry_policy,
                    classify=default_classify,
                )

            analyses = map_bounded(
                _analyze_one,
                extraction.frames,
                max_workers=self._llm_workers,
                pause_token=self._pause_token,
            )
            slides = tuple(
                AnalyzedSlide(
                    start_seconds=frame.start_seconds,
                    end_seconds=frame.end_seconds,
                    content=analysis.content,
                )
                for frame, analysis in zip(extraction.frames, analyses, strict=True)
            )
            cost = sum(analysis.cost_usd for analysis in analyses)
            with self._lock:
                self._costs_by_source[source_id] = cost
                self._dropped_by_source[source_id] = extraction.dropped_groups
            return SlideAnalysisReport(
                slides=slides,
                cost_usd=cost,
                dropped_groups=extraction.dropped_groups,
            )
        finally:
            shutil.rmtree(frames_dir, ignore_errors=True)

    def consumed_cost_usd_for(self, source_id: str) -> float:
        """Coût vision consommé pour une source (0 si non analysée).

        Args:
            source_id: Identifiant de la source.

        Returns:
            Le coût USD de l'analyse de cette source.
        """
        with self._lock:
            return self._costs_by_source.get(source_id, 0.0)

    def dropped_groups_for(self, source_id: str) -> int:
        """Nombre de slides ignorées par les plafonds pour une source.

        Args:
            source_id: Identifiant de la source.

        Returns:
            Le nombre de groupes ignorés (0 si détection stable).
        """
        with self._lock:
            return self._dropped_by_source.get(source_id, 0)
