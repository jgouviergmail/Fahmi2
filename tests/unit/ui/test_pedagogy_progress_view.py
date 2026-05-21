"""Smoke tests de PedagogyProgressView."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fahmi2.domain.enums import Language, SupportType
from fahmi2.ui.viewmodels.pedagogy_progress import PedagogyProgressViewModel
from fahmi2.ui.viewmodels.pedagogy_state import PedagogyState, PedagogyStateInfo
from fahmi2.ui.widgets.pedagogy_progress_view import PedagogyProgressView


def _vm() -> PedagogyProgressViewModel:
    vm = PedagogyProgressViewModel()
    vm.reset(
        supports=(SupportType.QCM, SupportType.KEY_POINTS),
        languages=(Language.FR,),
    )
    return vm


def test_apply_snapshot_fills_matrix(qtbot: QtBot) -> None:
    view = PedagogyProgressView()
    qtbot.addWidget(view)
    vm = _vm()
    view.apply_snapshot(vm.cost_matrix_snapshot(), vm.stats_snapshot())
    assert view.row_count() == 2  # 2 supports


def test_set_state_updates_banner(qtbot: QtBot) -> None:
    view = PedagogyProgressView()
    qtbot.addWidget(view)
    view.set_state(
        PedagogyStateInfo(
            state=PedagogyState.READY, message="Prêt à générer.", can_generate=True
        )
    )
    assert "Prêt" in view.banner_text()


def test_clear_resets(qtbot: QtBot) -> None:
    view = PedagogyProgressView()
    qtbot.addWidget(view)
    vm = _vm()
    view.apply_snapshot(vm.cost_matrix_snapshot(), vm.stats_snapshot())
    view.clear()
    assert view.row_count() == 0
    assert view.banner_text() == ""
