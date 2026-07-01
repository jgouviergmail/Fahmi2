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

    def __init__(self) -> None:
        super().__init__()
        self.audio_calls: list[str] = []
        self.video_calls: list[str] = []

    def _make_media(self, dest_dir: Path, stem: str) -> Path:
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

    def download_audio(self, url: str, dest_dir: Path, stem: str) -> Path:
        self.audio_calls.append(url)
        return self._make_media(dest_dir, stem)

    def download_video(self, url: str, dest_dir: Path, stem: str) -> Path:
        self.video_calls.append(url)
        return self._make_media(dest_dir, stem)


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


def test_youtube_avec_slides_telecharge_la_video(tmp_path: Path) -> None:
    """analyze_slides=True : la vidéo est téléchargée (pas l'audio seul) et le
    contenu des slides est fusionné dans la transcription."""
    from PIL import Image  # noqa: PLC0415

    from fahmi2.infra.video.frame_extractor import (  # noqa: PLC0415
        SlideExtractionResult,
        SlideFrame,
        SlideFrameExtractor,
    )
    from fahmi2.infra.vision._fakes import FakeVisionProvider  # noqa: PLC0415
    from fahmi2.infra.vision.slide_analyzer import SlideAnalyzer  # noqa: PLC0415

    class _OneSlideFrameExtractor(SlideFrameExtractor):
        def extract(
            self, video_path: Path, frames_dir: Path, *, duration_seconds: float
        ) -> SlideExtractionResult:
            del video_path, duration_seconds
            frames_dir.mkdir(parents=True, exist_ok=True)
            frame = frames_dir / "000001.jpg"
            Image.new("RGB", (32, 32)).save(frame)
            return SlideExtractionResult(
                frames=(SlideFrame(0.0, 1.0, frame),), dropped_groups=0
            )

    analyzer = SlideAnalyzer(
        frame_extractor=_OneSlideFrameExtractor(ffmpeg_binary="inutilise"),
        vision_provider=FakeVisionProvider(),
        llm_workers=1,
    )
    downloader = _RealAudioDownloader()
    ingestor = YoutubeIngestor(downloader, MediaIngestor())
    deps = _deps(tmp_path)
    deps = IngestionDeps(
        workspace=deps.workspace,
        artifacts=deps.artifacts,
        stt_provider=deps.stt_provider,
        ffmpeg=deps.ffmpeg,
        slide_analyzer=analyzer,
    )

    transcription = ingestor.ingest(
        InputSource(kind=SourceKind.YOUTUBE, location="https://youtu.be/abc"),
        _SOURCE_ID,
        deps,
        language_hint=Language.FR,
        delete_audio_after=True,
        analyze_slides=True,
    )

    assert downloader.video_calls == ["https://youtu.be/abc"]
    assert downloader.audio_calls == []
    assert any(s.text.startswith("[Slide") for s in transcription.segments)


def test_youtube_sans_slides_telecharge_l_audio(tmp_path: Path) -> None:
    """Comportement historique préservé : audio seul, pas de vidéo."""
    downloader = _RealAudioDownloader()
    ingestor = YoutubeIngestor(downloader, MediaIngestor())

    ingestor.ingest(
        InputSource(kind=SourceKind.YOUTUBE, location="https://youtu.be/abc"),
        _SOURCE_ID,
        _deps(tmp_path),
        language_hint=Language.FR,
        delete_audio_after=True,
    )

    assert downloader.audio_calls == ["https://youtu.be/abc"]
    assert downloader.video_calls == []


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
