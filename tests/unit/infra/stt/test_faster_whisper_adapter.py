"""Tests de FasterWhisperAdapter (CUDA mocké)."""

from pathlib import Path

import faster_whisper
import pytest

from fahmi2.core.errors.exceptions import STTError
from fahmi2.infra.stt.faster_whisper_adapter import FasterWhisperAdapter


def test_name(tmp_path: Path) -> None:
    adapter = FasterWhisperAdapter(model_cache_dir=tmp_path, cuda_check=lambda: True)
    assert adapter.name == "faster-whisper-large-v3-turbo"


def test_name_reflects_configured_model(tmp_path: Path) -> None:
    adapter = FasterWhisperAdapter(
        model_cache_dir=tmp_path, model="medium", cuda_check=lambda: True
    )
    assert adapter.name == "faster-whisper-medium"


def test_configured_model_passed_to_whisper(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    captured: dict[str, object] = {}

    def _capture(name: str, **kwargs: object) -> object:
        captured["name"] = name
        return object()

    monkeypatch.setattr(faster_whisper, "WhisperModel", _capture)
    adapter = FasterWhisperAdapter(
        model_cache_dir=tmp_path, model="small", cuda_check=lambda: True
    )
    adapter._load_model_or_raise()  # noqa: SLF001 — vérifie le nom transmis
    assert captured["name"] == "small"


def test_estimate_cost_is_zero(tmp_path: Path) -> None:
    adapter = FasterWhisperAdapter(model_cache_dir=tmp_path, cuda_check=lambda: True)
    assert adapter.estimate_cost(duration_seconds=999.0) == 0.0


def test_transcribe_raises_when_no_cuda(tmp_path: Path) -> None:
    adapter = FasterWhisperAdapter(model_cache_dir=tmp_path, cuda_check=lambda: False)
    audio = tmp_path / "x.wav"
    audio.write_bytes(b"x")
    with pytest.raises(STTError) as exc_info:
        adapter.transcribe(audio)
    assert exc_info.value.code == "STT.GPU_UNAVAILABLE"


def test_transcribe_raises_when_model_load_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # On force le chargement à échouer en simulant une exception
    # via un répertoire de cache impossible à créer (mauvais chemin).
    adapter = FasterWhisperAdapter(
        model_cache_dir=tmp_path / "cache",
        cuda_check=lambda: True,
    )

    def _raise(*_: object, **__: object) -> object:
        raise RuntimeError("simulated model load failure")

    monkeypatch.setattr(faster_whisper, "WhisperModel", _raise)
    audio = tmp_path / "x.wav"
    audio.write_bytes(b"x")
    with pytest.raises(STTError) as exc_info:
        adapter.transcribe(audio)
    assert exc_info.value.code == "STT.MODEL_LOAD_FAILED"
