"""Widget ``CostMatrixView`` — matrice de coût générique (statut + coût + totaux).

``QTableView`` + ``QAbstractTableModel`` piloté par un ``CostMatrixSnapshot``.
Chaque cellule de données est peinte par ``_CostCellDelegate`` : glyphe de statut
proéminent (couleur du statut) + coût en secondaire (petit, gris). La dernière
colonne et la dernière ligne portent les totaux (mis en avant). Réutilisé par les
dashboards Génération et Pédagogie (axes injectés via le snapshot).
"""

from __future__ import annotations

from PySide6.QtCore import (
    QAbstractTableModel,
    QCoreApplication,
    QModelIndex,
    QPersistentModelIndex,
    QRect,
    Qt,
)
from PySide6.QtGui import QBrush, QColor, QFont, QPainter
from PySide6.QtWidgets import (
    QHeaderView,
    QStyledItemDelegate,
    QStyleOptionViewItem,
    QTableView,
    QWidget,
)

from fahmi2.domain.enums import PhaseStatus
from fahmi2.ui.theme._tokens import TokenPalette, current_palette
from fahmi2.ui.viewmodels.cost_matrix import CostMatrixCell, CostMatrixSnapshot

_COST_DECIMALS = 4
_CELL_ROLE = int(Qt.ItemDataRole.UserRole) + 1


def _total_header() -> str:
    """Libellé traduit de l'en-tête / ligne « Total » de la matrice."""
    return QCoreApplication.translate("CostMatrix", "Total")

#: Hauteur d'une ligne de la matrice (px) — accueille glyphe + coût sur 2 niveaux.
_ROW_HEIGHT_PX = 40
#: Taille de police du glyphe de statut (proéminent).
_GLYPH_POINT_SIZE = 11
#: Taille de police du coût secondaire (discret).
_COST_POINT_SIZE = 8
#: Marge verticale (px) au-dessus du glyphe et sous le coût.
_CELL_VPADDING_PX = 2

_STATUS_SYMBOLS: dict[PhaseStatus, str] = {
    PhaseStatus.PENDING: "·",
    PhaseStatus.RUNNING: "▶",
    PhaseStatus.SUCCEEDED: "✓",
    PhaseStatus.FAILED: "✗",
    PhaseStatus.SKIPPED: "↷",
}

def _status_colors(
    status: PhaseStatus, palette: TokenPalette
) -> tuple[QColor, QColor]:
    """Retourne le couple ``(bg, fg)`` adapté au thème actif pour un statut.

    Mappe chaque ``PhaseStatus`` aux tokens sémantiques de la palette plutôt
    qu'à des couleurs fixes : la matrice s'éclaircit/s'assombrit correctement
    avec le thème.

    Args:
        status: Statut de phase.
        palette: Palette active (résultat de :func:`current_palette`).

    Returns:
        Tuple ``(background, foreground)`` en ``QColor``.
    """
    if status is PhaseStatus.RUNNING:
        return QColor(palette.accent_soft), QColor(palette.accent_strong)
    if status is PhaseStatus.SUCCEEDED:
        return QColor(palette.success_bg), QColor(palette.success)
    if status is PhaseStatus.FAILED:
        return QColor(palette.danger_bg), QColor(palette.danger)
    if status is PhaseStatus.SKIPPED:
        return QColor(palette.info_bg), QColor(palette.info)
    # PENDING (et tout statut inconnu) : neutre — fond surface, texte gris.
    return QColor(palette.surface_soft), QColor(palette.text_3)


def _label_background(palette: TokenPalette) -> QBrush:
    """Fond des cellules de libellés / totaux (couleur surface du thème)."""
    return QBrush(QColor(palette.surface))


def _label_foreground(palette: TokenPalette) -> QBrush:
    """Texte des cellules de libellés / totaux (couleur texte principal)."""
    return QBrush(QColor(palette.text_1))


def _cost_foreground(palette: TokenPalette) -> QColor:
    """Couleur du coût secondaire dans une cellule de données (texte aide)."""
    return QColor(palette.text_3)


#: Snapshot vide réutilisable (initialisation / réinitialisation des dashboards).
EMPTY_COST_MATRIX = CostMatrixSnapshot(
    row_header="",
    column_labels=(),
    row_labels=(),
    cells=(),
    row_totals=(),
    column_totals=(),
    grand_total=0.0,
)


def _fmt_cost(value: float | None) -> str:
    """Formate un coût (``None`` → tiret).

    Args:
        value: Coût ou ``None``.

    Returns:
        Chaîne ``$x.xxxx`` ou ``—``.
    """
    return "—" if value is None else f"${value:.{_COST_DECIMALS}f}"


class _CostMatrixModel(QAbstractTableModel):
    """Modèle Qt adossé à un ``CostMatrixSnapshot`` (+ colonne/ligne Total)."""

    def __init__(self, snapshot: CostMatrixSnapshot) -> None:
        super().__init__()
        self._s = snapshot

    def set_snapshot(self, snapshot: CostMatrixSnapshot) -> None:
        """Remplace le snapshot et réinitialise la vue.

        Args:
            snapshot: Nouveau snapshot.
        """
        self.beginResetModel()
        self._s = snapshot
        self.endResetModel()

    def rowCount(  # noqa: N802
        self, parent: QModelIndex | QPersistentModelIndex | None = None
    ) -> int:
        if parent is not None and parent.isValid():
            return 0
        return len(self._s.row_labels) + (1 if self._s.column_labels else 0)

    def columnCount(  # noqa: N802
        self, parent: QModelIndex | QPersistentModelIndex | None = None
    ) -> int:
        if parent is not None and parent.isValid():
            return 0
        return 1 + len(self._s.column_labels) + (1 if self._s.column_labels else 0)

    def headerData(  # noqa: N802
        self,
        section: int,
        orientation: Qt.Orientation,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> object:
        if role != Qt.ItemDataRole.DisplayRole:
            return None
        if orientation is not Qt.Orientation.Horizontal:
            return None
        if section == 0:
            return self._s.row_header
        n_cols = len(self._s.column_labels)
        if 1 <= section <= n_cols:
            return self._s.column_labels[section - 1]
        return _total_header()

    def _is_total_row(self, row: int) -> bool:
        return row == len(self._s.row_labels)

    def _is_total_col(self, col: int) -> bool:
        return col == 1 + len(self._s.column_labels)

    def data(
        self,
        index: QModelIndex | QPersistentModelIndex,
        role: int = Qt.ItemDataRole.DisplayRole,
    ) -> object:
        if not index.isValid():
            return None
        row, col = index.row(), index.column()
        total_row = self._is_total_row(row)
        total_col = self._is_total_col(col)
        if not total_row and not total_col and col >= 1:
            return self._data_cell(row, col, role)
        return self._data_summary(row, col, total_row=total_row, role=role)

    def _data_cell(self, row: int, col: int, role: int) -> object:
        """Données d'une cellule peinte par le délégué (statut + coût).

        Args:
            row: Ligne.
            col: Colonne (>= 1).
            role: Rôle Qt demandé.

        Returns:
            La ``CostMatrixCell`` (``_CELL_ROLE``), l'infobulle, ou ``None``.
        """
        cell = self._s.cells[row][col - 1]
        if role == _CELL_ROLE:
            return cell
        if role == Qt.ItemDataRole.ToolTipRole:
            return cell.tooltip or None
        return None

    def _data_summary(  # noqa: PLR0911
        self, row: int, col: int, *, total_row: bool, role: int
    ) -> object:
        """Données des cellules de libellé et de totaux (texte + style).

        Args:
            row: Ligne.
            col: Colonne.
            total_row: ``True`` si la ligne est la ligne de totaux.
            role: Rôle Qt demandé.

        Returns:
            La valeur pour le rôle, ou ``None``.
        """
        if role == Qt.ItemDataRole.DisplayRole:
            return self._summary_text(row, col, total_row=total_row)
        if role == Qt.ItemDataRole.TextAlignmentRole:
            if col == 0:
                return int(Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft)
            return int(Qt.AlignmentFlag.AlignCenter)
        if role == Qt.ItemDataRole.FontRole:
            # Seuls les totaux (ligne/colonne) sont mis en avant en gras ; les
            # libellés de lignes restent en graisse normale.
            if total_row or self._is_total_col(col):
                font = QFont()
                font.setBold(True)
                return font
            return None
        if role == Qt.ItemDataRole.BackgroundRole:
            return _label_background(current_palette())
        if role == Qt.ItemDataRole.ForegroundRole:
            return _label_foreground(current_palette())
        return None

    def _summary_text(self, row: int, col: int, *, total_row: bool) -> str:
        """Texte affiché pour une cellule de libellé / total.

        Args:
            row: Ligne.
            col: Colonne.
            total_row: ``True`` si la ligne est la ligne de totaux.

        Returns:
            Le texte à afficher.
        """
        if col == 0:
            return _total_header() if total_row else self._s.row_labels[row]
        total_col = self._is_total_col(col)
        if total_row and total_col:
            return _fmt_cost(self._s.grand_total)
        if total_row:
            return _fmt_cost(self._s.column_totals[col - 1])
        return _fmt_cost(self._s.row_totals[row])


class _CostCellDelegate(QStyledItemDelegate):
    """Peint une cellule de données : glyphe de statut + coût secondaire."""

    def paint(
        self,
        painter: QPainter,
        option: QStyleOptionViewItem,
        index: QModelIndex | QPersistentModelIndex,
    ) -> None:
        """Peint la cellule si elle porte une ``CostMatrixCell``, sinon défaut.

        Args:
            painter: ``QPainter`` fourni par Qt.
            option: Options de style (rectangle, etc.).
            index: Index de la cellule.
        """
        cell = index.data(_CELL_ROLE)
        if not isinstance(cell, CostMatrixCell):
            super().paint(painter, option, index)
            return
        palette = current_palette()
        bg, fg = _status_colors(cell.status, palette)
        rect: QRect = option.rect
        painter.fillRect(rect, bg)

        glyph = _STATUS_SYMBOLS.get(cell.status, "?")
        glyph_font = QFont()
        glyph_font.setBold(True)
        glyph_font.setPointSize(_GLYPH_POINT_SIZE)
        painter.setFont(glyph_font)
        painter.setPen(fg)
        top = QRect(
            rect.x(), rect.y() + _CELL_VPADDING_PX, rect.width(), rect.height() // 2
        )
        painter.drawText(top, int(Qt.AlignmentFlag.AlignCenter), glyph)

        cost_font = QFont()
        cost_font.setPointSize(_COST_POINT_SIZE)
        painter.setFont(cost_font)
        painter.setPen(_cost_foreground(palette))
        bottom = QRect(
            rect.x(),
            rect.y() + rect.height() // 2,
            rect.width(),
            rect.height() // 2 - _CELL_VPADDING_PX,
        )
        painter.drawText(
            bottom, int(Qt.AlignmentFlag.AlignCenter), _fmt_cost(cell.cost_usd)
        )


class CostMatrixView(QTableView):
    """Matrice de coût générique (statut + coût par cellule, totaux)."""

    def __init__(
        self,
        snapshot: CostMatrixSnapshot | None = None,
        parent: QWidget | None = None,
    ) -> None:
        """Construit la vue.

        Args:
            snapshot: Snapshot initial (peut être ``None``).
            parent: Parent Qt optionnel.
        """
        super().__init__(parent)
        self.setObjectName("costMatrix")
        self._model = _CostMatrixModel(snapshot or EMPTY_COST_MATRIX)
        self.setModel(self._model)
        self.setItemDelegate(_CostCellDelegate(self))
        self.setEditTriggers(QTableView.EditTrigger.NoEditTriggers)
        # Matrice en lecture seule : pas de sélection (le délégué peint le fond des
        # cellules de statut, un surlignage de sélection serait incohérent).
        self.setSelectionMode(QTableView.SelectionMode.NoSelection)
        self.setShowGrid(False)
        v_header = self.verticalHeader()
        if v_header is not None:
            v_header.setVisible(False)
            v_header.setDefaultSectionSize(_ROW_HEIGHT_PX)
        header = self.horizontalHeader()
        if header is not None:
            header.setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
            header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)

    def apply_snapshot(self, snapshot: CostMatrixSnapshot) -> None:
        """Applique un nouveau snapshot.

        Args:
            snapshot: Nouveau snapshot.
        """
        self._model.set_snapshot(snapshot)
