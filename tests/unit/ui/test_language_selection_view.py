"""Tests du widget unifié de sélection des langues (produites + principale)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fahmi2.domain.enums import Language
from fahmi2.ui.widgets.language_selection_view import LanguageSelectionView


def _view(qtbot: QtBot) -> LanguageSelectionView:
    view = LanguageSelectionView((Language.FR, Language.EN))
    qtbot.addWidget(view)
    return view


def test_language_selection_uses_display_labels(qtbot: QtBot) -> None:
    view = LanguageSelectionView(tuple(Language))
    qtbot.addWidget(view)
    labels = {view._checks[lang].text() for lang in Language}  # noqa: SLF001
    assert "Chinois" in labels
    assert "Arabe" in labels
    assert "fr" not in labels  # plus de code brut affiché


def test_default_first_language_is_primary_and_produced(qtbot: QtBot) -> None:
    view = _view(qtbot)
    assert view.primary_language() is Language.FR
    assert view.output_languages() == (Language.FR,)


def test_set_selection_reflects_primary_and_outputs(qtbot: QtBot) -> None:
    view = _view(qtbot)
    view.set_selection(primary=Language.FR, outputs=(Language.FR, Language.EN))
    assert view.primary_language() is Language.FR
    assert set(view.output_languages()) == {Language.FR, Language.EN}


def test_english_can_be_primary(qtbot: QtBot) -> None:
    view = _view(qtbot)
    view.set_selection(primary=Language.EN, outputs=(Language.FR, Language.EN))
    assert view.primary_language() is Language.EN
    assert set(view.output_languages()) == {Language.FR, Language.EN}


def test_primary_is_always_produced(qtbot: QtBot) -> None:
    # EN principale → EN produite même si absente des outputs fournis.
    view = _view(qtbot)
    view.set_selection(primary=Language.EN, outputs=())
    assert view.primary_language() is Language.EN
    assert Language.EN in view.output_languages()


def test_primary_combo_lists_only_produced(qtbot: QtBot) -> None:
    view = _view(qtbot)
    view.set_selection(primary=Language.FR, outputs=(Language.FR,))
    # Seul FR est produit → le combo principale ne propose que FR.
    assert view._primary_combo.count() == 1  # noqa: SLF001
    view._checks[Language.EN].setChecked(True)  # noqa: SLF001 — produit EN aussi
    assert view._primary_combo.count() == 2  # noqa: SLF001


def test_unchecking_last_language_is_reverted(qtbot: QtBot) -> None:
    view = _view(qtbot)
    view.set_selection(primary=Language.FR, outputs=(Language.FR,))
    view._checks[Language.FR].setChecked(False)  # noqa: SLF001 — tentative tout décocher
    # Au moins une langue reste produite : le décochage est annulé.
    assert view._checks[Language.FR].isChecked()  # noqa: SLF001
    assert view.output_languages() == (Language.FR,)


def test_primary_moves_when_its_language_unproduced(qtbot: QtBot) -> None:
    view = _view(qtbot)
    view.set_selection(primary=Language.FR, outputs=(Language.FR, Language.EN))
    view._checks[Language.FR].setChecked(False)  # noqa: SLF001 — FR n'est plus produit
    # La principale bascule sur une langue encore produite (EN).
    assert view.primary_language() is Language.EN
    assert Language.FR not in view.output_languages()
