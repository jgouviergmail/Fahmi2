"""Briques UI partagées (helpers d'assemblage standards).

Fournit les composants de présentation réutilisés par tous les écrans :

- :func:`card` : ``QFrame`` stylé (``objectName="card"``) avec ombre douce
  + header (titre obligatoire, description optionnelle).
- :func:`page_header` : titre + description grise pour un écran de réglages.
- :func:`field_hint` / :func:`section_label` / :func:`horizontal_separator` :
  helpers texte courts.
- :func:`install_shadow` / :func:`reapply_card_shadows` : ombres adaptées au
  thème actif (l'ombre est portée par un effet Python car QSS ne supporte
  pas ``box-shadow``).
- :func:`frenchify_button_box` : remplace les libellés des boutons standard
  Qt (Save/Cancel/Close…) par leur version française.

Ces helpers s'accrochent à des ``objectName`` réservés
(``card`` / ``cardTitle`` / ``cardDesc`` / ``settingsPageTitle`` /
``settingsPageDesc`` / ``fieldHint`` / ``sectionLabel`` / ``hsep``) stylés
dans les feuilles QSS ``light_fluent.qss`` / ``dark_fluent.qss``.
"""

from __future__ import annotations

from typing import Final

from PySide6.QtWidgets import (
    QApplication,
    QDialogButtonBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from fahmi2.ui.theme._tokens import ShadowSpec, current_palette

# ---------------------------------------------------------------- object names

#: ``objectName`` réservé aux cartes (stylé par les QSS clair/sombre).
CARD_OBJECT_NAME: Final[str] = "card"
#: ``objectName`` réservé au titre d'une carte.
CARD_TITLE_OBJECT_NAME: Final[str] = "cardTitle"
#: ``objectName`` réservé à la description optionnelle sous un titre de carte.
CARD_DESC_OBJECT_NAME: Final[str] = "cardDesc"
#: ``objectName`` réservé au titre d'un écran de réglages.
PAGE_TITLE_OBJECT_NAME: Final[str] = "settingsPageTitle"
#: ``objectName`` réservé à la description d'un écran de réglages.
PAGE_DESC_OBJECT_NAME: Final[str] = "settingsPageDesc"
#: ``objectName`` réservé aux textes d'aide sous un champ.
FIELD_HINT_OBJECT_NAME: Final[str] = "fieldHint"
#: ``objectName`` réservé aux micro-labels de section (majuscules).
SECTION_LABEL_OBJECT_NAME: Final[str] = "sectionLabel"
#: ``objectName`` réservé aux séparateurs horizontaux fins.
HSEP_OBJECT_NAME: Final[str] = "hsep"

# ----------------------------------------------------------- card geometry

# Padding interne d'une carte (left, top, right, bottom). Aligné sur la grille
# 4 px du système de design (cf. spec § 3.4).
_CARD_PADDING_LEFT: Final[int] = 22
_CARD_PADDING_TOP: Final[int] = 18
_CARD_PADDING_RIGHT: Final[int] = 22
_CARD_PADDING_BOTTOM: Final[int] = 20
#: Espacement vertical entre les enfants d'une carte.
_CARD_SPACING: Final[int] = 12
#: Hauteur fixe d'un séparateur horizontal (``#hsep``).
_HSEP_FIXED_HEIGHT: Final[int] = 1

# ------------------------------------------------- French standard button labels

#: Libellés français des boutons standard Qt (Save/Cancel/Close…). Appliqués
#: par :func:`frenchify_button_box`. Sources : conventions UX françaises +
#: glossaire du spec (cf. § 6.3).
_FRENCH_STANDARD_BUTTON_TEXTS: Final[dict[QDialogButtonBox.StandardButton, str]] = {
    QDialogButtonBox.StandardButton.Ok: "OK",
    QDialogButtonBox.StandardButton.Cancel: "Annuler",
    QDialogButtonBox.StandardButton.Save: "Enregistrer",
    QDialogButtonBox.StandardButton.Close: "Fermer",
    QDialogButtonBox.StandardButton.Yes: "Oui",
    QDialogButtonBox.StandardButton.No: "Non",
    QDialogButtonBox.StandardButton.Apply: "Appliquer",
    QDialogButtonBox.StandardButton.Discard: "Abandonner",
    QDialogButtonBox.StandardButton.Reset: "Réinitialiser",
    QDialogButtonBox.StandardButton.Help: "Aide",
}


def card(
    parent: QWidget | None,
    *,
    title: str,
    description: str | None = None,
) -> tuple[QFrame, QVBoxLayout]:
    """Construit une carte stylée (fond, bordure, ombre douce) + son layout.

    La carte porte ``objectName="card"`` (stylé en QSS) et reçoit une ombre
    via :func:`install_shadow` (couleur adaptée au thème actif). Le titre est
    obligatoire ; la description est optionnelle.

    Args:
        parent: Parent Qt.
        title: Titre de la carte (toujours présent, en ``#cardTitle``).
        description: Description courte sous le titre (en ``#cardDesc``).

    Returns:
        Le couple ``(carte, layout interne prêt à recevoir le contenu)``.
        Le layout contient déjà le titre (et la description si fournie) ;
        l'appelant peut directement ``addWidget`` / ``addLayout`` à la suite.
    """
    frame = QFrame(parent)
    frame.setObjectName(CARD_OBJECT_NAME)
    install_shadow(frame)
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(
        _CARD_PADDING_LEFT,
        _CARD_PADDING_TOP,
        _CARD_PADDING_RIGHT,
        _CARD_PADDING_BOTTOM,
    )
    layout.setSpacing(_CARD_SPACING)
    title_label = QLabel(title, frame)
    title_label.setObjectName(CARD_TITLE_OBJECT_NAME)
    title_label.setWordWrap(True)
    layout.addWidget(title_label)
    if description is not None:
        desc_label = QLabel(description, frame)
        desc_label.setObjectName(CARD_DESC_OBJECT_NAME)
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)
    return frame, layout


def page_header(
    parent: QWidget | None,
    *,
    title: str,
    description: str | None = None,
) -> QWidget:
    """En-tête d'écran de réglages (titre 20/700 + description grise).

    Args:
        parent: Parent Qt.
        title: Titre de la page (en ``#settingsPageTitle``).
        description: Description courte sous le titre (en ``#settingsPageDesc``,
            optionnelle).

    Returns:
        Le widget conteneur prêt à être ajouté en tête d'une page de réglages.
    """
    container = QWidget(parent)
    layout = QVBoxLayout(container)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(2)
    title_label = QLabel(title, container)
    title_label.setObjectName(PAGE_TITLE_OBJECT_NAME)
    title_label.setWordWrap(True)
    layout.addWidget(title_label)
    if description is not None:
        desc_label = QLabel(description, container)
        desc_label.setObjectName(PAGE_DESC_OBJECT_NAME)
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)
    return container


def field_hint(parent: QWidget | None, text: str) -> QLabel:
    """Texte d'aide gris (12 px) placé sous un champ ou une carte.

    Args:
        parent: Parent Qt.
        text: Texte du hint.

    Returns:
        Le ``QLabel`` configuré (``objectName="fieldHint"``, ``wordWrap`` activé).
    """
    label = QLabel(text, parent)
    label.setObjectName(FIELD_HINT_OBJECT_NAME)
    label.setWordWrap(True)
    return label


def section_label(parent: QWidget | None, text: str) -> QLabel:
    """Micro-label majuscules (11/700 letter-spacing) — en-tête de sous-section.

    Args:
        parent: Parent Qt.
        text: Texte du label (passé en majuscules dans le rendu).

    Returns:
        Le ``QLabel`` configuré (``objectName="sectionLabel"``).
    """
    label = QLabel(text.upper(), parent)
    label.setObjectName(SECTION_LABEL_OBJECT_NAME)
    return label


def horizontal_separator(parent: QWidget | None) -> QFrame:
    """Séparateur horizontal fin (1 px), stylé via QSS (``#hsep``).

    Args:
        parent: Parent Qt.

    Returns:
        Le ``QFrame`` configuré (hauteur fixe 1 px).
    """
    line = QFrame(parent)
    line.setObjectName(HSEP_OBJECT_NAME)
    line.setFixedHeight(_HSEP_FIXED_HEIGHT)
    line.setFrameShape(QFrame.Shape.HLine)
    return line


def install_shadow(widget: QWidget, spec: ShadowSpec | None = None) -> None:
    """Installe une ombre douce sur ``widget`` (adaptée au thème actif).

    Si ``spec`` n'est pas fourni, utilise ``shadow_card`` de la palette
    actuellement active (cf. :func:`fahmi2.ui.theme._tokens.current_palette`).
    Sur changement de thème, :func:`reapply_card_shadows` ré-installe les
    ombres des cartes existantes avec la nouvelle couleur.

    Args:
        widget: Widget à orner.
        spec: Spécification d'ombre explicite (optionnel).
    """
    effective = spec if spec is not None else current_palette().shadow_card
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(effective.blur_radius)
    effect.setXOffset(effective.x_offset)
    effect.setYOffset(effective.y_offset)
    effect.setColor(effective.color)
    widget.setGraphicsEffect(effect)


def reapply_card_shadows(app: QApplication) -> None:
    """Ré-installe les ombres de toutes les cartes (changement de thème).

    Itère ``QApplication.allWidgets()`` et, pour chaque widget portant
    ``objectName=="card"``, re-applique :func:`install_shadow` avec la
    palette active. Sans effet sur les widgets sans carte.

    Args:
        app: ``QApplication`` actif.
    """
    for w in app.allWidgets():
        if w.objectName() == CARD_OBJECT_NAME:
            install_shadow(w)


def frenchify_button_box(box: QDialogButtonBox) -> None:
    """Remplace les libellés des boutons standard Qt par leur version française.

    Sur certains systèmes Qt n'utilise pas la locale française pour les boutons
    standard (``Cancel`` apparaît tel quel) ; ce helper garantit un libellé
    cohérent partout (« Annuler » au lieu de « Cancel », « Enregistrer » au
    lieu de « Save », etc.). Les boutons custom (ajoutés explicitement avec
    leur libellé) ne sont pas modifiés.

    Args:
        box: ``QDialogButtonBox`` à franciser.
    """
    for std_button, french_text in _FRENCH_STANDARD_BUTTON_TEXTS.items():
        button = box.button(std_button)
        if button is not None:
            button.setText(french_text)


__all__ = [
    "CARD_DESC_OBJECT_NAME",
    "CARD_OBJECT_NAME",
    "CARD_TITLE_OBJECT_NAME",
    "FIELD_HINT_OBJECT_NAME",
    "HSEP_OBJECT_NAME",
    "PAGE_DESC_OBJECT_NAME",
    "PAGE_TITLE_OBJECT_NAME",
    "SECTION_LABEL_OBJECT_NAME",
    "card",
    "field_hint",
    "frenchify_button_box",
    "horizontal_separator",
    "install_shadow",
    "page_header",
    "reapply_card_shadows",
    "section_label",
]
