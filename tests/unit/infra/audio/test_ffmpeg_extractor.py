"""Tests de FFmpegExtractor."""

import subprocess
from pathlib import Path

import pytest

from fahmi2.core.errors.exceptions import FFmpegError
from fahmi2.infra.audio.ffmpeg_extractor import (
    AudioInfo,
    FFmpegExtractor,
)


@pytest.fixture(scope="session")
def short_mp4_with_audio(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Génère un fichier MP4 court de 2 s avec piste audio sine."""
    out = tmp_path_factory.mktemp("media") / "short.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=2",
            "-f",
            "lavfi",
            "-i",
            "testsrc=duration=2:size=64x48:rate=10",
            "-c:a",
            "aac",
            "-c:v",
            "libx264",
            "-shortest",
            "-loglevel",
            "error",
            str(out),
        ],
        check=True,
        capture_output=True,
    )
    return out


@pytest.fixture(scope="session")
def video_no_audio(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Génère un MP4 court sans piste audio."""
    out = tmp_path_factory.mktemp("media") / "silent.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "testsrc=duration=1:size=64x48:rate=10",
            "-c:v",
            "libx264",
            "-loglevel",
            "error",
            str(out),
        ],
        check=True,
        capture_output=True,
    )
    return out


def test_extract_creates_wav_file(short_mp4_with_audio: Path, tmp_path: Path) -> None:
    extractor = FFmpegExtractor()
    out_wav = tmp_path / "audio.wav"
    info = extractor.extract(short_mp4_with_audio, out_wav)
    assert out_wav.exists()
    assert info.sample_rate_hz == 16_000
    assert info.channels == 1
    assert 1.5 < info.duration_seconds < 2.5


def test_extract_creates_parent_directory(
    short_mp4_with_audio: Path, tmp_path: Path
) -> None:
    extractor = FFmpegExtractor()
    out_wav = tmp_path / "sub" / "dir" / "audio.wav"
    extractor.extract(short_mp4_with_audio, out_wav)
    assert out_wav.exists()


def test_extract_raises_when_source_missing(tmp_path: Path) -> None:
    extractor = FFmpegExtractor()
    out_wav = tmp_path / "audio.wav"
    with pytest.raises(FFmpegError) as exc_info:
        extractor.extract(tmp_path / "missing.mp4", out_wav)
    assert exc_info.value.code in {"FFMPEG.SOURCE_MISSING", "FFMPEG.EXTRACTION_FAILED"}


def test_extract_raises_when_no_audio_stream(
    video_no_audio: Path, tmp_path: Path
) -> None:
    extractor = FFmpegExtractor()
    out_wav = tmp_path / "audio.wav"
    with pytest.raises(FFmpegError) as exc_info:
        extractor.extract(video_no_audio, out_wav)
    assert exc_info.value.code == "FFMPEG.NO_AUDIO_STREAM"


def test_audio_info_serializable() -> None:
    info = AudioInfo(sample_rate_hz=16_000, channels=1, duration_seconds=12.5)
    assert info.sample_rate_hz == 16_000
    assert info.channels == 1
    assert info.duration_seconds == 12.5
