"""Composant ``SettingsView`` — réglages en master-detail (catégories + détail).

Liste de catégories à gauche (``QListWidget``), pages de détail à droite
(``QStackedWidget``). Chaque page de détail est englobée dans un
``QScrollArea`` (transparent, sans bordure) pour qu'un contenu plus haut
que la fenêtre devienne défilable verticalement plutôt que clippé.

Réutilisable par toute fonctionnalité dont les réglages sont nombreux,
pour éviter une fenêtre surchargée.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Final

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QListWidget,
    QScrollArea,
    QStackedWidget,
    QWidget,
)

#: Largeur fixe (px) de la colonne de navigation des catégories.
_CATEGORY_LIST_WIDTH_PX: Final[int] = 200


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
        # Pas de scroll horizontal sur une nav verticale étroite (évite le
        # tracé d'un scrollbar inutile en bas du panneau).
        self._list.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        self._stack = QStackedWidget(self)

        for label, page in categories:
            self._list.addItem(label)
            # Chaque page est englobée dans un ``QScrollArea`` : si le contenu
            # est plus haut que la zone visible (cas fréquent quand le
            # dialogue est réduit ou que la page a beaucoup de cartes), un
            # scrollbar vertical apparaît automatiquement plutôt qu'un
            # rognage en bas de page.
            scroll = QScrollArea(self)
            scroll.setWidget(page)
            scroll.setWidgetResizable(True)
            # Pas de cadre autour du QScrollArea (intégration propre dans la
            # vue ; le fond du dialogue reste visible).
            scroll.setFrameShape(QFrame.Shape.NoFrame)
            scroll.setHorizontalScrollBarPolicy(
                Qt.ScrollBarPolicy.ScrollBarAlwaysOff
            )
            self._stack.addWidget(scroll)

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
