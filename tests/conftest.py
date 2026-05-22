"""Pytest fixtures globales pour Fahmi2."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from fahmi2.domain.enums import (
    BloomObjective,
    ExportFormat,
    Language,
    LLMModel,
    PhaseId,
    SttProvider,
    StylePreset,
    SupportDensity,
    SupportType,
    TargetAudience,
)
from fahmi2.domain.generation import GenerationSettings, ParallelismConfig
from fahmi2.domain.ids import ProjectId
from fahmi2.domain.pedagogy import PedagogySettings
from fahmi2.domain.phase import PhaseConfig
from fahmi2.domain.project import Project


@pytest.fixture
def make_generation_settings() -> Any:
    """Fabrique des ``GenerationSettings`` valides (kwargs de surcharge).

    Returns:
        Fonction renvoyant un ``GenerationSettings`` validé.
    """

    def _factory(**overrides: Any) -> GenerationSettings:
        base: dict[str, Any] = {
            "input_folder": Path("./input"),
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
            "export_formats": frozenset(),
        }
        base.update(overrides)
        return GenerationSettings(**base)

    return _factory


@pytest.fixture
def make_project(make_generation_settings: Any) -> Any:
    """Fabrique un ``Project`` minimal valide (kwargs de surcharge).

    Args:
        make_generation_settings: Fixture de fabrication des réglages génération.

    Returns:
        Fonction renvoyant un ``Project`` (avec ``generation`` par défaut).
    """

    def _factory(**overrides: Any) -> Project:
        base: dict[str, Any] = {
            "id": ProjectId.new(),
            "name": "Test Project",
            "workspace_folder": Path("./workspace"),
            "created_at": datetime.now(tz=UTC),
            "generation": make_generation_settings(),
        }
        base.update(overrides)
        return Project(**base)

    return _factory


@pytest.fixture
def make_pedagogy_settings() -> Any:
    """Fabrique des ``PedagogySettings`` valides (kwargs de surcharge).

    Returns:
        Fonction renvoyant un ``PedagogySettings`` validé.
    """

    def _factory(**overrides: Any) -> PedagogySettings:
        base: dict[str, Any] = {
            "selected_supports": frozenset({SupportType.FLASHCARDS_CONCEPTS}),
            "separate_correction": frozenset(),
            "target_audience": TargetAudience.LICENCE,
            "bloom_objective": BloomObjective.AUTO,
            "pedagogy_directives": "",
            "languages": (Language.FR,),
            "density": SupportDensity.STANDARD,
            "llm_model": LLMModel.DEEPSEEK_V4_FLASH,
            "llm_config": PhaseConfig(),
            "cost_ceiling_usd": None,
            "export_formats": frozenset({ExportFormat.APKG}),
        }
        base.update(overrides)
        return PedagogySettings(**base)

    return _factory
