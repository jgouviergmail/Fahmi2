"""Tests des validateurs de transitions d'état."""

import pytest

from fahmi2.domain.enums import PhaseStatus, RunStatus
from fahmi2.domain.state_machine import (
    InvalidTransitionError,
    can_transition_phase,
    can_transition_run,
    validate_transition_phase,
    validate_transition_run,
)


@pytest.mark.parametrize(
    ("from_s", "to_s", "expected"),
    [
        (RunStatus.CREATED, RunStatus.RUNNING, True),
        (RunStatus.CREATED, RunStatus.PAUSED, False),
        (RunStatus.RUNNING, RunStatus.PAUSED, True),
        (RunStatus.RUNNING, RunStatus.COMPLETED, True),
        (RunStatus.RUNNING, RunStatus.CANCELLED, True),
        (RunStatus.RUNNING, RunStatus.FAILED, True),
        (RunStatus.RUNNING, RunStatus.CREATED, False),
        (RunStatus.PAUSED, RunStatus.RUNNING, True),
        (RunStatus.PAUSED, RunStatus.CANCELLED, True),
        (RunStatus.PAUSED, RunStatus.COMPLETED, False),
        (RunStatus.COMPLETED, RunStatus.RUNNING, False),
        (RunStatus.CANCELLED, RunStatus.RUNNING, False),
        (RunStatus.FAILED, RunStatus.RUNNING, False),
        (RunStatus.RUNNING, RunStatus.RUNNING, False),
    ],
)
def test_run_transitions(from_s: RunStatus, to_s: RunStatus, expected: bool) -> None:
    assert can_transition_run(from_s, to_s) is expected


def test_validate_run_raises_on_invalid() -> None:
    with pytest.raises(InvalidTransitionError):
        validate_transition_run(RunStatus.COMPLETED, RunStatus.RUNNING)


def test_validate_run_passes_on_valid() -> None:
    validate_transition_run(RunStatus.CREATED, RunStatus.RUNNING)


@pytest.mark.parametrize(
    ("from_s", "to_s", "expected"),
    [
        (PhaseStatus.PENDING, PhaseStatus.RUNNING, True),
        (PhaseStatus.PENDING, PhaseStatus.SKIPPED, True),
        (PhaseStatus.PENDING, PhaseStatus.SUCCEEDED, False),
        (PhaseStatus.RUNNING, PhaseStatus.SUCCEEDED, True),
        (PhaseStatus.RUNNING, PhaseStatus.FAILED, True),
        (PhaseStatus.RUNNING, PhaseStatus.SKIPPED, False),
        (PhaseStatus.FAILED, PhaseStatus.RUNNING, True),
        (PhaseStatus.SUCCEEDED, PhaseStatus.RUNNING, False),
        (PhaseStatus.SKIPPED, PhaseStatus.RUNNING, False),
    ],
)
def test_phase_transitions(
    from_s: PhaseStatus, to_s: PhaseStatus, expected: bool
) -> None:
    assert can_transition_phase(from_s, to_s) is expected


def test_validate_phase_raises_on_invalid() -> None:
    with pytest.raises(InvalidTransitionError):
        validate_transition_phase(PhaseStatus.SUCCEEDED, PhaseStatus.RUNNING)


def test_validate_phase_passes_on_valid() -> None:
    validate_transition_phase(PhaseStatus.PENDING, PhaseStatus.RUNNING)
