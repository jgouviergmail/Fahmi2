"""Widget ``PedagogyProgressView`` — bandeau d'état + table de progression.

Affiche l'état de fraîcheur (bandeau coloré via la propriété QSS ``state``) et la
progression des supports (une ligne par (support, langue) avec statut et coût).
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QAbstractItemView,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from fahmi2.ui.pedagogy_labels import status_label, support_label
from fahmi2.ui.viewmodels.pedagogy_progress import PedagogyProgressSnapshot
from fahmi2.ui.viewmodels.pedagogy_state import PedagogyStateInfo

_BANNER_OBJECT_NAME = "pedagogyStateBanner"
_COLUMNS = ("Support", "Langue", "Statut", "Coût")
_COST_DECIMALS = 4


class PedagogyProgressView(QWidget):
    """Bandeau d'état + table de progression des supports."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Construit la vue.

        Args:
            parent: Parent Qt optionnel.
        """
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._banner = QLabel("", self)
        self._banner.setObjectName(_BANNER_OBJECT_NAME)
        self._banner.setWordWrap(True)

        self._table = QTableWidget(0, len(_COLUMNS), self)
        self._table.setHorizontalHeaderLabels(list(_COLUMNS))
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setSelectionMode(QAbstractItemView.SelectionMode.NoSelection)
        self._table.verticalHeader().setVisible(False)
        header = self._table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)

        layout.addWidget(self._banner)
        layout.addWidget(self._table, stretch=1)

    def apply_snapshot(self, snapshot: PedagogyProgressSnapshot) -> None:
        """Remplit la table à partir d'un snapshot de progression.

        Args:
            snapshot: Snapshot à afficher.
        """
        self._table.setRowCount(len(snapshot.cells))
        for row, cell in enumerate(snapshot.cells):
            self._table.setItem(
                row, 0, QTableWidgetItem(support_label(cell.support_type))
            )
            self._table.setItem(row, 1, QTableWidgetItem(cell.language.value))
            self._table.setItem(row, 2, QTableWidgetItem(status_label(cell.status)))
            self._table.setItem(
                row, 3, QTableWidgetItem(f"${cell.cost_usd:.{_COST_DECIMALS}f}")
            )

    def set_state(self, info: PedagogyStateInfo) -> None:
        """Met à jour le bandeau d'état.

        Args:
            info: État + message à afficher.
        """
        self._banner.setText(info.message)
        self._set_banner_state(info.state.value)

    def clear(self) -> None:
        """Vide la table de progression et le bandeau (aucun projet sélectionné)."""
        self._table.setRowCount(0)
        self._banner.setText("")
        self._set_banner_state("")

    def _set_banner_state(self, state: str) -> None:
        """Applique la propriété QSS dynamique ``state`` et force le re-style.

        Args:
            state: Valeur de l'état (``""`` pour réinitialiser).
        """
        self._banner.setProperty("state", state)
        style = self._banner.style()
        if style is not None:
            style.unpolish(self._banner)
            style.polish(self._banner)

    def row_count(self) -> int:
        """Retourne le nombre de lignes affichées.

        Returns:
            Le nombre de lignes de la table.
        """
        return self._table.rowCount()

    def banner_text(self) -> str:
        """Retourne le texte courant du bandeau.

        Returns:
            Le texte du bandeau.
        """
        return self._banner.text()
