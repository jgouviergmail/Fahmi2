"""Smoke tests du widget CostMatrixView."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fahmi2.domain.enums import PhaseStatus
from fahmi2.ui.viewmodels.cost_matrix import CostMatrixCell, build_cost_matrix
from fahmi2.ui.widgets.cost_matrix_view import CostMatrixView


def _snapshot() -> object:
    return build_cost_matrix(
        row_header="Support",
        column_labels=("FR", "EN"),
        rows=(
            (
                "QCM",
                (
                    CostMatrixCell(PhaseStatus.SUCCEEDED, 0.10, "ok"),
                    CostMatrixCell(PhaseStatus.PENDING, None, "attente"),
                ),
            ),
        ),
    )


def test_view_dimensions(qtbot: QtBot) -> None:
    view = CostMatrixView()
    qtbot.addWidget(view)
    view.apply_snapshot(_snapshot())  # type: ignore[arg-type]
    model = view.model()
    assert model is not None
    # 1 ligne data + 1 ligne Total
    assert model.rowCount() == 2
    # colonne libellé + 2 colonnes data + colonne Total
    assert model.columnCount() == 4


def test_empty_view_does_not_crash(qtbot: QtBot) -> None:
    view = CostMatrixView()
    qtbot.addWidget(view)
    assert view.model() is not None
