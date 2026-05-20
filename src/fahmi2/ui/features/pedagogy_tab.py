"""Onglet « Supports pédagogiques » — stub (implémenté au sous-projet SP2).

Affiche un état « bientôt disponible » et un rappel du prérequis (un document
consolidé doit avoir été généré). Aucune logique ni réglage à ce stade.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from fahmi2.ui.features.feature import FeatureId, FeatureTab

_TAB_TITLE = "Supports pédagogiques"
_PLACEHOLDER_TITLE = "Bientôt disponible"
_PLACEHOLDER_HINT = (
    "Cette fonctionnalité générera des supports de révision (flashcards, QCM, "
    "fiches…) à partir du document consolidé produit par la Génération."
)


class PedagogyTab(FeatureTab):
    """Onglet stub de la fonctionnalité Supports pédagogiques."""

    def __init__(self, parent: QWidget | None = None) -> None:
        """Construit le widget stub.

        Args:
            parent: Parent Qt optionnel.
        """
        self._widget = QWidget(parent)
        layout = QVBoxLayout(self._widget)
        layout.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title = QLabel(_PLACEHOLDER_TITLE, self._widget)
        title.setObjectName("pedagogyPlaceholderTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint = QLabel(_PLACEHOLDER_HINT, self._widget)
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hint.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(hint)

    @property
    def feature_id(self) -> FeatureId:
        """Identifiant de la fonctionnalité."""
        return FeatureId.PEDAGOGY

    @property
    def title(self) -> str:
        """Libellé de l'onglet."""
        return _TAB_TITLE

    @property
    def widget(self) -> QWidget:
        """Widget racine de l'onglet."""
        return self._widget
