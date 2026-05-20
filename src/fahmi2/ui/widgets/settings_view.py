"""Composant ``SettingsView`` — réglages en master-detail (catégories + détail).

Liste de catégories à gauche (``QListWidget``), pages de détail à droite
(``QStackedWidget``). Réutilisable par toute fonctionnalité dont les réglages sont
nombreux, pour éviter une fenêtre surchargée.
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtWidgets import (
    QHBoxLayout,
    QListWidget,
    QStackedWidget,
    QWidget,
)

_CATEGORY_LIST_WIDTH_PX = 180


class SettingsView(QWidget):
    """Vue de réglages master-detail (catégories à gauche, détail à droite)."""

    def __init__(
        self,
        categories: Sequence[tuple[str, QWidget]],
        parent: QWidget | None = None,
    ) -> None:
        """Construit la vue.

        Args:
            categories: Séquence ordonnée ``(libellé, page)``.
            parent: Parent Qt optionnel.
        """
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self._list = QListWidget(self)
        self._list.setObjectName("settingsCategoryList")
        self._list.setFixedWidth(_CATEGORY_LIST_WIDTH_PX)
        self._stack = QStackedWidget(self)

        for label, page in categories:
            self._list.addItem(label)
            self._stack.addWidget(page)

        self._list.currentRowChanged.connect(self._stack.setCurrentIndex)
        layout.addWidget(self._list)
        layout.addWidget(self._stack, stretch=1)

        if categories:
            self._list.setCurrentRow(0)

    def category_count(self) -> int:
        """Retourne le nombre de catégories.

        Returns:
            Le nombre de pages enregistrées.
        """
        return self._list.count()

    def current_index(self) -> int:
        """Retourne l'index de la catégorie courante (``-1`` si vide).

        Returns:
            Index courant.
        """
        return self._list.currentRow()

    def set_current_index(self, index: int) -> None:
        """Sélectionne la catégorie d'index ``index``.

        Args:
            index: Index de catégorie.
        """
        self._list.setCurrentRow(index)
