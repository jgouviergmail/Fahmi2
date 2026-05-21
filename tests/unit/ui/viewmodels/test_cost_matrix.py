"""Tests du viewmodel générique de matrice de coût."""

from __future__ import annotations

import pytest

from fahmi2.domain.enums import PhaseStatus
from fahmi2.ui.viewmodels.cost_matrix import (
    CostMatrixCell,
    build_cost_matrix,
)


def _cell(status: PhaseStatus, cost: float | None) -> CostMatrixCell:
    return CostMatrixCell(status=status, cost_usd=cost, tooltip="")


def test_build_computes_totals() -> None:
    snap = build_cost_matrix(
        row_header="Support",
        column_labels=("FR", "EN"),
        rows=(
            (
                "QCM",
                (_cell(PhaseStatus.SUCCEEDED, 0.10), _cell(PhaseStatus.RUNNING, None)),
            ),
            (
                "Cloze",
                (
                    _cell(PhaseStatus.SUCCEEDED, 0.05),
                    _cell(PhaseStatus.SUCCEEDED, 0.07),
                ),
            ),
        ),
    )
    assert snap.row_labels == ("QCM", "Cloze")
    assert snap.row_totals == pytest.approx((0.10, 0.12))
    assert snap.column_totals == pytest.approx((0.15, 0.07))
    assert snap.grand_total == pytest.approx(0.22)


def test_none_costs_count_as_zero() -> None:
    snap = build_cost_matrix(
        row_header="Vidéo",
        column_labels=("STT",),
        rows=(("v1", (_cell(PhaseStatus.PENDING, None),)),),
    )
    assert snap.row_totals == (0.0,)
    assert snap.grand_total == 0.0


def test_empty_matrix() -> None:
    snap = build_cost_matrix(row_header="X", column_labels=("A",), rows=())
    assert snap.row_labels == ()
    assert snap.column_totals == (0.0,)
    assert snap.grand_total == 0.0


def test_row_with_wrong_cell_count_raises() -> None:
    with pytest.raises(ValueError, match="cell count"):
        build_cost_matrix(
            row_header="X",
            column_labels=("A", "B"),
            rows=(("r", (_cell(PhaseStatus.PENDING, None),)),),
        )
