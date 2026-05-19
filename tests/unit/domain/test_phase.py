"""Tests des entités PhaseConfig et PhaseExecution."""

from datetime import UTC, datetime

import pytest

from fahmi2.core.errors.error_info import ErrorInfo
from fahmi2.core.errors.severity import Severity
from fahmi2.domain.enums import PhaseId, PhaseStatus, ReasoningEffort
from fahmi2.domain.phase import PhaseConfig, PhaseExecution


def test_phase_config_defaults() -> None:
    cfg = PhaseConfig()
    assert cfg.thinking_enabled is False
    assert cfg.reasoning_effort is None
    assert cfg.temperature == 0.3
    assert cfg.max_retries == 5


def test_phase_config_with_reasoning_effort() -> None:
    cfg = PhaseConfig(thinking_enabled=True, reasoning_effort=ReasoningEffort.MAX)
    assert cfg.thinking_enabled is True
    assert cfg.reasoning_effort is ReasoningEffort.MAX


def test_phase_config_validates_temperature() -> None:
    with pytest.raises(ValueError):
        PhaseConfig(temperature=-0.1)
    with pytest.raises(ValueError):
        PhaseConfig(temperature=2.1)


def test_phase_config_validates_max_retries() -> None:
    with pytest.raises(ValueError):
        PhaseConfig(max_retries=-1)


def test_phase_execution_minimal() -> None:
    ex = PhaseExecution(phase_id=PhaseId.STT, status=PhaseStatus.PENDING)
    assert ex.phase_id is PhaseId.STT
    assert ex.status is PhaseStatus.PENDING
    assert ex.started_at is None
    assert ex.finished_at is None
    assert ex.artifact_path is None
    assert ex.retry_count == 0
    assert ex.cost_usd == 0.0
    assert ex.error is None


def test_phase_execution_with_full_state() -> None:
    info = ErrorInfo(code="X", user_message="oups", severity=Severity.ERROR)
    started = datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC)
    finished = datetime(2026, 5, 19, 12, 0, 5, tzinfo=UTC)
    ex = PhaseExecution(
        phase_id=PhaseId.REFORMULATION,
        status=PhaseStatus.FAILED,
        started_at=started,
        finished_at=finished,
        retry_count=3,
        cost_usd=0.42,
        error=info,
    )
    assert ex.status is PhaseStatus.FAILED
    assert ex.retry_count == 3
    assert ex.cost_usd == 0.42
    assert ex.error is info


def test_phase_execution_with_status_returns_new() -> None:
    ex = PhaseExecution(phase_id=PhaseId.STT, status=PhaseStatus.PENDING)
    new = ex.with_status(PhaseStatus.RUNNING)
    assert new is not ex
    assert new.status is PhaseStatus.RUNNING
    assert ex.status is PhaseStatus.PENDING
