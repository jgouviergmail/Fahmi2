"""Smoke tests de VisualsProgressView."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fahmi2.domain.enums import Language
from fahmi2.ui.viewmodels.visuals_progress import VisualsProgressViewModel
from fahmi2.ui.viewmodels.visuals_state import VisualsState, VisualsStateInfo
from fahmi2.ui.visuals_labels import VisualsDeliverable
from fahmi2.ui.widgets.visuals_progress_view import VisualsProgressView


def _vm() -> VisualsProgressViewModel:
    vm = VisualsProgressViewModel()
    vm.reset(
        deliverables=(
            VisualsDeliverable.KNOWLEDGE_MAP,
            VisualsDeliverable.DIAGRAMS,
        ),
        languages=(Language.FR, Language.EN),
    )
    return vm


def test_apply_snapshot_fills_matrix(qtbot: QtBot) -> None:
    view = VisualsProgressView()
    qtbot.addWidget(view)
    vm = _vm()
    view.apply_snapshot(vm.cost_matrix_snapshot(), vm.stats_snapshot())
    assert view.row_count() == 2  # 2 livrables


def test_set_state_updates_banner(qtbot: QtBot) -> None:
    view = VisualsProgressView()
    qtbot.addWidget(view)
    view.set_state(
        VisualsStateInfo(
            state=VisualsState.READY, message="Prêt à générer.", can_generate=True
        )
    )
    assert "Prêt" in view.banner_text()


def test_clear_resets(qtbot: QtBot) -> None:
    view = VisualsProgressView()
    qtbot.addWidget(view)
    vm = _vm()
    view.apply_snapshot(vm.cost_matrix_snapshot(), vm.stats_snapshot())
    view.clear()
    assert view.row_count() == 0
    assert view.banner_text() == ""
