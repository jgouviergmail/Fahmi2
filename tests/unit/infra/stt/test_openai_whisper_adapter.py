"""Tests d'OpenAIWhisperAdapter (mocké via responses)."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from openai import AuthenticationError, RateLimitError

from fahmi2.core.errors.exceptions import STTError
from fahmi2.domain.enums import Language
from fahmi2.infra.stt.openai_whisper_adapter import (
    OpenAIWhisperAdapter,
    _parse_verbose_response,
)


def _verbose_payload() -> dict[str, object]:
    return {
        "language": "fr",
        "duration": 2.0,
        "segments": [
            {"start": 0.0, "end": 1.0, "text": "bonjour"},
            {"start": 1.0, "end": 2.0, "text": "le monde"},
        ],
    }


def test_parse_verbose_response_basic() -> None:
    transcription = _parse_verbose_response(_verbose_payload())
    assert transcription.detected_language is Language.FR
    assert transcription.duration_seconds == 2.0
    assert len(transcription.segments) == 2
    assert transcription.full_text() == "bonjour le monde"


def test_parse_verbose_response_maps_full_language_name() -> None:
    # OpenAI Whisper (verbose_json) renvoie le NOM complet de la langue détectée
    # (ex. "french"/"english"), pas le code ISO — doit être mappé vers Language.
    fr = _parse_verbose_response(
        {"language": "french", "duration": 1.0, "segments": []}
    )
    assert fr.detected_language is Language.FR
    en = _parse_verbose_response(
        {"language": "English", "duration": 1.0, "segments": []}
    )
    assert en.detected_language is Language.EN


def test_parse_verbose_response_unknown_language_uses_fallback() -> None:
    # Langue détectée hors périmètre (FR/EN) : repli sur l'indice fourni.
    t = _parse_verbose_response(
        {"language": "spanish", "duration": 1.0, "segments": []},
        fallback=Language.FR,
    )
    assert t.detected_language is Language.FR


def test_parse_verbose_response_empty_segments() -> None:
    transcription = _parse_verbose_response(
        {"language": "en", "duration": 0.0, "segments": []}
    )
    assert transcription.segments == ()


def test_estimate_cost_per_minute() -> None:
    adapter = OpenAIWhisperAdapter(api_key="dummy", client=MagicMock())
    assert adapter.estimate_cost(duration_seconds=60.0) == pytest.approx(0.006)
    assert adapter.estimate_cost(duration_seconds=600.0) == pytest.approx(0.06)


def test_name() -> None:
    adapter = OpenAIWhisperAdapter(api_key="dummy", client=MagicMock())
    assert adapter.name == "openai-whisper"


def test_transcribe_returns_transcription(tmp_path: Path) -> None:
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"x")

    mock_client = MagicMock()
    response_mock = MagicMock()
    response_mock.model_dump.return_value = _verbose_payload()
    mock_client.audio.transcriptions.create.return_value = response_mock

    adapter = OpenAIWhisperAdapter(api_key="dummy", client=mock_client)
    result = adapter.transcribe(audio)
    assert result.full_text() == "bonjour le monde"
    mock_client.audio.transcriptions.create.assert_called_once()


def test_transcribe_invokes_on_progress(tmp_path: Path) -> None:
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"x")

    mock_client = MagicMock()
    response_mock = MagicMock()
    response_mock.model_dump.return_value = _verbose_payload()
    mock_client.audio.transcriptions.create.return_value = response_mock

    adapter = OpenAIWhisperAdapter(api_key="dummy", client=mock_client)
    progress: list[float] = []
    adapter.transcribe(audio, on_progress=progress.append)
    assert progress == [0.0, 1.0]


def test_transcribe_maps_auth_error(tmp_path: Path) -> None:
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"x")

    mock_client = MagicMock()
    response_mock = MagicMock()
    response_mock.request = MagicMock()
    mock_client.audio.transcriptions.create.side_effect = AuthenticationError(
        message="bad key", response=response_mock, body=None
    )

    adapter = OpenAIWhisperAdapter(api_key="dummy", client=mock_client)
    with pytest.raises(STTError) as exc_info:
        adapter.transcribe(audio)
    assert exc_info.value.code == "STT.AUTH_INVALID"


def test_transcribe_maps_rate_limit(tmp_path: Path) -> None:
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"x")

    mock_client = MagicMock()
    response_mock = MagicMock()
    response_mock.request = MagicMock()
    mock_client.audio.transcriptions.create.side_effect = RateLimitError(
        message="too many", response=response_mock, body=None
    )

    adapter = OpenAIWhisperAdapter(api_key="dummy", client=mock_client)
    with pytest.raises(STTError) as exc_info:
        adapter.transcribe(audio)
    assert exc_info.value.code == "STT.RATE_LIMIT"
