"""Ingesteur des sources média locales (vidéo + audio) : ffmpeg → STT.

Reprend la logique d'extraction audio + transcription historiquement portée par
la phase 0. Vidéo et audio sont traités à l'identique : ``ffmpeg`` extrait une
piste audio WAV 16 kHz mono, que le ``STTProvider`` transcrit.
"""

from __future__ import annotations

from pathlib import Path

from fahmi2.domain.enums import Language, SourceKind
from fahmi2.domain.source import InputSource
from fahmi2.infra.ingestion.interface import IngestionDeps
from fahmi2.infra.stt.interface import Transcription

_AUDIO_SUBDIR = "audio"
_AUDIO_EXTENSION = ".wav"


class MediaIngestor:
    """Ingesteur vidéo/audio : extrait l'audio (WAV 16 kHz mono) puis transcrit."""

    @property
    def kind(self) -> SourceKind:
        """Type de référence de l'ingesteur.

        Note:
            ``MediaIngestor`` gère **deux** types (``VIDEO`` et ``AUDIO``) au
            comportement identique ; le dispatcher l'enregistre sous les deux
            clés. Cette propriété renvoie ``AUDIO`` par convention et n'est pas
            utilisée pour le routage.
        """
        return SourceKind.AUDIO

    def ingest(
        self,
        source: InputSource,
        source_id: str,
        deps: IngestionDeps,
        *,
        language_hint: Language | None,
        delete_audio_after: bool,
    ) -> Transcription:
        """Extrait l'audio de ``source`` et le transcrit.

        Args:
            source: Source média locale (vidéo ou audio).
            source_id: Identifiant de la source (nom du WAV intermédiaire).
            deps: Dépendances injectées (ffmpeg, STT, workspace).
            language_hint: Indice de langue pour le STT (``None`` = auto).
            delete_audio_after: Supprime le WAV après transcription si ``True``.

        Returns:
            La ``Transcription`` produite.

        Raises:
            FFmpegError: Si l'extraction ffmpeg échoue.
            STTError: Si la transcription échoue.
        """
        audio_path = deps.workspace / _AUDIO_SUBDIR / f"{source_id}{_AUDIO_EXTENSION}"
        try:
            deps.ffmpeg.extract(source.as_path, audio_path)
            return deps.stt_provider.transcribe(
                audio_path, language_hint=language_hint
            )
        finally:
            if delete_audio_after:
                _safe_delete(audio_path)


def _safe_delete(path: Path) -> None:
    """Supprime ``path`` si présent, sans lever en cas d'échec.

    Args:
        path: Fichier à supprimer.
    """
    if path.exists():
        try:
            path.unlink()
        except OSError:
            pass
