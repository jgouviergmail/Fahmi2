"""Tests du CloudAudioPreparer (ffmpeg réel)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from fahmi2.infra.audio.cloud_audio_preparer import AudioChunk, CloudAudioPreparer


@pytest.fixture(scope="session")
def speech_wav(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """Génère un WAV 16 kHz mono de 6 s (sinus) via ffmpeg."""
    out = tmp_path_factory.mktemp("cap_media") / "audio.wav"
    subprocess.run(
        [
            "ffmpeg", "-y", "-f", "lavfi", "-i",
            "sine=frequency=300:duration=6", "-ac", "1", "-ar", "16000",
            "-loglevel", "error", str(out),
        ],
        check=True, capture_output=True,
    )
    return out


def test_prepare_single_chunk_when_small(speech_wav: Path, tmp_path: Path) -> None:
    preparer = CloudAudioPreparer()
    chunks = preparer.prepare(speech_wav, tmp_path / "work")
    assert len(chunks) == 1
    assert isinstance(chunks[0], AudioChunk)
    assert chunks[0].offset_seconds == 0.0
    assert chunks[0].path.exists()
    assert chunks[0].path.suffix == ".ogg"
    # Opus bien plus petit que le WAV source.
    assert chunks[0].path.stat().st_size < speech_wav.stat().st_size
