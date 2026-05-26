"""Préparation de l'audio pour le STT cloud (limite 25 Mo d'OpenAI Whisper).

Transcode le WAV en Opus (compact) ; si le résultat dépasse la limite, découpe
aux silences (cf. ``_plan_boundaries``). Renvoie des ``AudioChunk`` (fichier
Opus + offset temporel) que l'adapter cloud transcrit puis recolle.
"""

from __future__ import annotations

import math
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from fahmi2.core.errors.exceptions import FFmpegError
from fahmi2.core.errors.severity import Severity

_OPUS_BITRATE_KBPS = 24
_MAX_CHUNK_BYTES = 24_000_000  # marge sous les 25 Mo (overhead conteneur)
_SILENCE_NOISE_DB = -30
_SILENCE_MIN_SECONDS = 0.5
_OPUS_CONTAINER_SUFFIX = ".ogg"
_OPUS_APPLICATION = "voip"
_FFMPEG_BINARY = "ffmpeg"
_FFPROBE_BINARY = "ffprobe"
_LOGLEVEL_ERROR = "error"
# Vise des segments un peu plus courts que la limite (VBR : la taille n'est pas
# strictement proportionnelle à la durée).
_SIZE_SAFETY_RATIO = 0.9
_RE_SILENCE_START = re.compile(r"silence_start:\s*([0-9.]+)")
_RE_SILENCE_END = re.compile(r"silence_end:\s*([0-9.]+)")
_UNKNOWN_ENCODER_MARKERS = ("Unknown encoder", "Automatic encoder selection failed")


@dataclass(frozen=True)
class AudioChunk:
    """Un segment audio prêt pour le STT cloud.

    Attributes:
        path: Fichier Opus (≤ ``max_chunk_bytes``).
        offset_seconds: Décalage temporel du segment dans l'audio d'origine.
        duration_seconds: Durée du segment (s). Utilisée par l'adapter cloud pour
            reconstruire la durée totale quand le modèle ne renvoie pas de
            timestamps (modèles ``gpt-4o-*-transcribe``).
    """

    path: Path
    offset_seconds: float
    duration_seconds: float = 0.0


class AudioPreparer(Protocol):
    """Contrat de préparation d'audio pour le STT cloud.

    Permet d'injecter un double de test dans l'adapter cloud sans dépendre de
    l'implémentation concrète ``CloudAudioPreparer``.
    """

    def prepare(self, wav_path: Path, work_dir: Path) -> list[AudioChunk]:
        """Produit des segments audio ≤ limite (avec offsets temporels).

        Args:
            wav_path: WAV source.
            work_dir: Dossier de travail.

        Returns:
            Liste ordonnée d'``AudioChunk`` (au moins un).
        """
        ...


class CloudAudioPreparer:
    """Transforme un WAV en fichiers Opus ≤ limite pour le STT cloud."""

    def __init__(
        self,
        *,
        ffmpeg_binary: str | None = None,
        ffprobe_binary: str | None = None,
        bitrate_kbps: int = _OPUS_BITRATE_KBPS,
        max_chunk_bytes: int = _MAX_CHUNK_BYTES,
        silence_noise_db: int = _SILENCE_NOISE_DB,
        silence_min_seconds: float = _SILENCE_MIN_SECONDS,
    ) -> None:
        """Construit le préparateur.

        Args:
            ffmpeg_binary: Chemin de ``ffmpeg`` (``None`` = depuis ``PATH``).
            ffprobe_binary: Chemin de ``ffprobe`` (``None`` = depuis ``PATH``).
            bitrate_kbps: Débit Opus cible (kbps).
            max_chunk_bytes: Taille maximale par fichier produit.
            silence_noise_db: Seuil de silence (dB) pour ``silencedetect``.
            silence_min_seconds: Durée minimale d'un silence détecté.
        """
        self._ffmpeg = ffmpeg_binary or _FFMPEG_BINARY
        self._ffprobe = ffprobe_binary or _FFPROBE_BINARY
        self._bitrate_kbps = bitrate_kbps
        self._max_chunk_bytes = max_chunk_bytes
        self._silence_noise_db = silence_noise_db
        self._silence_min_seconds = silence_min_seconds

    def prepare(self, wav_path: Path, work_dir: Path) -> list[AudioChunk]:
        """Produit des segments Opus ≤ limite, avec offsets.

        Args:
            wav_path: WAV source (16 kHz mono).
            work_dir: Dossier de travail (créé si absent).

        Returns:
            Liste ordonnée d'``AudioChunk`` (au moins un, offsets croissants).

        Raises:
            FFmpegError: Transcodage échoué ou encodeur ``libopus`` indisponible.
        """
        work_dir.mkdir(parents=True, exist_ok=True)
        full = work_dir / f"full{_OPUS_CONTAINER_SUFFIX}"
        self._encode_opus(wav_path, full, start=None, end=None)
        if full.stat().st_size <= self._max_chunk_bytes:
            return [
                AudioChunk(
                    path=full,
                    offset_seconds=0.0,
                    duration_seconds=self._probe_duration(wav_path),
                )
            ]
        return self._split(wav_path, work_dir, full.stat().st_size)

    def _split(
        self, wav_path: Path, work_dir: Path, full_size: int
    ) -> list[AudioChunk]:
        """Découpe le WAV en segments Opus ≤ limite, alignés sur les silences.

        Args:
            wav_path: WAV source.
            work_dir: Dossier de travail.
            full_size: Taille de l'Opus complet (pour estimer le nombre de
                segments).

        Returns:
            Liste ordonnée d'``AudioChunk`` (offsets croissants).
        """
        duration = self._probe_duration(wav_path)
        midpoints = self._detect_silence_midpoints(wav_path)
        n_segments = max(
            2, math.ceil(full_size / (self._max_chunk_bytes * _SIZE_SAFETY_RATIO))
        )
        bounds = self._plan_boundaries(duration, n_segments, midpoints)
        chunks: list[AudioChunk] = []
        for index, (start, end) in enumerate(bounds):
            seg = work_dir / f"seg_{index}{_OPUS_CONTAINER_SUFFIX}"
            self._encode_opus(wav_path, seg, start=start, end=end)
            chunks.append(
                AudioChunk(
                    path=seg, offset_seconds=start, duration_seconds=end - start
                )
            )
        return chunks

    @staticmethod
    def _plan_boundaries(
        duration: float, n_segments: int, silence_midpoints: list[float]
    ) -> list[tuple[float, float]]:
        """Calcule les bornes ``[start, end]`` de ``n_segments``, alignées aux silences.

        Pour chaque frontière visée ``k·duration/n``, choisit le silence le plus
        proche dans une fenêtre ``±(duration/n/2)`` ; à défaut, coupe à la cible.

        Args:
            duration: Durée totale (s).
            n_segments: Nombre de segments souhaité (>= 1).
            silence_midpoints: Milieux des silences détectés (s).

        Returns:
            Liste ordonnée de ``(start, end)`` couvrant ``[0, duration]``.
        """
        if n_segments <= 1:
            return [(0.0, duration)]
        step = duration / n_segments
        window = step / 2
        cuts: list[float] = []
        for k in range(1, n_segments):
            target = step * k
            candidates = [m for m in silence_midpoints if abs(m - target) <= window]
            cuts.append(
                min(candidates, key=lambda m: abs(m - target))
                if candidates
                else target
            )
        bounds: list[tuple[float, float]] = []
        prev = 0.0
        for cut in sorted(cuts):
            bounds.append((prev, cut))
            prev = cut
        bounds.append((prev, duration))
        return bounds

    def _detect_silence_midpoints(self, wav_path: Path) -> list[float]:
        """Détecte les silences (``silencedetect``) et retourne leurs milieux.

        Args:
            wav_path: WAV source.

        Returns:
            Liste des instants médians de chaque silence (s). Vide si aucun.
        """
        cmd = [
            self._ffmpeg, "-i", str(wav_path), "-af",
            f"silencedetect=noise={self._silence_noise_db}dB:"
            f"d={self._silence_min_seconds}",
            "-f", "null", "-",
        ]
        result = subprocess.run(cmd, capture_output=True, check=False)  # noqa: S603
        stderr = result.stderr.decode("utf-8", errors="replace")
        starts = [float(m) for m in _RE_SILENCE_START.findall(stderr)]
        ends = [float(m) for m in _RE_SILENCE_END.findall(stderr)]
        return [(s + e) / 2 for s, e in zip(starts, ends, strict=False)]

    def _probe_duration(self, media_path: Path) -> float:
        """Durée d'un média via ffprobe (``0.0`` si indéterminable).

        Args:
            media_path: Fichier à sonder.

        Returns:
            Durée en secondes.
        """
        try:
            result = subprocess.run(  # noqa: S603
                [
                    self._ffprobe, "-loglevel", _LOGLEVEL_ERROR,
                    "-show_entries", "format=duration",
                    "-of", "default=noprint_wrappers=1:nokey=1", str(media_path),
                ],
                check=True, capture_output=True,
            )
        except (FileNotFoundError, subprocess.CalledProcessError):
            return 0.0
        try:
            return float(result.stdout.decode("utf-8").strip())
        except ValueError:
            return 0.0

    def _encode_opus(
        self, src_wav: Path, out: Path, *, start: float | None, end: float | None
    ) -> None:
        """Encode (une tranche de) ``src_wav`` en Opus dans ``out``.

        Args:
            src_wav: WAV source.
            out: Fichier Opus cible.
            start: Début de tranche (s) ou ``None`` (depuis le début).
            end: Fin de tranche (s) ou ``None`` (jusqu'à la fin).

        Raises:
            FFmpegError: ``FFMPEG.OPUS_UNAVAILABLE`` si libopus absent, sinon
                ``FFMPEG.EXTRACTION_FAILED``.
        """
        cmd = [self._ffmpeg, "-y", "-i", str(src_wav)]
        if start is not None:
            cmd += ["-ss", str(start)]
        if end is not None:
            cmd += ["-to", str(end)]
        cmd += [
            "-vn", "-ac", "1", "-c:a", "libopus",
            "-b:a", f"{self._bitrate_kbps}k", "-application", _OPUS_APPLICATION,
            "-loglevel", _LOGLEVEL_ERROR, str(out),
        ]
        try:
            subprocess.run(cmd, check=True, capture_output=True)  # noqa: S603
        except FileNotFoundError as exc:
            raise FFmpegError(
                code="FFMPEG.BINARY_NOT_FOUND",
                user_message="Le binaire ffmpeg est introuvable.",
                severity=Severity.FATAL,
                technical_details={"ffmpeg_binary": self._ffmpeg},
            ) from exc
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else ""
            if any(marker in stderr for marker in _UNKNOWN_ENCODER_MARKERS):
                raise FFmpegError(
                    code="FFMPEG.OPUS_UNAVAILABLE",
                    user_message=(
                        "Le ffmpeg installé ne supporte pas l'encodeur Opus "
                        "(libopus), requis pour le STT cloud."
                    ),
                    severity=Severity.FATAL,
                    technical_details={"stderr": stderr},
                ) from exc
            raise FFmpegError(
                code="FFMPEG.EXTRACTION_FAILED",
                user_message="Échec de la compression audio (Opus).",
                severity=Severity.ERROR,
                technical_details={"stderr": stderr, "cmd": cmd},
            ) from exc
