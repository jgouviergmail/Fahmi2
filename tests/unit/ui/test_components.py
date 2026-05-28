"""Smoke tests des briques UI partagées (`ui/_components.py`)."""

from __future__ import annotations

from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,
    QDialogButtonBox,
    QFrame,
    QGraphicsDropShadowEffect,
    QLabel,
)

from fahmi2.ui._components import (
    CARD_DESC_OBJECT_NAME,
    CARD_OBJECT_NAME,
    CARD_TITLE_OBJECT_NAME,
    FIELD_HINT_OBJECT_NAME,
    HSEP_OBJECT_NAME,
    PAGE_DESC_OBJECT_NAME,
    PAGE_TITLE_OBJECT_NAME,
    SECTION_LABEL_OBJECT_NAME,
    card,
    field_hint,
    frenchify_button_box,
    horizontal_separator,
    install_shadow,
    page_header,
    reapply_card_shadows,
    section_label,
)
from fahmi2.ui.theme._tokens import (
    LIGHT_TOKENS,
    current_palette,
    set_current_palette,
)


def test_card_returns_frame_with_object_name_and_title(qtbot: object) -> None:
    """``card`` produit un ``QFrame`` stylé avec le titre fourni."""
    del qtbot
    frame, layout = card(None, title="Mise en forme")
    assert isinstance(frame, QFrame)
    assert frame.objectName() == CARD_OBJECT_NAME
    # Le titre est le premier enfant ajouté au layout interne.
    item = layout.itemAt(0)
    assert item is not None
    first_child = item.widget()
    assert isinstance(first_child, QLabel)
    assert first_child.objectName() == CARD_TITLE_OBJECT_NAME
    assert first_child.text() == "Mise en forme"


def test_card_with_description_adds_desc_label(qtbot: object) -> None:
    """Si une description est fournie, elle est ajoutée juste après le titre."""
    del qtbot
    _, layout = card(None, title="T", description="explication")
    item = layout.itemAt(1)
    assert item is not None
    desc = item.widget()
    assert isinstance(desc, QLabel)
    assert desc.objectName() == CARD_DESC_OBJECT_NAME
    assert desc.text() == "explication"


def test_card_without_description_does_not_add_desc_label(qtbot: object) -> None:
    """Sans description, le layout ne contient que le titre."""
    del qtbot
    _, layout = card(None, title="T")
    # 1 seul widget : le titre.
    assert layout.count() == 1


def test_card_installs_shadow_effect(qtbot: object) -> None:
    """Une carte porte automatiquement un ``QGraphicsDropShadowEffect``."""
    del qtbot
    frame, _ = card(None, title="T")
    assert isinstance(frame.graphicsEffect(), QGraphicsDropShadowEffect)


def test_page_header_returns_title_and_optional_description(qtbot: object) -> None:
    """``page_header`` produit un widget avec titre et description optionnelle."""
    del qtbot
    container = page_header(None, title="Style", description="Ton et mise en forme.")
    labels = container.findChildren(QLabel)
    object_names = {label.objectName() for label in labels}
    assert PAGE_TITLE_OBJECT_NAME in object_names
    assert PAGE_DESC_OBJECT_NAME in object_names


def test_page_header_without_description(qtbot: object) -> None:
    """Sans description, le header ne contient qu'un seul label (titre)."""
    del qtbot
    container = page_header(None, title="Style")
    labels = container.findChildren(QLabel)
    assert len(labels) == 1
    assert labels[0].objectName() == PAGE_TITLE_OBJECT_NAME


def test_field_hint_creates_word_wrapped_label(qtbot: object) -> None:
    """``field_hint`` retourne un ``QLabel`` ``#fieldHint`` avec word-wrap."""
    del qtbot
    label = field_hint(None, "Aide explicative.")
    assert label.objectName() == FIELD_HINT_OBJECT_NAME
    assert label.wordWrap() is True
    assert label.text() == "Aide explicative."


def test_section_label_uppercases_text(qtbot: object) -> None:
    """``section_label`` passe le texte en majuscules + objectName ``sectionLabel``."""
    del qtbot
    label = section_label(None, "détail")
    assert label.objectName() == SECTION_LABEL_OBJECT_NAME
    assert label.text() == "DÉTAIL"


def test_horizontal_separator_is_hsep(qtbot: object) -> None:
    """``horizontal_separator`` retourne un ``QFrame`` ``#hsep`` de hauteur 1."""
    del qtbot
    line = horizontal_separator(None)
    assert line.objectName() == HSEP_OBJECT_NAME
    assert line.frameShape() is QFrame.Shape.HLine
    assert line.maximumHeight() == 1


def test_install_shadow_attaches_drop_shadow(qtbot: object) -> None:
    """``install_shadow`` installe un ``QGraphicsDropShadowEffect`` configuré."""
    del qtbot
    widget = QFrame()
    install_shadow(widget)
    effect = widget.graphicsEffect()
    assert isinstance(effect, QGraphicsDropShadowEffect)
    assert effect.blurRadius() > 0


def test_reapply_card_shadows_targets_only_cards(qtbot: object) -> None:
    """``reapply_card_shadows`` ne ré-installe une ombre que sur les widgets ``card``."""
    del qtbot
    app = QApplication.instance()
    assert isinstance(app, QApplication)

    card_widget = QFrame()
    card_widget.setObjectName(CARD_OBJECT_NAME)
    install_shadow(card_widget)

    other_widget = QFrame()
    other_widget.setObjectName("notACard")

    reapply_card_shadows(app)

    # Card : effet présent.
    card_effect = card_widget.graphicsEffect()
    assert isinstance(card_effect, QGraphicsDropShadowEffect)
    # Autre widget : pas d'effet installé.
    assert other_widget.graphicsEffect() is None


def test_frenchify_button_box_translates_standard_buttons(qtbot: object) -> None:
    """``frenchify_button_box`` remplace ``Save/Cancel/Close`` par leur FR."""
    del qtbot
    box = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Save
        | QDialogButtonBox.StandardButton.Cancel
        | QDialogButtonBox.StandardButton.Close
    )
    frenchify_button_box(box)
    save_btn = box.button(QDialogButtonBox.StandardButton.Save)
    cancel_btn = box.button(QDialogButtonBox.StandardButton.Cancel)
    close_btn = box.button(QDialogButtonBox.StandardButton.Close)
    assert save_btn is not None and save_btn.text() == "Enregistrer"
    assert cancel_btn is not None and cancel_btn.text() == "Annuler"
    assert close_btn is not None and close_btn.text() == "Fermer"


def test_install_shadow_uses_current_palette_color(qtbot: object) -> None:
    """L'ombre installée utilise la couleur de ``current_palette().shadow_card``."""
    del qtbot
    set_current_palette(LIGHT_TOKENS)
    widget = QFrame()
    install_shadow(widget)
    effect = widget.graphicsEffect()
    assert isinstance(effect, QGraphicsDropShadowEffect)
    color = QColor(effect.color())
    expected = current_palette().shadow_card.color
    assert (color.red(), color.green(), color.blue(), color.alpha()) == (
        expected.red(),
        expected.green(),
        expected.blue(),
        expected.alpha(),
    )
