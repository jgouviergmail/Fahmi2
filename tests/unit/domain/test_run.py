"""Tests de l'entité Run."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fahmi2.domain.enums import (
    Language,
    LLMModel,
    PhaseId,
    PhaseStatus,
    RunStatus,
    SttProvider,
    StylePreset,
)
from fahmi2.domain.ids import ProjectId, RunId
from fahmi2.domain.phase import PhaseConfig, PhaseExecution
from fahmi2.domain.project import ParallelismConfig, ProjectSettings
from fahmi2.domain.run import Run


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
        "phases_config": {pid: PhaseConfig() for pid in PhaseId if pid is not PhaseId.STT},
        "cost_ceiling_usd": None,
        "parallelism": ParallelismConfig(),
        "delete_audio_after_stt": True,
    }
    base.update(overrides)
    return ProjectSettings(**base)


def test_run_minimal() -> None:
    rid = RunId.new()
    pid = ProjectId.new()
    started = datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC)
    settings = _make_settings()
    run = Run(
        id=rid,
        project_id=pid,
        started_at=started,
        status=RunStatus.CREATED,
        settings_snapshot=settings,
    )
    assert run.id is rid
    assert run.project_id is pid
    assert run.started_at == started
    assert run.finished_at is None
    assert run.status is RunStatus.CREATED
    assert run.cost_usd == 0.0
    assert run.videos == ()
    assert run.phase_executions == {}


def test_run_with_videos_and_phases() -> None:
    pe = PhaseExecution(
        phase_id=PhaseId.GLOSSARY_RECONCILIATION, status=PhaseStatus.SUCCEEDED
    )
    run = Run(
        id=RunId.new(),
        project_id=ProjectId.new(),
        started_at=datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC),
        status=RunStatus.RUNNING,
        settings_snapshot=_make_settings(),
        cost_usd=1.5,
        phase_executions={PhaseId.GLOSSARY_RECONCILIATION: pe},
    )
    assert run.cost_usd == 1.5
    assert run.phase_executions[PhaseId.GLOSSARY_RECONCILIATION] is pe


def test_run_with_status_returns_new_instance() -> None:
    run = Run(
        id=RunId.new(),
        project_id=ProjectId.new(),
        started_at=datetime.now(tz=UTC),
        status=RunStatus.CREATED,
        settings_snapshot=_make_settings(),
    )
    new = run.with_status(RunStatus.RUNNING)
    assert new is not run
    assert new.status is RunStatus.RUNNING
    assert run.status is RunStatus.CREATED


def test_run_with_added_cost() -> None:
    run = Run(
        id=RunId.new(),
        project_id=ProjectId.new(),
        started_at=datetime.now(tz=UTC),
        status=RunStatus.RUNNING,
        settings_snapshot=_make_settings(),
        cost_usd=1.0,
    )
    new = run.with_added_cost(0.5)
    assert new.cost_usd == 1.5
    assert run.cost_usd == 1.0


def test_run_with_finished_at() -> None:
    run = Run(
        id=RunId.new(),
        project_id=ProjectId.new(),
        started_at=datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC),
        status=RunStatus.RUNNING,
        settings_snapshot=_make_settings(),
    )
    finished = datetime(2026, 5, 19, 14, 30, 0, tzinfo=UTC)
    new = run.with_finished_at(finished)
    assert new.finished_at == finished
    assert run.finished_at is None
