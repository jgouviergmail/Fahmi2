"""Ingesteur des sources YouTube : téléchargement audio puis délégation média.

Compose ``MediaIngestor`` : ``yt-dlp`` télécharge la piste audio dans le
workspace, puis le fichier est ingéré comme un média local (ffmpeg + STT). Le
fichier téléchargé intermédiaire est supprimé après extraction.
"""

from __future__ import annotations

from fahmi2.domain.enums import Language, SourceKind
from fahmi2.domain.source import InputSource
from fahmi2.infra.ingestion._fs import safe_delete
from fahmi2.infra.ingestion.interface import IngestionDeps
from fahmi2.infra.ingestion.media_ingestor import MediaIngestor
from fahmi2.infra.ingestion.youtube_downloader import YoutubeDownloader
from fahmi2.infra.stt.interface import Transcription

_DOWNLOADS_SUBDIR = "downloads"


class YoutubeIngestor:
    """Ingesteur YouTube : télécharge l'audio (yt-dlp) puis délègue au média."""

    def __init__(
        self,
        downloader: YoutubeDownloader,
        media_ingestor: MediaIngestor,
    ) -> None:
        """Construit l'ingesteur.

        Args:
            downloader: Téléchargeur yt-dlp.
            media_ingestor: Ingesteur média réutilisé pour l'audio téléchargé.
        """
        self._downloader = downloader
        self._media_ingestor = media_ingestor

    @property
    def kind(self) -> SourceKind:
        """Type de source géré."""
        return SourceKind.YOUTUBE

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
        """Télécharge l'audio (ou la vidéo) de ``source`` puis l'ingère.

        Sans analyse de slides, seule la piste audio est téléchargée
        (comportement historique). Avec l'option activée, la **vidéo** ≤ 720p
        est téléchargée : la piste vidéo est nécessaire pour extraire les
        frames de slides.

        Args:
            source: Source YouTube (``location`` = URL).
            source_id: Identifiant de la source.
            deps: Dépendances injectées (workspace, ffmpeg, STT).
            language_hint: Indice de langue pour le STT.
            delete_audio_after: Transmis au ``MediaIngestor`` (WAV extrait).
            analyze_slides: Analyse les slides de la vidéo (requiert
                ``deps.slide_analyzer``).

        Returns:
            La ``Transcription`` produite.

        Raises:
            IngestionError: Échec de téléchargement (propagé du downloader).
        """
        downloads_dir = deps.workspace / _DOWNLOADS_SUBDIR
        with_slides = analyze_slides and deps.slide_analyzer is not None
        if with_slides:
            downloaded = self._downloader.download_video(
                source.location, downloads_dir, source_id
            )
            media_kind = SourceKind.VIDEO
        else:
            downloaded = self._downloader.download_audio(
                source.location, downloads_dir, source_id
            )
            media_kind = SourceKind.AUDIO
        try:
            media_source = InputSource(kind=media_kind, location=str(downloaded))
            return self._media_ingestor.ingest(
                media_source,
                source_id,
                deps,
                language_hint=language_hint,
                delete_audio_after=delete_audio_after,
                analyze_slides=with_slides,
            )
        finally:
            safe_delete(downloaded)
