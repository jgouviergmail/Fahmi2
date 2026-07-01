"""Échantillonnage ffmpeg d'une vidéo en frames JPEG + détection des slides.

Une passe ``ffmpeg`` produit une frame réduite toutes les
``SAMPLE_INTERVAL_SECONDS`` ; les frames sont hachées par tuiles puis
regroupées en slides (cf. ``grouping``). L'appel ffmpeg est isolé dans
``_sample_frames`` (surchargeable en test).
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from PIL import Image

from fahmi2.core.errors.exceptions import FFmpegError
from fahmi2.core.errors.severity import Severity
from fahmi2.infra.audio._ffmpeg_common import (
    DEFAULT_FFMPEG_BINARY,
    FFMPEG_LOGLEVEL_ERROR,
)
from fahmi2.infra.video._constants import (
    FFMPEG_JPEG_QUALITY,
    MAX_FRAME_DIMENSION_PX,
    SAMPLE_INTERVAL_SECONDS,
)
from fahmi2.infra.video.grouping import FrameSample, group_slides
from fahmi2.infra.video.tiles import tile_dhashes

_FRAME_PATTERN = "%06d.jpg"
_FRAME_GLOB = "*.jpg"
#: Délai maximal de l'échantillonnage (s) — généreux pour les longues vidéos.
_SAMPLING_TIMEOUT_SECONDS = 1800.0


@dataclass(frozen=True)
class SlideFrame:
    """La frame représentative d'une slide, avec sa plage d'affichage.

    Attributes:
        start_seconds: Début d'affichage de la slide.
        end_seconds: Fin d'affichage.
        image_path: Frame JPEG représentative (état final de la slide).
    """

    start_seconds: float
    end_seconds: float
    image_path: Path


@dataclass(frozen=True)
class SlideExtractionResult:
    """Résultat de l'extraction des slides d'une vidéo.

    Attributes:
        frames: Slides détectées, ordonnées temporellement.
        dropped_groups: Slides ignorées par les plafonds (détection instable).
    """

    frames: tuple[SlideFrame, ...]
    dropped_groups: int


class SlideFrameExtractor:
    """Échantillonne une vidéo et en extrait les frames de slides."""

    def __init__(self, *, ffmpeg_binary: str | None = None) -> None:
        """Construit l'extracteur.

        Args:
            ffmpeg_binary: Chemin de ``ffmpeg`` (``None`` = depuis ``PATH``).
        """
        self._ffmpeg = ffmpeg_binary or DEFAULT_FFMPEG_BINARY

    def extract(
        self, video_path: Path, frames_dir: Path, *, duration_seconds: float
    ) -> SlideExtractionResult:
        """Extrait les slides de ``video_path``.

        Args:
            video_path: Vidéo source.
            frames_dir: Dossier de travail des frames (créé si absent ; le
                nettoyage relève de l'appelant, cf. ``SlideAnalyzer``).
            duration_seconds: Durée de la vidéo (bornage du dernier groupe et
                plafond de slides).

        Returns:
            Le ``SlideExtractionResult``.

        Raises:
            FFmpegError: Si l'échantillonnage ffmpeg échoue.
        """
        frames_dir.mkdir(parents=True, exist_ok=True)
        self._sample_frames(video_path, frames_dir)
        paths = sorted(frames_dir.glob(_FRAME_GLOB))
        if not paths:
            return SlideExtractionResult(frames=(), dropped_groups=0)
        samples: list[FrameSample] = []
        for index, path in enumerate(paths):
            with Image.open(path) as image:
                hashes = tile_dhashes(image)
            samples.append(
                FrameSample(
                    time_seconds=index * SAMPLE_INTERVAL_SECONDS,
                    tile_hashes=hashes,
                )
            )
        effective_duration = (
            duration_seconds
            if duration_seconds > 0
            else len(paths) * SAMPLE_INTERVAL_SECONDS
        )
        grouping = group_slides(samples, duration_seconds=effective_duration)
        frames = tuple(
            SlideFrame(
                start_seconds=group.start_seconds,
                end_seconds=group.end_seconds,
                image_path=paths[group.representative_index],
            )
            for group in grouping.groups
        )
        return SlideExtractionResult(
            frames=frames, dropped_groups=grouping.dropped_groups
        )

    def _sample_frames(self, video_path: Path, frames_dir: Path) -> None:
        """Écrit une frame JPEG réduite toutes les ``SAMPLE_INTERVAL_SECONDS``.

        Args:
            video_path: Vidéo source.
            frames_dir: Dossier de sortie (``%06d.jpg``).

        Raises:
            FFmpegError: ``FFMPEG.FRAME_EXTRACTION_FAILED`` en cas d'échec.
        """
        scale = f"scale='min({MAX_FRAME_DIMENSION_PX},iw)':-2"
        cmd = [
            self._ffmpeg,
            "-hide_banner",
            "-loglevel",
            FFMPEG_LOGLEVEL_ERROR,
            "-i",
            str(video_path),
            "-vf",
            f"fps=1/{SAMPLE_INTERVAL_SECONDS},{scale}",
            "-q:v",
            str(FFMPEG_JPEG_QUALITY),
            str(frames_dir / _FRAME_PATTERN),
        ]
        try:
            subprocess.run(  # noqa: S603
                cmd,
                check=True,
                capture_output=True,
                timeout=_SAMPLING_TIMEOUT_SECONDS,
            )
        except FileNotFoundError as exc:
            raise FFmpegError(
                code="FFMPEG.NOT_FOUND",
                user_message="ffmpeg est introuvable pour extraire les slides.",
                severity=Severity.FATAL,
                technical_details={"ffmpeg_binary": self._ffmpeg},
            ) from exc
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
            stderr = ""
            if isinstance(exc, subprocess.CalledProcessError) and exc.stderr:
                stderr = exc.stderr.decode("utf-8", errors="replace")
            raise FFmpegError(
                code="FFMPEG.FRAME_EXTRACTION_FAILED",
                user_message=(
                    "L'extraction des images de slides a échoué (vidéo "
                    "illisible ou sans piste vidéo)."
                ),
                severity=Severity.ERROR,
                technical_details={"video": str(video_path), "stderr": stderr},
            ) from exc
