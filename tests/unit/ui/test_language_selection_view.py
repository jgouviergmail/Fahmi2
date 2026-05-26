"""Tests du widget unifié de sélection des langues (principale + incluses)."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fahmi2.domain.enums import Language
from fahmi2.ui.widgets.language_selection_view import LanguageSelectionView


def _view(qtbot: QtBot) -> LanguageSelectionView:
    view = LanguageSelectionView((Language.FR, Language.EN))
    qtbot.addWidget(view)
    return view


def test_default_first_language_is_primary_and_included(qtbot: QtBot) -> None:
    view = _view(qtbot)
    assert view.primary_language() is Language.FR
    assert view.output_languages() == (Language.FR,)


def test_set_selection_reflects_primary_and_outputs(qtbot: QtBot) -> None:
    view = _view(qtbot)
    view.set_selection(primary=Language.FR, outputs=(Language.FR, Language.EN))
    assert view.primary_language() is Language.FR
    assert set(view.output_languages()) == {Language.FR, Language.EN}


def test_primary_is_always_included(qtbot: QtBot) -> None:
    # EN principale → EN inclus même si seul FR était coché au départ.
    view = _view(qtbot)
    view.set_selection(primary=Language.EN, outputs=())
    assert view.primary_language() is Language.EN
    assert Language.EN in view.output_languages()


def test_primary_checkbox_is_locked_others_free(qtbot: QtBot) -> None:
    view = _view(qtbot)
    view.set_selection(primary=Language.FR, outputs=(Language.FR, Language.EN))
    # La case de la principale est verrouillée (toujours incluse)…
    assert not view._checks[Language.FR].isEnabled()  # noqa: SLF001
    # … les autres restent librement décochables.
    assert view._checks[Language.EN].isEnabled()  # noqa: SLF001


def test_changing_primary_relocks_and_frees(qtbot: QtBot) -> None:
    view = _view(qtbot)
    view.set_selection(primary=Language.EN, outputs=(Language.FR, Language.EN))
    assert not view._checks[Language.EN].isEnabled()  # noqa: SLF001 — EN verrouillée
    assert view._checks[Language.FR].isEnabled()  # noqa: SLF001 — FR libérée
