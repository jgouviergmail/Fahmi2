"""Smoke tests du dialogue PedagogySettingsView."""

from __future__ import annotations

from typing import Any

from pytestqt.qtbot import QtBot

from fahmi2.domain.enums import (
    BloomObjective,
    Language,
    SupportDensity,
    SupportType,
    TargetAudience,
)
from fahmi2.ui.dialogs.pedagogy_settings_view import PedagogySettingsView


def test_build_settings_from_selection(qtbot: QtBot) -> None:
    dialog = PedagogySettingsView(available_languages=(Language.FR, Language.EN))
    qtbot.addWidget(dialog)
    dialog.select_support(SupportType.QCM, selected=True)
    dialog.select_language(Language.FR, selected=True)
    dialog.select_language(Language.EN, selected=False)
    settings = dialog.build_settings()
    assert settings is not None
    assert SupportType.QCM in settings.selected_supports
    assert settings.languages == (Language.FR,)


def test_roundtrip_from_initial(
    qtbot: QtBot, make_pedagogy_settings: Any
) -> None:
    initial = make_pedagogy_settings(
        selected_supports=frozenset({SupportType.KEY_POINTS}),
        target_audience=TargetAudience.MASTER_EXPERT,
        bloom_objective=BloomObjective.ANALYZE_BEYOND,
        density=SupportDensity.DENSE,
        languages=(Language.FR,),
    )
    dialog = PedagogySettingsView(
        available_languages=(Language.FR,), initial=initial
    )
    qtbot.addWidget(dialog)
    rebuilt = dialog.build_settings()
    assert rebuilt is not None
    assert rebuilt.selected_supports == frozenset({SupportType.KEY_POINTS})
    assert rebuilt.target_audience is TargetAudience.MASTER_EXPERT
    assert rebuilt.bloom_objective is BloomObjective.ANALYZE_BEYOND
    assert rebuilt.density is SupportDensity.DENSE


def test_build_returns_none_when_no_support(qtbot: QtBot) -> None:
    dialog = PedagogySettingsView(available_languages=(Language.FR,))
    qtbot.addWidget(dialog)
    dialog.select_language(Language.FR, selected=True)
    # Aucun support coché -> invalide -> None.
    assert dialog.build_settings() is None


def test_llm_workers_round_trips_through_view(
    qtbot: QtBot, make_pedagogy_settings: Any
) -> None:
    initial = make_pedagogy_settings(llm_workers=24)
    view = PedagogySettingsView(available_languages=(Language.FR,), initial=initial)
    qtbot.addWidget(view)
    built = view.build_settings()
    assert built is not None
    assert built.llm_workers == 24
