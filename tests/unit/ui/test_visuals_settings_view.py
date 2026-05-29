"""Smoke tests du dialogue VisualsSettingsView."""

from __future__ import annotations

from pytestqt.qtbot import QtBot

from fahmi2.domain.enums import DiagramType, SupportDensity
from fahmi2.domain.visuals import VisualsSettings
from fahmi2.ui.dialogs.visuals_settings_view import VisualsSettingsView


def test_default_build_is_valid(qtbot: QtBot) -> None:
    dialog = VisualsSettingsView()
    qtbot.addWidget(dialog)
    settings = dialog.build_settings()
    assert settings is not None
    assert settings.produce_knowledge_map is True
    assert settings.produce_diagrams is True
    assert settings.diagram_types == frozenset(DiagramType)


def test_build_returns_none_when_no_deliverable(qtbot: QtBot) -> None:
    dialog = VisualsSettingsView()
    qtbot.addWidget(dialog)
    dialog._knowledge_map_check.setChecked(False)  # noqa: SLF001
    dialog._diagrams_check.setChecked(False)  # noqa: SLF001
    assert dialog.build_settings() is None


def test_build_returns_none_when_diagrams_without_types(qtbot: QtBot) -> None:
    dialog = VisualsSettingsView()
    qtbot.addWidget(dialog)
    dialog._knowledge_map_check.setChecked(False)  # noqa: SLF001
    dialog._diagrams_check.setChecked(True)  # noqa: SLF001
    for cb in dialog._diagram_type_checks.values():  # noqa: SLF001
        cb.setChecked(False)
    assert dialog.build_settings() is None


def test_roundtrip_from_initial(qtbot: QtBot) -> None:
    initial = VisualsSettings(
        produce_knowledge_map=True,
        produce_diagrams=False,
        density=SupportDensity.DENSE,
        diagram_types=frozenset({DiagramType.FLOWCHART}),
        llm_workers=24,
    )
    dialog = VisualsSettingsView(initial=initial)
    qtbot.addWidget(dialog)
    rebuilt = dialog.build_settings()
    assert rebuilt is not None
    assert rebuilt.produce_knowledge_map is True
    assert rebuilt.produce_diagrams is False
    assert rebuilt.density is SupportDensity.DENSE
    assert rebuilt.llm_workers == 24
