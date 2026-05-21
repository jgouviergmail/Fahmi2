"""Tests des libellés et accents de statut partagés (dashboards)."""

from __future__ import annotations

from fahmi2.domain.enums import RunStatus
from fahmi2.ui.status_labels import (
    ACCENT_NEUTRAL,
    cost_accent,
    run_status_accent,
    run_status_icon,
    run_status_label,
)


def test_run_status_icon_per_status() -> None:
    # Chaque statut a un glyphe distinct (pas le repli) ; tous différents.
    icons = {run_status_icon(s) for s in RunStatus}
    assert len(icons) == len(list(RunStatus))
    assert run_status_icon(RunStatus.COMPLETED) == "✓"
    assert run_status_icon(RunStatus.RUNNING) == "▶"


def test_run_status_label_known() -> None:
    assert run_status_label(RunStatus.COMPLETED) == "Terminé"
    assert run_status_label(RunStatus.RUNNING) == "En cours"


def test_run_status_accent_mapping() -> None:
    assert run_status_accent(RunStatus.RUNNING) == "running"
    assert run_status_accent(RunStatus.PAUSED) == "warning"
    assert run_status_accent(RunStatus.COMPLETED) == "success"
    assert run_status_accent(RunStatus.FAILED) == "danger"
    assert run_status_accent(RunStatus.CANCELLED) == "danger"
    # Statut sans accent dédié -> neutre.
    assert run_status_accent(RunStatus.CREATED) == ACCENT_NEUTRAL


def test_cost_accent_thresholds() -> None:
    assert cost_accent(0.5, None) == ACCENT_NEUTRAL  # pas de plafond
    assert cost_accent(0.5, 0.0) == ACCENT_NEUTRAL  # plafond nul ignoré
    assert cost_accent(0.5, 2.0) == ACCENT_NEUTRAL  # 25 %
    assert cost_accent(1.7, 2.0) == "warning"  # 85 % (> 80 %)
    assert cost_accent(2.0, 2.0) == "danger"  # 100 %
    assert cost_accent(3.0, 2.0) == "danger"  # dépassement
