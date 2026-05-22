"""Tests de ``YoutubeIngestor`` (téléchargement fake + délégation média)."""

import subprocess
from pathlib import Path

import pytest

from fahmi2.core.errors.exceptions import IngestionError
from fahmi2.core.errors.severity import Severity
from fahmi2.domain.enums import Language, SourceKind
from fahmi2.domain.source import InputSource
from fahmi2.infra.audio.ffmpeg_extractor import FFmpegExtractor, has_ffmpeg_in_path
from fahmi2.infra.ingestion._fakes import FakeYoutubeDownloader
from fahmi2.infra.ingestion.interface import IngestionDeps
from fahmi2.infra.ingestion.media_ingestor import MediaIngestor
from fahmi2.infra.ingestion.youtube_ingestor import YoutubeIngestor
from fahmi2.infra.storage.fs_artifacts import FsArtifactStore
from fahmi2.infra.stt._fakes import FakeSTTProvider

_SOURCE_ID = "01HZX9KQ7N8YV3JD4M2C6B5A0E"
pytestmark = pytest.mark.skipif(not has_ffmpeg_in_path(), reason="ffmpeg requis")


class _RealAudioDownloader(FakeYoutubeDownloader):
    """Downloader fake produisant un vrai WAV (pour l'extraction ffmpeg)."""

    def download_audio(self, url: str, dest_dir: Path, stem: str) -> Path:
        del url
        dest_dir.mkdir(parents=True, exist_ok=True)
        out = dest_dir / f"{stem}.wav"
        subprocess.run(
            [
                "ffmpeg", "-y", "-f", "lavfi", "-i",
                "sine=frequency=440:duration=1", "-ac", "1", "-ar", "16000",
                "-loglevel", "error", str(out),
            ],
            check=True,
            capture_output=True,
        )
        return out


def _deps(tmp_path: Path) -> IngestionDeps:
    return IngestionDeps(
        workspace=tmp_path / "ws",
        artifacts=FsArtifactStore(),
        stt_provider=FakeSTTProvider(),
        ffmpeg=FFmpegExtractor(),
    )


def test_youtube_ingest_delegates_to_media(tmp_path: Path) -> None:
    ingestor = YoutubeIngestor(_RealAudioDownloader(), MediaIngestor())
    transcription = ingestor.ingest(
        InputSource(kind=SourceKind.YOUTUBE, location="https://youtu.be/abc"),
        _SOURCE_ID,
        _deps(tmp_path),
        language_hint=Language.FR,
        delete_audio_after=True,
    )
    assert transcription.segments
    # Le fichier téléchargé intermédiaire est nettoyé.
    assert not (tmp_path / "ws" / "downloads" / f"{_SOURCE_ID}.wav").exists()


def test_youtube_ingest_propagates_download_error(tmp_path: Path) -> None:
    boom = IngestionError(
        code="INGESTION.YOUTUBE_DOWNLOAD_FAILED",
        user_message="échec",
        severity=Severity.ERROR,
    )
    ingestor = YoutubeIngestor(
        FakeYoutubeDownloader(fail_with=boom), MediaIngestor()
    )
    with pytest.raises(IngestionError) as exc:
        ingestor.ingest(
            InputSource(kind=SourceKind.YOUTUBE, location="https://youtu.be/x"),
            _SOURCE_ID,
            _deps(tmp_path),
            language_hint=Language.FR,
            delete_audio_after=True,
        )
    assert exc.value.code == "INGESTION.YOUTUBE_DOWNLOAD_FAILED"
