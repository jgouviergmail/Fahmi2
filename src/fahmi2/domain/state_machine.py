"""Validateurs de transitions d'état pour ``Run`` et ``Phase``."""

from __future__ import annotations

from fahmi2.domain.enums import PhaseStatus, RunStatus


class InvalidTransitionError(ValueError):
    """Levée lors d'une tentative de transition d'état invalide."""


_RUN_TRANSITIONS: dict[RunStatus, frozenset[RunStatus]] = {
    RunStatus.CREATED: frozenset({RunStatus.RUNNING}),
    RunStatus.RUNNING: frozenset(
        {
            RunStatus.RUNNING,  # idempotent (héritage crash app)
            RunStatus.PAUSED,
            RunStatus.CANCELLED,
            RunStatus.COMPLETED,
            RunStatus.FAILED,
        }
    ),
    RunStatus.PAUSED: frozenset({RunStatus.RUNNING, RunStatus.CANCELLED}),
    # FAILED -> RUNNING permet la reprise après une erreur de phase : le
    # PipelineEngine skippera automatiquement les phases déjà SUCCEEDED et
    # réessaiera la phase qui a planté (et celles suivantes).
    RunStatus.FAILED: frozenset({RunStatus.RUNNING}),
    RunStatus.CANCELLED: frozenset(),
    RunStatus.COMPLETED: frozenset(),
}


_PHASE_TRANSITIONS: dict[PhaseStatus, frozenset[PhaseStatus]] = {
    PhaseStatus.PENDING: frozenset({PhaseStatus.RUNNING, PhaseStatus.SKIPPED}),
    PhaseStatus.RUNNING: frozenset({PhaseStatus.SUCCEEDED, PhaseStatus.FAILED}),
    PhaseStatus.FAILED: frozenset({PhaseStatus.RUNNING}),
    PhaseStatus.SUCCEEDED: frozenset(),
    PhaseStatus.SKIPPED: frozenset(),
}


def can_transition_run(from_status: RunStatus, to_status: RunStatus) -> bool:
    """Indique si la transition de ``Run`` est autorisée.

    Args:
        from_status: État de départ.
        to_status: État cible.

    Returns:
        ``True`` si autorisée, ``False`` sinon.
    """
    return to_status in _RUN_TRANSITIONS.get(from_status, frozenset())


def validate_transition_run(from_status: RunStatus, to_status: RunStatus) -> None:
    """Valide la transition ``Run`` ou lève ``InvalidTransitionError``.

    Args:
        from_status: État de départ.
        to_status: État cible.

    Raises:
        InvalidTransitionError: Si la transition n'est pas autorisée.
    """
    if not can_transition_run(from_status, to_status):
        raise InvalidTransitionError(
            f"Invalid Run transition {from_status} -> {to_status}"
        )


def can_transition_phase(from_status: PhaseStatus, to_status: PhaseStatus) -> bool:
    """Indique si la transition de ``Phase`` est autorisée.

    Args:
        from_status: État de départ.
        to_status: État cible.

    Returns:
        ``True`` si autorisée, ``False`` sinon.
    """
    return to_status in _PHASE_TRANSITIONS.get(from_status, frozenset())


def validate_transition_phase(from_status: PhaseStatus, to_status: PhaseStatus) -> None:
    """Valide la transition ``Phase`` ou lève ``InvalidTransitionError``.

    Args:
        from_status: État de départ.
        to_status: État cible.

    Raises:
        InvalidTransitionError: Si la transition n'est pas autorisée.
    """
    if not can_transition_phase(from_status, to_status):
        raise InvalidTransitionError(
            f"Invalid Phase transition {from_status} -> {to_status}"
        )
