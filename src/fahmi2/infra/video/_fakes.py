"""Doubles de test du sous-système vidéo (détection de slides)."""

from __future__ import annotations

from pathlib import Path

from PIL import Image

from fahmi2.infra.video.frame_extractor import (
    SlideExtractionResult,
    SlideFrame,
    SlideFrameExtractor,
)

_FAKE_FRAME_SIZE = (32, 32)
_FAKE_SLIDE_DURATION_SECONDS = 10.0


class FakeSlideFrameExtractor(SlideFrameExtractor):
    """Extracteur factice : écrit des frames synthétiques, sans appel ffmpeg.

    Produit ``slide_count`` slides contiguës de
    ``_FAKE_SLIDE_DURATION_SECONDS`` chacune, avec une image JPEG réelle par
    slide (utilisable par un provider vision fake ou réel).
    """

    def __init__(self, *, slide_count: int = 1, dropped_groups: int = 0) -> None:
        """Construit le fake.

        Args:
            slide_count: Nombre de slides simulées.
            dropped_groups: Valeur de ``dropped_groups`` du résultat (simule
                une détection instable plafonnée).
        """
        super().__init__(ffmpeg_binary="ffmpeg-inutilise")
        self._slide_count = slide_count
        self._dropped_groups = dropped_groups

    def extract(
        self, video_path: Path, frames_dir: Path, *, duration_seconds: float
    ) -> SlideExtractionResult:
        """Écrit ``slide_count`` frames synthétiques (cf. classe).

        Args:
            video_path: Ignoré.
            frames_dir: Dossier des frames (créé).
            duration_seconds: Ignoré (plages fixes déterministes).

        Returns:
            Le ``SlideExtractionResult`` simulé.
        """
        del video_path, duration_seconds
        frames_dir.mkdir(parents=True, exist_ok=True)
        frames: list[SlideFrame] = []
        for i in range(self._slide_count):
            path = frames_dir / f"{i + 1:06d}.jpg"
            Image.new("RGB", _FAKE_FRAME_SIZE, (i * 40 % 256, 0, 0)).save(path)
            frames.append(
                SlideFrame(
                    start_seconds=i * _FAKE_SLIDE_DURATION_SECONDS,
                    end_seconds=(i + 1) * _FAKE_SLIDE_DURATION_SECONDS,
                    image_path=path,
                )
            )
        return SlideExtractionResult(
            frames=tuple(frames), dropped_groups=self._dropped_groups
        )
