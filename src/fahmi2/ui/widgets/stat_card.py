"""Widget ``StatCard`` — carte d'indicateur réutilisable (icône + valeur + sous-info).

Extraite de ``stats_strip`` pour être partagée par les bandes de stats Génération
et Pédagogie. Une variante d'accent (``neutral``/``running``/``success``/
``warning``/``danger``) pilote la couleur de la valeur via le QSS global.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget


class StatCard(QFrame):
    """Carte d'indicateur (icône + titre + valeur principale + sous-info)."""

    def __init__(
        self,
        *,
        icon: str,
        title: str,
        parent: QWidget | None = None,
    ) -> None:
        """Construit la carte.

        Args:
            icon: Glyphe Unicode décoratif.
            title: Libellé court de l'indicateur.
            parent: Parent Qt optionnel.
        """
        super().__init__(parent)
        self.setObjectName("statCard")
        self.setFrameShape(QFrame.Shape.NoFrame)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 10, 14, 10)
        layout.setSpacing(2)

        header = QHBoxLayout()
        header.setSpacing(6)
        self._icon_label = QLabel(icon, self)
        self._icon_label.setObjectName("statCardIcon")
        self._title_label = QLabel(title, self)
        self._title_label.setObjectName("statCardTitle")
        header.addWidget(self._icon_label)
        header.addWidget(self._title_label)
        header.addStretch(1)
        layout.addLayout(header)

        self._value_label = QLabel("—", self)
        self._value_label.setObjectName("statCardValue")
        self._value_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.NoTextInteraction
        )
        layout.addWidget(self._value_label)

        self._sub_label = QLabel(" ", self)
        self._sub_label.setObjectName("statCardSub")
        layout.addWidget(self._sub_label)

    def set_value(self, value: str, sub: str = "") -> None:
        """Met à jour la valeur principale et la sous-info.

        Args:
            value: Texte de la valeur principale.
            sub: Texte secondaire (peut être vide).
        """
        self._value_label.setText(value)
        # On garde un espace insécable si vide pour éviter un saut de hauteur.
        self._sub_label.setText(sub or " ")

    def set_accent(self, kind: str) -> None:
        """Force une variante d'accent visuelle via une propriété Qt.

        Args:
            kind: ``"neutral"``, ``"running"``, ``"success"``, ``"warning"`` ou
                ``"danger"`` (interprété par le QSS global).
        """
        self._value_label.setProperty("accent", kind)
        style = self._value_label.style()
        if style is not None:
            style.unpolish(self._value_label)
            style.polish(self._value_label)

    def value_text(self) -> str:
        """Retourne le texte courant de la valeur principale (tests).

        Returns:
            Le texte de la valeur.
        """
        return self._value_label.text()
