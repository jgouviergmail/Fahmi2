"""Tests des entités Project, ProjectSettings, ParallelismConfig."""

from datetime import UTC, datetime
from typing import Any

import pytest

from fahmi2.domain.enums import Language, PhaseId
from fahmi2.domain.ids import ProjectId
from fahmi2.domain.phase import PhaseConfig
from fahmi2.domain.project import ParallelismConfig, Project


def test_parallelism_config_defaults() -> None:
    p = ParallelismConfig()
    assert p.stt_cloud_workers == 3
    assert p.llm_workers == 4


def test_parallelism_config_validates_positive() -> None:
    with pytest.raises(ValueError):
        ParallelismConfig(stt_cloud_workers=0)
    with pytest.raises(ValueError):
        ParallelismConfig(llm_workers=-1)


def test_settings_requires_source_in_output(make_settings: Any) -> None:
    with pytest.raises(ValueError):
        make_settings(source_language=Language.FR, output_languages=(Language.EN,))


def test_settings_accepts_source_in_output(make_settings: Any) -> None:
    s = make_settings(
        source_language=Language.FR, output_languages=(Language.FR, Language.EN)
    )
    assert Language.FR in s.output_languages


def test_settings_requires_at_least_one_output_language(make_settings: Any) -> None:
    with pytest.raises(ValueError):
        make_settings(output_languages=())


def test_settings_requires_all_llm_phases_configured(make_settings: Any) -> None:
    incomplete = {PhaseId.TERM_EXTRACTION: PhaseConfig()}
    with pytest.raises(ValueError):
        make_settings(phases_config=incomplete)


def test_settings_must_not_configure_stt_phase(make_settings: Any) -> None:
    invalid = {pid: PhaseConfig() for pid in PhaseId}
    with pytest.raises(ValueError):
        make_settings(phases_config=invalid)


def test_settings_cost_ceiling_must_be_non_negative(make_settings: Any) -> None:
    with pytest.raises(ValueError):
        make_settings(cost_ceiling_usd=-1.0)


def test_settings_cost_ceiling_zero_is_valid(make_settings: Any) -> None:
    s = make_settings(cost_ceiling_usd=0.0)
    assert s.cost_ceiling_usd == 0.0


def test_project_minimal(make_settings: Any) -> None:
    pid = ProjectId.new()
    s = make_settings()
    created = datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC)
    project = Project(id=pid, settings=s, created_at=created)
    assert project.id is pid
    assert project.settings is s
    assert project.created_at == created
    assert project.last_run_at is None
    assert project.runs == ()
