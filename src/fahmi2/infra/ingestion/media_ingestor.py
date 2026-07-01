"""Ingesteur des sources média locales (vidéo + audio) : ffmpeg → STT.

Reprend la logique d'extraction audio + transcription historiquement portée par
la phase 0. Vidéo et audio sont traités à l'identique : ``ffmpeg`` extrait une
piste audio WAV 16 kHz mono, que le ``STTProvider`` transcrit. Pour une
**vidéo** dont l'option « analyser les slides » est activée, le contenu des
slides est extrait (``SlideAnalyzer``) puis fusionné, horodaté, dans la
transcription.
"""

from __future__ import annotations

from fahmi2.domain.enums import Language, SourceKind
from fahmi2.domain.source import InputSource
from fahmi2.infra.ingestion._fs import safe_delete
from fahmi2.infra.ingestion.interface import IngestionDeps
from fahmi2.infra.ingestion.slide_merge import merge_slides_into_transcription
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
        analyze_slides: bool = False,
    ) -> Transcription:
        """Extrait l'audio de ``source``, le transcrit, et fusionne les slides.

        Args:
            source: Source média locale (vidéo ou audio).
            source_id: Identifiant de la source (nom du WAV intermédiaire).
            deps: Dépendances injectées (ffmpeg, STT, workspace).
            language_hint: Indice de langue pour le STT (``None`` = auto).
            delete_audio_after: Supprime le WAV après transcription si ``True``.
            analyze_slides: Analyse les slides (vidéo uniquement, requiert
                ``deps.slide_analyzer``) et intercale leur contenu horodaté.

        Returns:
            La ``Transcription`` produite (enrichie des slides le cas échéant).

        Raises:
            FFmpegError: Si l'extraction ffmpeg (audio ou frames) échoue.
            STTError: Si la transcription échoue.
            VisionError: Si l'analyse vision échoue après retries.
        """
        audio_path = deps.workspace / _AUDIO_SUBDIR / f"{source_id}{_AUDIO_EXTENSION}"
        try:
            deps.ffmpeg.extract(source.as_path, audio_path)
            transcription = deps.stt_provider.transcribe(
                audio_path, language_hint=language_hint
            )
        finally:
            if delete_audio_after:
                safe_delete(audio_path)
        # L'analyse des slides suit le STT : la langue détectée pilote la
        # langue de sortie du prompt vision (transcript monolingue).
        if (
            analyze_slides
            and source.kind is SourceKind.VIDEO
            and deps.slide_analyzer is not None
        ):
            report = deps.slide_analyzer.analyze(
                source.as_path,
                source_id,
                workspace=deps.workspace,
                language=transcription.detected_language,
                duration_seconds=transcription.duration_seconds,
            )
            transcription = merge_slides_into_transcription(
                transcription, report.slides
            )
        return transcription
