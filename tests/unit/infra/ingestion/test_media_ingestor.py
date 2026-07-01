"""Tests de ``MediaIngestor`` (extraction ffmpeg réelle + STT factice)."""

import subprocess
from pathlib import Path

import pytest
from PIL import Image

from fahmi2.domain.enums import Language, SourceKind
from fahmi2.domain.source import InputSource
from fahmi2.infra.audio.ffmpeg_extractor import FFmpegExtractor, has_ffmpeg_in_path
from fahmi2.infra.ingestion.interface import IngestionDeps
from fahmi2.infra.ingestion.media_ingestor import MediaIngestor
from fahmi2.infra.storage.fs_artifacts import FsArtifactStore
from fahmi2.infra.stt._fakes import FakeSTTProvider
from fahmi2.infra.video.frame_extractor import (
    SlideExtractionResult,
    SlideFrame,
    SlideFrameExtractor,
)
from fahmi2.infra.vision._fakes import FakeVisionProvider
from fahmi2.infra.vision.slide_analyzer import SlideAnalyzer

pytestmark = pytest.mark.skipif(not has_ffmpeg_in_path(), reason="ffmpeg requis")

_SOURCE_ID = "01HZX9KQ7N8YV3JD4M2C6B5A0E"


def _make_wav(path: Path) -> None:
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", "sine=frequency=440:duration=1",
            "-ac", "1", "-ar", "16000", "-loglevel", "error", str(path),
        ],
        check=True,
        capture_output=True,
    )


class _OneSlideFrameExtractor(SlideFrameExtractor):
    """Extracteur stub : une seule frame synthétique, sans appel ffmpeg."""

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


def _slide_analyzer() -> tuple[SlideAnalyzer, FakeVisionProvider]:
    provider = FakeVisionProvider()
    analyzer = SlideAnalyzer(
        frame_extractor=_OneSlideFrameExtractor(ffmpeg_binary="inutilise"),
        vision_provider=provider,
        llm_workers=1,
    )
    return analyzer, provider


def _deps(
    workspace: Path, slide_analyzer: SlideAnalyzer | None = None
) -> IngestionDeps:
    return IngestionDeps(
        workspace=workspace,
        artifacts=FsArtifactStore(),
        stt_provider=FakeSTTProvider(),
        ffmpeg=FFmpegExtractor(),
        slide_analyzer=slide_analyzer,
    )


def test_kind_is_audio_or_video() -> None:
    assert MediaIngestor().kind in {SourceKind.VIDEO, SourceKind.AUDIO}


def test_ingest_audio_produces_transcription_and_cleans_wav(tmp_path: Path) -> None:
    src_file = tmp_path / "lesson.wav"
    _make_wav(src_file)
    workspace = tmp_path / "ws"

    transcription = MediaIngestor().ingest(
        InputSource(kind=SourceKind.AUDIO, location=str(src_file)),
        _SOURCE_ID,
        _deps(workspace),
        language_hint=Language.FR,
        delete_audio_after=True,
    )

    assert transcription.segments  # FakeSTTProvider renvoie un segment par défaut
    # delete_audio_after=True : le WAV intermédiaire est supprimé
    assert not (workspace / "audio" / f"{_SOURCE_ID}.wav").exists()


def test_ingest_keeps_wav_when_requested(tmp_path: Path) -> None:
    src_file = tmp_path / "clip.wav"
    _make_wav(src_file)
    workspace = tmp_path / "ws"

    MediaIngestor().ingest(
        InputSource(kind=SourceKind.VIDEO, location=str(src_file)),
        _SOURCE_ID,
        _deps(workspace),
        language_hint=None,
        delete_audio_after=False,
    )

    assert (workspace / "audio" / f"{_SOURCE_ID}.wav").exists()


def test_video_avec_slides_fusionne_le_contenu(tmp_path: Path) -> None:
    """analyze_slides=True + vidéo : les segments slides sont intercalés."""
    src_file = tmp_path / "cours.wav"
    _make_wav(src_file)
    analyzer, provider = _slide_analyzer()

    transcription = MediaIngestor().ingest(
        InputSource(kind=SourceKind.VIDEO, location=str(src_file)),
        _SOURCE_ID,
        _deps(tmp_path / "ws", analyzer),
        language_hint=Language.FR,
        delete_audio_after=True,
        analyze_slides=True,
    )

    assert any(s.text.startswith("[Slide") for s in transcription.segments)
    assert len(provider.calls) == 1
    assert analyzer.consumed_cost_usd_for(_SOURCE_ID) > 0.0


def test_video_sans_option_ignore_les_slides(tmp_path: Path) -> None:
    """analyze_slides=False : le slide_analyzer n'est jamais appelé."""
    src_file = tmp_path / "cours.wav"
    _make_wav(src_file)
    analyzer, provider = _slide_analyzer()

    transcription = MediaIngestor().ingest(
        InputSource(kind=SourceKind.VIDEO, location=str(src_file)),
        _SOURCE_ID,
        _deps(tmp_path / "ws", analyzer),
        language_hint=Language.FR,
        delete_audio_after=True,
        analyze_slides=False,
    )

    assert not any(s.text.startswith("[Slide") for s in transcription.segments)
    assert provider.calls == []


def test_audio_avec_option_ignore_les_slides(tmp_path: Path) -> None:
    """Une source AUDIO n'est jamais analysée même avec analyze_slides=True."""
    src_file = tmp_path / "cours.wav"
    _make_wav(src_file)
    analyzer, provider = _slide_analyzer()

    MediaIngestor().ingest(
        InputSource(kind=SourceKind.AUDIO, location=str(src_file)),
        _SOURCE_ID,
        _deps(tmp_path / "ws", analyzer),
        language_hint=Language.FR,
        delete_audio_after=True,
        analyze_slides=True,
    )

    assert provider.calls == []


def test_option_sans_analyzer_disponible(tmp_path: Path) -> None:
    """slide_analyzer=None (pas de clé OpenAI) : transcription inchangée."""
    src_file = tmp_path / "cours.wav"
    _make_wav(src_file)

    transcription = MediaIngestor().ingest(
        InputSource(kind=SourceKind.VIDEO, location=str(src_file)),
        _SOURCE_ID,
        _deps(tmp_path / "ws", None),
        language_hint=Language.FR,
        delete_audio_after=True,
        analyze_slides=True,
    )

    assert not any(s.text.startswith("[Slide") for s in transcription.segments)
