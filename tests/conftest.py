"""Pytest fixtures globales pour Fahmi2."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from fahmi2.domain.enums import (
    Language,
    LLMModel,
    PhaseId,
    SttProvider,
    StylePreset,
)
from fahmi2.domain.phase import PhaseConfig
from fahmi2.domain.project import ParallelismConfig, ProjectSettings


@pytest.fixture
def make_settings() -> Any:
    """Retourne une fonction de fabrication de ``ProjectSettings`` valides.

    Utilisée par les tests de domain et plus tard d'application pour produire
    des settings cohérents sans dupliquer le boilerplate ``ProjectSettings``.

    Returns:
        Une fonction prenant des kwargs de surcharge et retournant un
        ``ProjectSettings`` validé.
    """

    def _factory(**overrides: Any) -> ProjectSettings:
        base: dict[str, Any] = {
            "name": "Test Project",
            "input_folder": Path("./input"),
            "workspace_folder": Path("./workspace"),
            "source_language": Language.FR,
            "output_languages": (Language.FR,),
            "style_preset": StylePreset.STANDARD,
            "style_directives": "",
            "stt_provider": SttProvider.OPENAI_CLOUD,
            "llm_model": LLMModel.DEEPSEEK_V4_FLASH,
            "phases_config": {
                pid: PhaseConfig() for pid in PhaseId if pid is not PhaseId.STT
            },
            "cost_ceiling_usd": None,
            "parallelism": ParallelismConfig(),
            "delete_audio_after_stt": True,
        }
        base.update(overrides)
        return ProjectSettings(**base)

    return _factory
