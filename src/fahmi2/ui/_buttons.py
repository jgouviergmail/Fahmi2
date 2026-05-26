"""Helpers de boutons d'action stylés (cohérence visuelle inter-onglets).

Le style visuel d'un bouton (``primary`` / ``default`` / ``danger``) est porté par
la feuille de style globale via la propriété Qt ``role`` (cf.
``theme/light_fluent.qss``). Ce helper centralise la création d'un bouton avec son
rôle + le curseur « main », pour que tous les onglets partagent le même rendu.
"""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QPushButton, QWidget

BUTTON_ROLE_PRIMARY = "primary"
BUTTON_ROLE_DEFAULT = "default"
BUTTON_ROLE_DANGER = "danger"


def make_role_button(
    parent: QWidget, text: str, *, role: str = BUTTON_ROLE_DEFAULT
) -> QPushButton:
    """Crée un ``QPushButton`` stylé par sa propriété ``role`` (QSS global).

    Args:
        parent: Parent Qt.
        text: Libellé du bouton.
        role: ``"primary"``, ``"default"`` ou ``"danger"``.

    Returns:
        Le bouton instancié (sans connexion : à brancher par l'appelant).
    """
    button = QPushButton(text, parent)
    button.setProperty("role", role)
    button.setCursor(Qt.CursorShape.PointingHandCursor)
    return button
