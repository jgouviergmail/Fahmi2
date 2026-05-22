"""Téléchargement de l'audio d'une vidéo YouTube via le binaire ``yt-dlp``.

Port ``YoutubeDownloader`` + adapter ``YtDlpDownloader`` (subprocess). Liens
**unitaires** uniquement (``--no-playlist``). Le binaire est résolu au runtime
(bundlé / override ``FAHMI2_YTDLP``) et reste **remplaçable** sans rebuild
(yt-dlp casse régulièrement quand YouTube évolue).
"""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Protocol

from fahmi2.core.errors.exceptions import IngestionError
from fahmi2.core.errors.severity import Severity

_YTDLP_BINARY = "yt-dlp"
_BESTAUDIO_FORMAT = "bestaudio/best"
_NO_PLAYLIST = "--no-playlist"
#: Suffixes des artefacts de téléchargement partiel/temporaire de yt-dlp, à
#: ignorer lors de la sélection du fichier audio produit.
_PARTIAL_DOWNLOAD_SUFFIXES = frozenset({".part", ".ytdl", ".temp"})
#: Délai maximal du téléchargement audio (s). Généreux : une longue vidéo de
#: cours peut produire un flux audio volumineux sur une connexion lente. Au-delà,
#: le processus est tué pour éviter un blocage indéfini du worker.
_DOWNLOAD_TIMEOUT_SECONDS = 1800.0
#: Délai maximal de la sonde de durée (s). L'opération ne télécharge pas le
#: média (``--skip-download``), donc reste rapide.
_PROBE_TIMEOUT_SECONDS = 60.0


class YoutubeDownloader(Protocol):
    """Télécharge l'audio d'une vidéo YouTube et sonde sa durée."""

    def download_audio(self, url: str, dest_dir: Path, stem: str) -> Path:
        """Télécharge la meilleure piste audio de ``url`` dans ``dest_dir``.

        Args:
            url: URL de la vidéo YouTube (unitaire).
            dest_dir: Dossier de destination (créé si absent).
            stem: Nom de base du fichier produit (sans extension).

        Returns:
            Le chemin du fichier audio téléchargé.

        Raises:
            IngestionError: ``INGESTION.YTDLP_NOT_FOUND`` ou
                ``INGESTION.YOUTUBE_DOWNLOAD_FAILED``.
        """

    def probe_duration(self, url: str) -> float:
        """Durée de la vidéo (s) via métadonnée, sans téléchargement.

        Args:
            url: URL de la vidéo.

        Returns:
            La durée en secondes (``0.0`` si indéterminable / réseau indisponible).
        """


class YtDlpDownloader:
    """Adapter ``yt-dlp`` (binaire externe)."""

    def __init__(self, *, ytdlp_binary: str | None = None) -> None:
        """Construit l'adapter.

        Args:
            ytdlp_binary: Chemin du binaire yt-dlp (``None`` = ``yt-dlp`` du PATH).
        """
        self._ytdlp = ytdlp_binary or _YTDLP_BINARY

    def download_audio(self, url: str, dest_dir: Path, stem: str) -> Path:
        """Télécharge la meilleure piste audio (cf. ``YoutubeDownloader``).

        Args:
            url: URL de la vidéo YouTube.
            dest_dir: Dossier de destination.
            stem: Nom de base du fichier produit.

        Returns:
            Le chemin du fichier audio téléchargé.

        Raises:
            IngestionError: ``INGESTION.YTDLP_NOT_FOUND`` si le binaire est
                introuvable, ``INGESTION.YOUTUBE_DOWNLOAD_FAILED`` sinon.
        """
        dest_dir.mkdir(parents=True, exist_ok=True)
        output_template = str(dest_dir / f"{stem}.%(ext)s")
        cmd = [
            self._ytdlp, _NO_PLAYLIST, "-f", _BESTAUDIO_FORMAT,
            "-o", output_template, url,
        ]
        try:
            subprocess.run(  # noqa: S603
                cmd, check=True, capture_output=True, timeout=_DOWNLOAD_TIMEOUT_SECONDS
            )
        except FileNotFoundError as exc:
            raise IngestionError(
                code="INGESTION.YTDLP_NOT_FOUND",
                user_message=(
                    "yt-dlp est introuvable. Installez-le ou définissez la "
                    "variable d'environnement FAHMI2_YTDLP."
                ),
                severity=Severity.FATAL,
                technical_details={"ytdlp_binary": self._ytdlp},
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise IngestionError(
                code="INGESTION.YOUTUBE_DOWNLOAD_FAILED",
                user_message=(
                    "Le téléchargement YouTube a dépassé le délai imparti "
                    "(connexion lente, ou yt-dlp bloqué). Réessayez."
                ),
                severity=Severity.ERROR,
                technical_details={
                    "url": url,
                    "timeout_seconds": _DOWNLOAD_TIMEOUT_SECONDS,
                },
            ) from exc
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr.decode("utf-8", errors="replace") if exc.stderr else ""
            raise IngestionError(
                code="INGESTION.YOUTUBE_DOWNLOAD_FAILED",
                user_message=(
                    "Échec du téléchargement YouTube (vidéo indisponible, privée, "
                    "géo-bloquée, ou yt-dlp obsolète — essayez de le mettre à jour)."
                ),
                severity=Severity.ERROR,
                technical_details={"url": url, "stderr": stderr},
            ) from exc
        produced = sorted(
            p
            for p in dest_dir.glob(f"{stem}.*")
            if p.suffix.lower() not in _PARTIAL_DOWNLOAD_SUFFIXES
        )
        if not produced:
            raise IngestionError(
                code="INGESTION.YOUTUBE_DOWNLOAD_FAILED",
                user_message="Le téléchargement YouTube n'a produit aucun fichier.",
                severity=Severity.ERROR,
                technical_details={"url": url, "stem": stem},
            )
        return produced[0]

    def probe_duration(self, url: str) -> float:
        """Durée via ``--print duration --skip-download`` (cf. ``YoutubeDownloader``).

        Args:
            url: URL de la vidéo.

        Returns:
            La durée en secondes, ou ``0.0`` si indéterminable.
        """
        cmd = [
            self._ytdlp, _NO_PLAYLIST, "--skip-download", "--print", "duration", url,
        ]
        try:
            result = subprocess.run(  # noqa: S603
                cmd, check=True, capture_output=True, timeout=_PROBE_TIMEOUT_SECONDS
            )
        except (
            FileNotFoundError,
            subprocess.CalledProcessError,
            subprocess.TimeoutExpired,
        ):
            return 0.0
        try:
            return float(result.stdout.decode("utf-8").strip().splitlines()[-1])
        except (ValueError, IndexError):
            return 0.0
