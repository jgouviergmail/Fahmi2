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

from typing import Final, cast

from PySide6.QtCore import QT_TRANSLATE_NOOP, QCoreApplication, Qt
from PySide6.QtWidgets import (
    QApplication,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
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
#: ``objectName`` réservé au footer de dialogue (séparateur top + padding).
DIALOG_FOOTER_OBJECT_NAME: Final[str] = "dialogFooter"

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

# --------------------------------------------------- settings page geometry

#: Marges externes d'une page de réglages (autour de la pile de cartes).
SETTINGS_PAGE_MARGIN_HORIZONTAL: Final[int] = 22
SETTINGS_PAGE_MARGIN_VERTICAL: Final[int] = 18
#: Espacement vertical entre les enfants d'une page de réglages.
SETTINGS_PAGE_SPACING: Final[int] = 16
#: Espacement horizontal d'un formulaire (entre étiquette et champ).
SETTINGS_FORM_HORIZONTAL_SPACING: Final[int] = 18
#: Espacement vertical d'un formulaire (entre lignes).
SETTINGS_FORM_VERTICAL_SPACING: Final[int] = 12

# --------------------------------------------------- dialog footer geometry

#: Padding horizontal du footer de dialogue (autour de la barre de boutons).
_DIALOG_FOOTER_PADDING_HORIZONTAL: Final[int] = 20
#: Padding vertical du footer de dialogue.
_DIALOG_FOOTER_PADDING_VERTICAL: Final[int] = 12
#: Espacement entre les boutons du footer.
_DIALOG_FOOTER_BUTTON_SPACING: Final[int] = 8

# ------------------------------------------------- French standard button labels

#: Libellés **sources FR** des boutons standard Qt (Save/Cancel/Close…)
#: appliqués par :func:`localize_button_box`. Marqués par
#: :func:`QT_TRANSLATE_NOOP` pour extraction ; la résolution effective passe
#: par ``QCoreApplication.translate("StandardButtons", source)`` au moment
#: où le bouton est rencontré, donc dans la langue active.
_STANDARD_BUTTON_SOURCES: Final[dict[QDialogButtonBox.StandardButton, str]] = {
    QDialogButtonBox.StandardButton.Ok: cast(str, QT_TRANSLATE_NOOP("StandardButtons", "OK")),
    QDialogButtonBox.StandardButton.Cancel: cast(
        str, QT_TRANSLATE_NOOP("StandardButtons", "Annuler")
    ),
    QDialogButtonBox.StandardButton.Save: cast(
        str, QT_TRANSLATE_NOOP("StandardButtons", "Enregistrer")
    ),
    QDialogButtonBox.StandardButton.Close: cast(
        str, QT_TRANSLATE_NOOP("StandardButtons", "Fermer")
    ),
    QDialogButtonBox.StandardButton.Yes: cast(str, QT_TRANSLATE_NOOP("StandardButtons", "Oui")),
    QDialogButtonBox.StandardButton.No: cast(str, QT_TRANSLATE_NOOP("StandardButtons", "Non")),
    QDialogButtonBox.StandardButton.Apply: cast(
        str, QT_TRANSLATE_NOOP("StandardButtons", "Appliquer")
    ),
    QDialogButtonBox.StandardButton.Discard: cast(
        str, QT_TRANSLATE_NOOP("StandardButtons", "Abandonner")
    ),
    QDialogButtonBox.StandardButton.Reset: cast(
        str, QT_TRANSLATE_NOOP("StandardButtons", "Réinitialiser")
    ),
    QDialogButtonBox.StandardButton.Help: cast(
        str, QT_TRANSLATE_NOOP("StandardButtons", "Aide")
    ),
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


def settings_page(parent: QWidget | None = None) -> tuple[QWidget, QVBoxLayout]:
    """Construit un widget de page de réglages (marges + spacing standards).

    Conventions du système de design (cf. spec § 3.4) : marges externes
    22×18, spacing vertical 16. Réutilisé par tous les écrans de réglages
    pour garantir un rythme homogène d'une page à l'autre.

    Args:
        parent: Parent Qt optionnel.

    Returns:
        Le couple ``(page, layout)``. Le layout est prêt à recevoir un
        ``page_header`` puis une pile de cartes.
    """
    page = QWidget(parent)
    layout = QVBoxLayout(page)
    layout.setContentsMargins(
        SETTINGS_PAGE_MARGIN_HORIZONTAL,
        SETTINGS_PAGE_MARGIN_VERTICAL,
        SETTINGS_PAGE_MARGIN_HORIZONTAL,
        SETTINGS_PAGE_MARGIN_VERTICAL,
    )
    layout.setSpacing(SETTINGS_PAGE_SPACING)
    return page, layout


def settings_form() -> QFormLayout:
    """Construit un ``QFormLayout`` aux conventions du système de design.

    Étiquettes alignées à gauche, champs étirés à la croissance, spacing
    horizontal/vertical standardisé (cf. spec § 3.4). Réutilisé par tous les
    écrans de réglages.

    Returns:
        Le ``QFormLayout`` configuré.
    """
    form = QFormLayout()
    form.setHorizontalSpacing(SETTINGS_FORM_HORIZONTAL_SPACING)
    form.setVerticalSpacing(SETTINGS_FORM_VERTICAL_SPACING)
    form.setLabelAlignment(
        Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
    )
    form.setFieldGrowthPolicy(QFormLayout.FieldGrowthPolicy.ExpandingFieldsGrow)
    return form


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

    Itère uniquement les widgets accessibles depuis les fenêtres
    top-level actuellement vivantes (via ``topLevelWidgets()`` +
    ``findChildren(QWidget)``) et applique :func:`install_shadow` à ceux
    portant ``objectName=="card"``.

    Pourquoi pas ``QApplication.allWidgets()`` ? Cette API retourne **tous**
    les widgets jamais créés et encore référencés (orphelins inclus). Sur des
    sessions longues — tests, ou démon avec ouvertures successives de
    dialogues — la liste peut contenir des widgets dont la destruction côté
    C++ a commencé mais dont la référence Python persiste, et accéder à
    ``.objectName()`` y déclenche des corruptions mémoire Windows
    (0xc0000374). Restreindre aux top-level vivants évite ce problème et
    reste sémantiquement équivalent en pratique (toute carte affichée vit
    sous une fenêtre top-level).

    Args:
        app: ``QApplication`` actif.
    """
    for top in app.topLevelWidgets():
        if top.objectName() == CARD_OBJECT_NAME:
            install_shadow(top)
        for child in top.findChildren(QWidget):
            if child.objectName() == CARD_OBJECT_NAME:
                install_shadow(child)


def dialog_footer(parent: QWidget | None, button_box: QDialogButtonBox) -> QWidget:
    """Englobe une ``QDialogButtonBox`` dans un footer stylé (séparateur + padding).

    Patron éprouvé pour les dialogues plein-largeur (master-detail) où la
    barre de boutons doit visuellement se détacher du contenu : fond
    surface, séparateur fin en haut, padding horizontal/vertical confortable
    autour des boutons (les boutons ne sont jamais collés au bord du
    dialogue).

    Args:
        parent: Parent Qt (typiquement le dialogue).
        button_box: ``QDialogButtonBox`` à englober.

    Returns:
        Le widget conteneur prêt à être ajouté au layout externe du dialogue.
    """
    footer = QWidget(parent)
    footer.setObjectName(DIALOG_FOOTER_OBJECT_NAME)
    layout = QHBoxLayout(footer)
    layout.setContentsMargins(
        _DIALOG_FOOTER_PADDING_HORIZONTAL,
        _DIALOG_FOOTER_PADDING_VERTICAL,
        _DIALOG_FOOTER_PADDING_HORIZONTAL,
        _DIALOG_FOOTER_PADDING_VERTICAL,
    )
    layout.setSpacing(_DIALOG_FOOTER_BUTTON_SPACING)
    layout.addStretch(1)
    layout.addWidget(button_box)
    return footer


def localize_button_box(box: QDialogButtonBox) -> None:
    """Localise les libellés des boutons standard Qt dans la langue active.

    Qt n'utilise pas toujours la locale pour les boutons standard (``Cancel``
    apparaît parfois tel quel) ; ce helper force le libellé via
    ``QCoreApplication.translate("StandardButtons", source)`` — en FR il
    retourne la chaîne source (« Annuler », « Enregistrer »…), en EN il
    retourne la traduction du ``.qm`` bundlé (« Cancel », « Save »…). Les
    boutons custom (ajoutés explicitement avec leur libellé) ne sont pas
    modifiés.

    Le bouton « accept » (``Save`` / ``Ok`` — rôle ``AcceptRole``) reçoit
    également ``role="primary"`` pour être affiché en bleu primaire de manière
    explicite (la propriété ``:default`` de Qt n'est pas toujours initialisée
    quand le dialogue n'est pas montré, ce qui peut laisser le bouton en
    style neutre dans les captures ou certains contextes).

    Args:
        box: ``QDialogButtonBox`` à localiser.
    """
    for std_button, source in _STANDARD_BUTTON_SOURCES.items():
        translated = box.button(std_button)
        if translated is not None:
            translated.setText(
                QCoreApplication.translate("StandardButtons", source)
            )
    for accept_candidate in box.buttons():
        if box.buttonRole(accept_candidate) == QDialogButtonBox.ButtonRole.AcceptRole:
            accept_candidate.setProperty("role", "primary")
            style = accept_candidate.style()
            if style is not None:
                style.unpolish(accept_candidate)
                style.polish(accept_candidate)
            break


# Alias rétro-compatible (sera retiré en i18n-3 après nettoyage des callers).
#: Deprecated alias — préférer :func:`localize_button_box`.
frenchify_button_box = localize_button_box


__all__ = [
    "CARD_DESC_OBJECT_NAME",
    "CARD_OBJECT_NAME",
    "CARD_TITLE_OBJECT_NAME",
    "DIALOG_FOOTER_OBJECT_NAME",
    "FIELD_HINT_OBJECT_NAME",
    "HSEP_OBJECT_NAME",
    "PAGE_DESC_OBJECT_NAME",
    "PAGE_TITLE_OBJECT_NAME",
    "SECTION_LABEL_OBJECT_NAME",
    "SETTINGS_FORM_HORIZONTAL_SPACING",
    "SETTINGS_FORM_VERTICAL_SPACING",
    "SETTINGS_PAGE_MARGIN_HORIZONTAL",
    "SETTINGS_PAGE_MARGIN_VERTICAL",
    "SETTINGS_PAGE_SPACING",
    "card",
    "dialog_footer",
    "field_hint",
    "frenchify_button_box",
    "horizontal_separator",
    "install_shadow",
    "localize_button_box",
    "page_header",
    "reapply_card_shadows",
    "section_label",
    "settings_form",
    "settings_page",
]
