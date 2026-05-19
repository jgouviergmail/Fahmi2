"""Widget ``RunMatrixView`` — matrice vidéos × phases d'un Run.

Affiche un tableau ``Vidéo × Phase`` où chaque cellule porte un symbole et
une couleur de fond/police selon le statut. Le contenu reste piloté par un
``MatrixSnapshot`` immuable produit par ``RunMatrixViewModel``.
"""

from __future__ import annotations

from PySide6.QtCore import (
    QAbstractTableModel,
    QModelIndex,
    QPersistentModelIndex,
    Qt,
)
from PySide6.QtGui import QBrush, QColor, QFont
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

_STATUS_LABEL: dict[PhaseStatus, str] = {
    PhaseStatus.PENDING: "en attente",
    PhaseStatus.RUNNING: "en cours",
    PhaseStatus.SUCCEEDED: "terminé",
    PhaseStatus.FAILED: "échec",
    PhaseStatus.SKIPPED: "déjà fait",
}

# Couleurs (fond, texte) par statut — coordonnées avec le thème Clair Fluent
_STATUS_COLORS: dict[PhaseStatus, tuple[QColor, QColor]] = {
    PhaseStatus.PENDING: (QColor("#f8fafc"), QColor("#8b95a1")),
    PhaseStatus.RUNNING: (QColor("#e3f0fb"), QColor("#0a4f93")),
    PhaseStatus.SUCCEEDED: (QColor("#e6f6ec"), QColor("#1a7f37")),
    PhaseStatus.FAILED: (QColor("#fcebec"), QColor("#cf222e")),
    PhaseStatus.SKIPPED: (QColor("#f1eefb"), QColor("#5b4cc7")),
}

_VIDEO_COL_BG = QColor("#ffffff")
_VIDEO_COL_FG = QColor("#1f2328")


_PHASE_SHORT_LABELS: dict[str, str] = {
    "phase_0_stt": "STT",
    "phase_1_term_extraction": "Termes",
    "phase_2_glossary_reconciliation": "Glossaire",
    "phase_3_reformulation": "Reformul.",
    "phase_4_structuration": "Structur.",
    "phase_5_consolidation": "Consolid.",
    "phase_6_translation": "Traduction",
    "phase_7_coherence": "Cohérence",
}


def _short_phase_label(phase_value: str) -> str:
    """Retourne un libellé court pour l'en-tête de colonne.

    Args:
        phase_value: Valeur brute de la phase (``phase_3_reformulation``…).

    Returns:
        Libellé compact pour l'en-tête, ou la valeur d'origine en fallback.
    """
    return _PHASE_SHORT_LABELS.get(phase_value, phase_value)


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
            return _short_phase_label(
                self._snapshot.phases_in_order[phase_index].value
            )
        return section + 1

    def data(  # noqa: PLR0911, C901
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

        if role == Qt.ItemDataRole.TextAlignmentRole:
            if col_idx == 0:
                return int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            return int(Qt.AlignmentFlag.AlignCenter)

        if role == Qt.ItemDataRole.BackgroundRole:
            if col_idx == 0:
                return QBrush(_VIDEO_COL_BG)
            phase_id = self._snapshot.phases_in_order[col_idx - 1]
            bg, _ = _STATUS_COLORS.get(
                row.cells[phase_id].status, (_VIDEO_COL_BG, _VIDEO_COL_FG)
            )
            return QBrush(bg)

        if role == Qt.ItemDataRole.ForegroundRole:
            if col_idx == 0:
                return QBrush(_VIDEO_COL_FG)
            phase_id = self._snapshot.phases_in_order[col_idx - 1]
            _, fg = _STATUS_COLORS.get(
                row.cells[phase_id].status, (_VIDEO_COL_BG, _VIDEO_COL_FG)
            )
            return QBrush(fg)

        if role == Qt.ItemDataRole.FontRole and col_idx > 0:
            font = QFont()
            font.setPointSize(11)
            font.setBold(True)
            return font

        if role == Qt.ItemDataRole.ToolTipRole and col_idx > 0:
            phase_id = self._snapshot.phases_in_order[col_idx - 1]
            cell = row.cells[phase_id]
            label = _STATUS_LABEL.get(cell.status, cell.status.value)
            return (
                f"{phase_id.value} — {label}"
                f" — retries: {cell.retry_count} — coût: ${cell.cost_usd:.4f}"
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
        self.setObjectName("runMatrix")
        self._model = _RunMatrixModel(snapshot or _empty_snapshot())
        self.setModel(self._model)
        self.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        self.setShowGrid(False)
        self.setAlternatingRowColors(False)
        v_header = self.verticalHeader()
        if v_header is not None:
            v_header.setVisible(False)
            v_header.setDefaultSectionSize(32)
        header = self.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)

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
