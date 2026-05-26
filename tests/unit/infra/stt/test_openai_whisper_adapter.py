"""Tests d'OpenAIWhisperAdapter (mocké via responses)."""

from pathlib import Path
from unittest.mock import MagicMock

import pytest
from openai import AuthenticationError, RateLimitError

from fahmi2.core.errors.exceptions import STTError
from fahmi2.domain.enums import Language
from fahmi2.infra.audio.cloud_audio_preparer import AudioChunk
from fahmi2.infra.stt.openai_whisper_adapter import (
    OpenAIWhisperAdapter,
    _parse_verbose_response,
    _resolve_language,
)


def test_resolve_language_maps_new_languages() -> None:
    assert _resolve_language("german", fallback=None) is Language.DE
    assert _resolve_language("de", fallback=None) is Language.DE
    assert _resolve_language("spanish", fallback=None) is Language.ES
    assert _resolve_language("italian", fallback=None) is Language.IT
    assert _resolve_language("chinese", fallback=None) is Language.ZH
    assert _resolve_language("zh", fallback=None) is Language.ZH
    assert _resolve_language("arabic", fallback=None) is Language.AR


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
    # Langue détectée hors périmètre supporté (ex. japonais) : repli sur l'indice.
    t = _parse_verbose_response(
        {"language": "japanese", "duration": 1.0, "segments": []},
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


def test_estimate_cost_uses_model_pricing() -> None:
    # gpt-4o-mini-transcribe est 2× moins cher que whisper-1.
    mini = OpenAIWhisperAdapter(
        api_key="dummy", client=MagicMock(), model="gpt-4o-mini-transcribe"
    )
    assert mini.estimate_cost(duration_seconds=60.0) == pytest.approx(0.003)


def test_name() -> None:
    adapter = OpenAIWhisperAdapter(api_key="dummy", client=MagicMock())
    assert adapter.name == "openai-whisper"


def test_transcribe_gpt4o_uses_json_and_single_segment(tmp_path: Path) -> None:
    # Les modèles gpt-4o-* ne supportent pas verbose_json : on bascule en json et
    # produit un segment unique par tranche (offset + durée du préparateur).
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"x")

    class _FakePreparer:
        def prepare(self, wav_path: Path, work_dir: Path) -> list[AudioChunk]:
            return [
                AudioChunk(
                    path=tmp_path / "a.ogg", offset_seconds=0.0, duration_seconds=30.0
                ),
                AudioChunk(
                    path=tmp_path / "b.ogg", offset_seconds=30.0, duration_seconds=20.0
                ),
            ]

    (tmp_path / "a.ogg").write_bytes(b"a")
    (tmp_path / "b.ogg").write_bytes(b"b")

    def _resp(text: str) -> object:
        m = MagicMock()
        m.text = text
        return m

    mock_client = MagicMock()
    mock_client.audio.transcriptions.create.side_effect = [_resp("un"), _resp("deux")]
    adapter = OpenAIWhisperAdapter(
        api_key="dummy",
        client=mock_client,
        preparer=_FakePreparer(),
        model="gpt-4o-transcribe",
    )
    result = adapter.transcribe(audio, language_hint=Language.FR)
    assert result.full_text() == "un deux"
    assert [(s.start_seconds, s.end_seconds, s.text) for s in result.segments] == [
        (0.0, 30.0, "un"),
        (30.0, 50.0, "deux"),
    ]
    assert result.duration_seconds == pytest.approx(50.0)
    assert result.detected_language is Language.FR  # json ne renvoie pas la langue
    call = mock_client.audio.transcriptions.create.call_args
    assert call.kwargs["response_format"] == "json"
    assert call.kwargs["model"] == "gpt-4o-transcribe"


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


def test_transcribe_merges_chunks_with_offsets(tmp_path: Path) -> None:
    audio = tmp_path / "audio.wav"
    audio.write_bytes(b"x")

    class _FakePreparer:
        def prepare(self, wav_path: Path, work_dir: Path) -> list[AudioChunk]:
            return [
                AudioChunk(path=tmp_path / "a.ogg", offset_seconds=0.0),
                AudioChunk(path=tmp_path / "b.ogg", offset_seconds=60.0),
            ]

    (tmp_path / "a.ogg").write_bytes(b"a")
    (tmp_path / "b.ogg").write_bytes(b"b")

    def _resp(text: str, start: float, end: float) -> object:
        m = MagicMock()
        m.model_dump.return_value = {
            "language": "french",
            "duration": end,
            "segments": [{"start": start, "end": end, "text": text}],
        }
        return m

    mock_client = MagicMock()
    mock_client.audio.transcriptions.create.side_effect = [
        _resp("un", 0.0, 5.0),
        _resp("deux", 1.0, 4.0),
    ]
    adapter = OpenAIWhisperAdapter(
        api_key="dummy", client=mock_client, preparer=_FakePreparer()
    )
    result = adapter.transcribe(audio)
    assert result.detected_language is Language.FR
    assert [
        (s.start_seconds, s.end_seconds, s.text) for s in result.segments
    ] == [
        (0.0, 5.0, "un"),
        (61.0, 64.0, "deux"),
    ]
    assert mock_client.audio.transcriptions.create.call_count == 2
