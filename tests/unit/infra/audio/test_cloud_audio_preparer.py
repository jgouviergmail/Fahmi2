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


def test_plan_boundaries_snaps_to_nearest_silence() -> None:
    # 100 s, 2 segments -> cible 50 s ; silence a 48 s dans la fenetre +/-25 s.
    bounds = CloudAudioPreparer._plan_boundaries(100.0, 2, [48.0, 5.0])
    assert bounds == [(0.0, 48.0), (48.0, 100.0)]


def test_plan_boundaries_hard_cut_when_no_silence() -> None:
    bounds = CloudAudioPreparer._plan_boundaries(100.0, 2, [])
    assert bounds == [(0.0, 50.0), (50.0, 100.0)]


def test_plan_boundaries_single_segment() -> None:
    assert CloudAudioPreparer._plan_boundaries(100.0, 1, []) == [(0.0, 100.0)]


def test_prepare_splits_when_over_limit(speech_wav: Path, tmp_path: Path) -> None:
    # Limite minuscule -> force le decoupage du petit WAV.
    preparer = CloudAudioPreparer(max_chunk_bytes=4_000)
    chunks = preparer.prepare(speech_wav, tmp_path / "work")
    assert len(chunks) >= 2
    offsets = [c.offset_seconds for c in chunks]
    assert offsets == sorted(offsets)
    for c in chunks:
        assert c.path.exists()
