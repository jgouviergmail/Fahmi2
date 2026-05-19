"""Tests des entités Project, ProjectSettings, ParallelismConfig."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from fahmi2.domain.enums import Language, LLMModel, PhaseId, SttProvider, StylePreset
from fahmi2.domain.ids import ProjectId
from fahmi2.domain.phase import PhaseConfig
from fahmi2.domain.project import ParallelismConfig, Project, ProjectSettings


def _make_phases_config() -> dict[PhaseId, PhaseConfig]:
    return {pid: PhaseConfig() for pid in PhaseId if pid is not PhaseId.STT}


def _make_settings(**overrides: Any) -> ProjectSettings:
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
        "phases_config": _make_phases_config(),
        "cost_ceiling_usd": None,
        "parallelism": ParallelismConfig(),
        "delete_audio_after_stt": True,
    }
    base.update(overrides)
    return ProjectSettings(**base)


def test_parallelism_config_defaults() -> None:
    p = ParallelismConfig()
    assert p.stt_cloud_workers == 3
    assert p.llm_workers == 4


def test_parallelism_config_validates_positive() -> None:
    with pytest.raises(ValueError):
        ParallelismConfig(stt_cloud_workers=0)
    with pytest.raises(ValueError):
        ParallelismConfig(llm_workers=-1)


def test_settings_requires_source_in_output() -> None:
    with pytest.raises(ValueError):
        _make_settings(source_language=Language.FR, output_languages=(Language.EN,))


def test_settings_accepts_source_in_output() -> None:
    s = _make_settings(
        source_language=Language.FR, output_languages=(Language.FR, Language.EN)
    )
    assert Language.FR in s.output_languages


def test_settings_requires_at_least_one_output_language() -> None:
    with pytest.raises(ValueError):
        _make_settings(output_languages=())


def test_settings_requires_all_llm_phases_configured() -> None:
    incomplete = {PhaseId.TERM_EXTRACTION: PhaseConfig()}
    with pytest.raises(ValueError):
        _make_settings(phases_config=incomplete)


def test_settings_must_not_configure_stt_phase() -> None:
    invalid = {pid: PhaseConfig() for pid in PhaseId}
    with pytest.raises(ValueError):
        _make_settings(phases_config=invalid)


def test_settings_cost_ceiling_must_be_non_negative() -> None:
    with pytest.raises(ValueError):
        _make_settings(cost_ceiling_usd=-1.0)


def test_settings_cost_ceiling_zero_is_valid() -> None:
    s = _make_settings(cost_ceiling_usd=0.0)
    assert s.cost_ceiling_usd == 0.0


def test_project_minimal() -> None:
    pid = ProjectId.new()
    s = _make_settings()
    created = datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC)
    project = Project(id=pid, settings=s, created_at=created)
    assert project.id is pid
    assert project.settings is s
    assert project.created_at == created
    assert project.last_run_at is None
    assert project.runs == ()
