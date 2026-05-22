"""Tests du value object ``InputSource`` et de l'entité ``SourceExecution``."""

from pathlib import Path

import pytest

from fahmi2.domain.enums import PhaseId, PhaseStatus, SourceKind
from fahmi2.domain.ids import SourceId
from fahmi2.domain.source import InputSource, SourceExecution


def test_local_file_source() -> None:
    src = InputSource(kind=SourceKind.VIDEO, location="D:/cours/01-intro.mp4")
    assert src.is_remote is False
    assert src.as_path == Path("D:/cours/01-intro.mp4")
    assert src.order_key() == "01-intro.mp4"
    assert src.display_name() == "01-intro.mp4"


def test_audio_source_is_local() -> None:
    src = InputSource(kind=SourceKind.AUDIO, location="/tmp/lesson.mp3")
    assert src.is_remote is False
    assert src.order_key() == "lesson.mp3"


def test_youtube_source_is_remote() -> None:
    src = InputSource(kind=SourceKind.YOUTUBE, location="https://youtu.be/abc123")
    assert src.is_remote is True
    assert src.order_key() == "https://youtu.be/abc123"
    assert src.display_name() == "https://youtu.be/abc123"
    with pytest.raises(ValueError, match="distante"):
        _ = src.as_path


def test_source_execution_phase_status_default_pending() -> None:
    se = SourceExecution(
        source_id=SourceId.new(),
        source=InputSource(kind=SourceKind.VIDEO, location="a.mp4"),
    )
    assert se.phase_status(PhaseId.STT) is PhaseStatus.PENDING
    assert se.detected_language is None
