"""Smoke tests de PedagogyProgressView."""

from __future__ import annotations

from fahmi2.domain.enums import Language, PhaseStatus, RunStatus, SupportType
from fahmi2.ui.viewmodels.pedagogy_progress import (
    PedagogyProgressCell,
    PedagogyProgressSnapshot,
)
from fahmi2.ui.viewmodels.pedagogy_state import PedagogyState, PedagogyStateInfo
from fahmi2.ui.widgets.pedagogy_progress_view import PedagogyProgressView


def test_apply_snapshot_fills_rows(qtbot):  # type: ignore[no-untyped-def]
    view = PedagogyProgressView()
    qtbot.addWidget(view)
    snapshot = PedagogyProgressSnapshot(
        cells=(
            PedagogyProgressCell(
                support_type=SupportType.QCM,
                language=Language.FR,
                status=PhaseStatus.SUCCEEDED,
                cost_usd=0.12,
            ),
            PedagogyProgressCell(
                support_type=SupportType.KEY_POINTS,
                language=Language.FR,
                status=None,
                cost_usd=0.0,
            ),
        ),
        overall_status=RunStatus.COMPLETED,
        total_cost_usd=0.12,
    )
    view.apply_snapshot(snapshot)
    assert view.row_count() == 2


def test_set_state_updates_banner(qtbot):  # type: ignore[no-untyped-def]
    view = PedagogyProgressView()
    qtbot.addWidget(view)
    view.set_state(
        PedagogyStateInfo(
            state=PedagogyState.READY, message="Prêt à générer.", can_generate=True
        )
    )
    assert "Prêt" in view.banner_text()
