"""Tests du FakeSTTProvider."""

from pathlib import Path

import pytest

from fahmi2.core.errors.exceptions import STTError
from fahmi2.core.errors.severity import Severity
from fahmi2.domain.enums import Language
from fahmi2.infra.stt._fakes import FakeSTTProvider
from fahmi2.infra.stt.interface import (
    STTProvider,
    Transcription,
    TranscriptionSegment,
)


def _sample_transcription() -> Transcription:
    return Transcription(
        segments=(
            TranscriptionSegment(start_seconds=0.0, end_seconds=2.0, text="bonjour"),
            TranscriptionSegment(start_seconds=2.0, end_seconds=4.0, text="le monde"),
        ),
        detected_language=Language.FR,
        duration_seconds=4.0,
    )


def test_fake_implements_protocol() -> None:
    fake: STTProvider = FakeSTTProvider()
    assert fake.name == "fake-stt"


def test_fake_returns_generic_when_no_scenario(tmp_path: Path) -> None:
    fake = FakeSTTProvider()
    path = tmp_path / "audio.wav"
    path.write_bytes(b"fake-audio")
    transcription = fake.transcribe(path)
    assert isinstance(transcription, Transcription)
    assert transcription.detected_language is Language.FR
    assert transcription.full_text()


def test_fake_returns_scripted_transcription(tmp_path: Path) -> None:
    expected = _sample_transcription()
    fake = FakeSTTProvider(scenarios={"audio.wav": expected})
    path = tmp_path / "audio.wav"
    path.write_bytes(b"x")
    transcription = fake.transcribe(path)
    assert transcription is expected


def test_fake_raises_when_configured_to_fail(tmp_path: Path) -> None:
    fake = FakeSTTProvider(failures={"audio.wav": STTError(
        code="STT.MODEL_LOAD_FAILED",
        user_message="boom",
        severity=Severity.ERROR,
    )})
    path = tmp_path / "audio.wav"
    path.write_bytes(b"x")
    with pytest.raises(STTError):
        fake.transcribe(path)


def test_fake_invokes_on_progress(tmp_path: Path) -> None:
    fake = FakeSTTProvider()
    path = tmp_path / "audio.wav"
    path.write_bytes(b"x")
    progress_values: list[float] = []
    fake.transcribe(path, on_progress=progress_values.append)
    assert progress_values == [0.0, 1.0]


def test_fake_estimate_cost_is_zero() -> None:
    fake = FakeSTTProvider()
    assert fake.estimate_cost(duration_seconds=600.0) == 0.0
