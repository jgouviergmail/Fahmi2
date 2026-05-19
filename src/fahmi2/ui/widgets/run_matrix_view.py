"""Widget ``RunMatrixView`` — matrice vidéos × phases d'un Run."""

from __future__ import annotations

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QPersistentModelIndex,
    Qt,
)
from PySide6.QtWidgets import QHeaderView, QTableView, QWidget

from fahmi2.domain.enums import PhaseStatus
from fahmi2.domain.ids import RunId
from fahmi2.ui.viewmodels.run_matrix import MatrixSnapshot

_STATUS_SYMBOLS: dict[PhaseStatus, str] = {
    PhaseStatus.PENDING: "·",
    PhaseStatus.RUNNING: "▶",
    PhaseStatus.SUCCEEDED: "✓",
    PhaseStatus.FAILED: "✗",
    PhaseStatus.SKIPPED: "↷",
}


class _RunMatrixModel(QAbstractTableModel):
    """``QAbstractTableModel`` adossé à un ``MatrixSnapshot``."""

    def __init__(self, snapshot: MatrixSnapshot) -> None:
        super().__init__()
        self._snapshot = snapshot

    def set_snapshot(self, snapshot: MatrixSnapshot) -> None:
        """Remplace le snapshot et notifie la vue.

        Args:
            snapshot: Nouveau snapshot.
        """
        self.beginResetModel()
        self._snapshot = snapshot
        self.endResetModel()

    def rowCount(  # noqa: N802
        self, parent: QModelIndex | QPersistentModelIndex | None = None
    ) -> int:
        if parent is not None and parent.isValid():
            return 0
        return len(self._snapshot.rows)

    def columnCount(  # noqa: N802
        self, parent: QModelIndex | QPersistentModelIndex | None = None
    ) -> int:
        if parent is not None and parent.isValid():
            return 0
        # Colonne 0 = nom de la vidéo
        return 1 + len(self._snapshot.phases_in_order)

    def headerData(  # noqa: N802
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> object:
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation is Qt.Orientation.Horizontal:
            if section == 0:
                return "Vidéo"
            phase_index = section - 1
            return self._snapshot.phases_in_order[phase_index].value
        return section + 1

    def data(
        self,
        index: QModelIndex | QPersistentModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> object:
        if not index.isValid():
            return None
        row_idx = index.row()
        col_idx = index.column()
        row = self._snapshot.rows[row_idx]
        if role == Qt.ItemDataRole.DisplayRole:
            if col_idx == 0:
                return row.video_label
            phase_id = self._snapshot.phases_in_order[col_idx - 1]
            cell = row.cells[phase_id]
            return _STATUS_SYMBOLS.get(cell.status, "?")
        if role == Qt.ItemDataRole.ToolTipRole:
            if col_idx > 0:
                phase_id = self._snapshot.phases_in_order[col_idx - 1]
                cell = row.cells[phase_id]
                return (
                    f"{phase_id.value} — statut: {cell.status.value} "
                    f"— retries: {cell.retry_count} — coût: ${cell.cost_usd:.4f}"
                )
        return None


class RunMatrixView(QTableView):
    """Vue ``QTableView`` affichant la matrice vidéos × phases du Run."""

    def __init__(
        self, snapshot: MatrixSnapshot | None = None, parent: QWidget | None = None
    ) -> None:
        """Construit la vue.

        Args:
            snapshot: Snapshot initial (peut être ``None``).
            parent: Parent Qt optionnel.
        """
        super().__init__(parent)
        self._model = _RunMatrixModel(snapshot or _empty_snapshot())
        self.setModel(self._model)
        self.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        header = self.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)

    def apply_snapshot(self, snapshot: MatrixSnapshot) -> None:
        """Applique un nouveau snapshot.

        Args:
            snapshot: Nouveau snapshot.
        """
        self._model.set_snapshot(snapshot)


def _empty_snapshot() -> MatrixSnapshot:
    """Construit un snapshot vide (utile pour l'initialisation).

    Returns:
        Snapshot vide (pas de rows, pas de phases).
    """
    return MatrixSnapshot(run_id=RunId.new(), phases_in_order=(), rows=())
