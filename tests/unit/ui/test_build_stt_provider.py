"""Tests de build_stt_provider (construction + injection préparateur)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from fahmi2.core.errors.exceptions import ConfigError
from fahmi2.domain.enums import SttProvider
from fahmi2.infra.stt.faster_whisper_adapter import FasterWhisperAdapter
from fahmi2.infra.stt.openai_whisper_adapter import OpenAIWhisperAdapter
from fahmi2.ui.generation_controller import build_stt_provider


def test_cloud_provider_has_preparer(make_generation_settings: Any) -> None:
    gen = make_generation_settings(stt_provider=SttProvider.OPENAI_CLOUD)
    provider = build_stt_provider(
        settings=gen, openai_api_key="dummy", models_dir=Path("models")
    )
    assert isinstance(provider, OpenAIWhisperAdapter)
    assert provider._preparer is not None  # noqa: SLF001 — anti-régression DI


def test_local_provider_is_faster_whisper(make_generation_settings: Any) -> None:
    gen = make_generation_settings(stt_provider=SttProvider.FASTER_WHISPER_LOCAL)
    provider = build_stt_provider(
        settings=gen, openai_api_key=None, models_dir=Path("models")
    )
    assert isinstance(provider, FasterWhisperAdapter)


def test_cloud_without_key_raises(make_generation_settings: Any) -> None:
    gen = make_generation_settings(stt_provider=SttProvider.OPENAI_CLOUD)
    with pytest.raises(ConfigError):
        build_stt_provider(settings=gen, openai_api_key=None, models_dir=Path("m"))
