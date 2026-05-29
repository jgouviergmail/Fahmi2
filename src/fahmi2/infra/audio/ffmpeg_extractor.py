"""Extraction audio depuis des vidéos MP4 vers WAV 16 kHz mono via ``ffmpeg``.

Le binaire ``ffmpeg`` est attendu accessible via le ``PATH``. Pour la
distribution portable Windows, on bundlera plus tard le binaire dans le dossier
de l'application et on passera son chemin absolu via le constructeur.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from fahmi2.core.errors.exceptions import FFmpegError
from fahmi2.core.errors.severity import Severity
from fahmi2.infra.audio._ffmpeg_common import (
    DEFAULT_FFMPEG_BINARY,
    DEFAULT_FFPROBE_BINARY,
    FFMPEG_LOGLEVEL_ERROR,
)

_DEFAULT_SAMPLE_RATE_HZ = 16_000
_DEFAULT_CHANNELS = 1
_DEFAULT_AUDIO_CODEC = "pcm_s16le"


@dataclass(frozen=True)
class AudioInfo:
    """Métadonnées audio extraites.

    Attributes:
        sample_rate_hz: Fréquence d'échantillonnage de la sortie WAV.
        channels: Nombre de canaux (1 = mono).
        duration_seconds: Durée de l'audio en secondes.
    """

    sample_rate_hz: int
    channels: int
    duration_seconds: float


class FFmpegExtractor:
    """Extrait la piste audio d'un fichier vidéo vers un WAV 16 kHz mono."""

    def __init__(
        self,
        *,
        ffmpeg_binary: str | None = None,
        ffprobe_binary: str | None = None,
        sample_rate_hz: int = _DEFAULT_SAMPLE_RATE_HZ,
        channels: int = _DEFAULT_CHANNELS,
    ) -> None:
        """Construit l'extracteur.

        Args:
            ffmpeg_binary: Chemin de ``ffmpeg`` (``None`` = depuis ``PATH``).
            ffprobe_binary: Chemin de ``ffprobe`` (``None`` = depuis ``PATH``).
            sample_rate_hz: Fréquence d'échantillonnage cible.
            channels: Nombre de canaux cible (1 = mono).
        """
        self._ffmpeg = ffmpeg_binary or DEFAULT_FFMPEG_BINARY
        self._ffprobe = ffprobe_binary or DEFAULT_FFPROBE_BINARY
        self._sample_rate_hz = sample_rate_hz
        self._channels = channels

    def extract(self, video_path: Path, output_path: Path) -> AudioInfo:
        """Extrait l'audio en WAV mono 16 kHz.

        Args:
            video_path: Fichier vidéo source.
            output_path: Fichier WAV à produire.

        Returns:
            ``AudioInfo`` avec sample_rate, channels et duration.

        Raises:
            FFmpegError: Si la source est introuvable, sans piste audio, ou si
                ``ffmpeg`` échoue pour une autre raison.
        """
        if not video_path.exists():
            raise FFmpegError(
                code="FFMPEG.SOURCE_MISSING",
                user_message=f"Fichier source introuvable : {video_path}",
                severity=Severity.ERROR,
                technical_details={"video_path": str(video_path)},
            )

        self._ensure_audio_stream(video_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        cmd = [
            self._ffmpeg,
            "-y",
            "-i",
            str(video_path),
            "-vn",  # pas de vidéo
            "-ac",
            str(self._channels),
            "-ar",
            str(self._sample_rate_hz),
            "-c:a",
            _DEFAULT_AUDIO_CODEC,
            "-loglevel",
            FFMPEG_LOGLEVEL_ERROR,
            str(output_path),
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True)  # noqa: S603
        except FileNotFoundError as exc:
            raise FFmpegError(
                code="FFMPEG.BINARY_NOT_FOUND",
                user_message=(
                    "Le binaire ffmpeg est introuvable. Vérifie ton installation."
                ),
                severity=Severity.FATAL,
                technical_details={"ffmpeg_binary": self._ffmpeg},
            ) from exc
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else ""
            raise FFmpegError(
                code="FFMPEG.EXTRACTION_FAILED",
                user_message="Échec de l'extraction audio.",
                severity=Severity.ERROR,
                technical_details={"stderr": stderr, "cmd": cmd},
            ) from exc

        return AudioInfo(
            sample_rate_hz=self._sample_rate_hz,
            channels=self._channels,
            duration_seconds=self._probe_duration(output_path),
        )

    def _ensure_audio_stream(self, video_path: Path) -> None:
        """Vérifie que le fichier contient au moins une piste audio.

        Args:
            video_path: Fichier à inspecter.

        Raises:
            FFmpegError: Si pas de piste audio détectée.
        """
        try:
            result = subprocess.run(  # noqa: S603
                [
                    self._ffprobe,
                    "-loglevel",
                    FFMPEG_LOGLEVEL_ERROR,
                    "-select_streams",
                    "a",
                    "-show_entries",
                    "stream=index",
                    "-of",
                    "json",
                    str(video_path),
                ],
                check=True,
                capture_output=True,
            )
        except FileNotFoundError as exc:
            raise FFmpegError(
                code="FFMPEG.BINARY_NOT_FOUND",
                user_message=(
                    "Le binaire ffprobe est introuvable. Vérifie ton installation."
                ),
                severity=Severity.FATAL,
                technical_details={"ffprobe_binary": self._ffprobe},
            ) from exc
        except subprocess.CalledProcessError as exc:
            raise FFmpegError(
                code="FFMPEG.PROBE_FAILED",
                user_message="Impossible d'inspecter le fichier vidéo.",
                severity=Severity.ERROR,
                technical_details={
                    "stderr": exc.stderr.decode("utf-8", errors="replace")
                    if exc.stderr
                    else "",
                },
            ) from exc

        data = json.loads(result.stdout.decode("utf-8"))
        if not data.get("streams"):
            raise FFmpegError(
                code="FFMPEG.NO_AUDIO_STREAM",
                user_message="Cette vidéo ne contient pas de piste audio.",
                severity=Severity.ERROR,
                technical_details={"video_path": str(video_path)},
            )

    def probe_duration_seconds(self, media_path: Path) -> float:
        """Lit la durée totale d'un fichier média (vidéo ou audio) via ffprobe.

        Cette méthode est exposée pour les pré-calculs côté UI (ex. estimation
        de coût avant lancement d'un Run). Elle est silencieuse : si le
        binaire est indisponible ou si la sortie ne peut pas être parsée,
        elle renvoie ``0.0`` au lieu de lever.

        Args:
            media_path: Chemin du fichier à inspecter.

        Returns:
            Durée en secondes (``0.0`` si indéterminable).
        """
        return self._probe_duration(media_path)

    def _probe_duration(self, audio_path: Path) -> float:
        """Lit la durée d'un fichier audio via ffprobe.

        Args:
            audio_path: Fichier audio.

        Returns:
            Durée en secondes (0 si indéterminable, jamais lève).
        """
        try:
            result = subprocess.run(  # noqa: S603
                [
                    self._ffprobe,
                    "-loglevel",
                    FFMPEG_LOGLEVEL_ERROR,
                    "-show_entries",
                    "format=duration",
                    "-of",
                    "default=noprint_wrappers=1:nokey=1",
                    str(audio_path),
                ],
                check=True,
                capture_output=True,
            )
        except (FileNotFoundError, subprocess.CalledProcessError):
            return 0.0
        try:
            return float(result.stdout.decode("utf-8").strip())
        except ValueError:
            return 0.0


def has_ffmpeg_in_path() -> bool:
    """Indique si ``ffmpeg`` est trouvable dans le ``PATH`` courant.

    Returns:
        ``True`` si ``shutil.which("ffmpeg")`` retourne un chemin.
    """
    return shutil.which(DEFAULT_FFMPEG_BINARY) is not None
