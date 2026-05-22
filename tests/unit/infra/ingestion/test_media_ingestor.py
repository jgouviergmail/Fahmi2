"""Tests de ``MediaIngestor`` (extraction ffmpeg réelle + STT factice)."""

import subprocess
from pathlib import Path

import pytest

from fahmi2.domain.enums import Language, SourceKind
from fahmi2.domain.source import InputSource
from fahmi2.infra.audio.ffmpeg_extractor import FFmpegExtractor, has_ffmpeg_in_path
from fahmi2.infra.ingestion.interface import IngestionDeps
from fahmi2.infra.ingestion.media_ingestor import MediaIngestor
from fahmi2.infra.storage.fs_artifacts import FsArtifactStore
from fahmi2.infra.stt._fakes import FakeSTTProvider

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


def _deps(workspace: Path) -> IngestionDeps:
    return IngestionDeps(
        workspace=workspace,
        artifacts=FsArtifactStore(),
        stt_provider=FakeSTTProvider(),
        ffmpeg=FFmpegExtractor(),
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
