"""Tests des dataclasses Transcription et TranscriptionSegment."""

import pytest

from fahmi2.domain.enums import Language
from fahmi2.infra.stt.interface import Transcription, TranscriptionSegment


def test_segment_minimal() -> None:
    s = TranscriptionSegment(start_seconds=0.0, end_seconds=2.5, text="hello world")
    assert s.start_seconds == 0.0
    assert s.end_seconds == 2.5
    assert s.text == "hello world"


def test_segment_validates_time_order() -> None:
    with pytest.raises(ValueError):
        TranscriptionSegment(start_seconds=2.0, end_seconds=1.0, text="x")


def test_segment_accepts_equal_start_and_end() -> None:
    s = TranscriptionSegment(start_seconds=1.0, end_seconds=1.0, text="")
    assert s.start_seconds == s.end_seconds


def test_segment_rejects_negative_start() -> None:
    with pytest.raises(ValueError):
        TranscriptionSegment(start_seconds=-0.1, end_seconds=1.0, text="x")


def test_transcription_minimal() -> None:
    seg = TranscriptionSegment(start_seconds=0.0, end_seconds=2.0, text="hi")
    t = Transcription(
        segments=(seg,),
        detected_language=Language.EN,
        duration_seconds=2.0,
    )
    assert t.segments == (seg,)
    assert t.detected_language is Language.EN
    assert t.duration_seconds == 2.0


def test_transcription_full_text_joins_segments() -> None:
    segs = (
        TranscriptionSegment(start_seconds=0.0, end_seconds=1.0, text="bonjour"),
        TranscriptionSegment(start_seconds=1.0, end_seconds=2.0, text="le monde"),
    )
    t = Transcription(
        segments=segs, detected_language=Language.FR, duration_seconds=2.0
    )
    assert t.full_text() == "bonjour le monde"


def test_transcription_full_text_empty() -> None:
    t = Transcription(
        segments=(), detected_language=Language.FR, duration_seconds=0.0
    )
    assert t.full_text() == ""


def test_transcription_rejects_negative_duration() -> None:
    with pytest.raises(ValueError):
        Transcription(
            segments=(), detected_language=Language.FR, duration_seconds=-1.0
        )
