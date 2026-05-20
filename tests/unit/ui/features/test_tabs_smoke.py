"""Smoke tests des onglets de fonctionnalité (pytest-qt)."""

from __future__ import annotations

from pathlib import Path

from pytestqt.qtbot import QtBot

from fahmi2.app.hardware_probe import HardwareInfo
from fahmi2.app.project_service import ProjectService
from fahmi2.app.secrets_service import SecretsService
from fahmi2.core.config.paths import AppPaths
from fahmi2.infra.secrets.interface import InMemorySecretsStore
from fahmi2.infra.storage.sqlite_state import SqliteState
from fahmi2.ui.features.feature import FeatureId
from fahmi2.ui.features.generation_tab import GenerationTab
from fahmi2.ui.features.pedagogy_tab import PedagogyTab
from fahmi2.ui.features.registry import FeatureRegistry
from fahmi2.ui.main_window import MainWindow


def _generation_tab(state: SqliteState, window: MainWindow) -> GenerationTab:
    return GenerationTab(
        logs_dock=window.logs_dock,
        window=window,
        project_service=ProjectService(state),
        secrets_service=SecretsService(InMemorySecretsStore()),
        hardware=HardwareInfo(cuda_available=False, gpu_name="", cuda_version=""),
        state=state,
        app_paths=AppPaths.default(),
    )


def test_main_window_shows_two_feature_tabs(qtbot: QtBot, tmp_path: Path) -> None:
    state = SqliteState(tmp_path / "t.db")
    window = MainWindow()
    qtbot.addWidget(window)
    generation_tab = _generation_tab(state, window)
    pedagogy_tab = PedagogyTab(window)
    window.set_feature_tabs(FeatureRegistry([generation_tab, pedagogy_tab]))

    assert generation_tab.feature_id is FeatureId.GENERATION
    assert pedagogy_tab.feature_id is FeatureId.PEDAGOGY
    assert window._tabs.count() == 2  # noqa: SLF001 — smoke d'assemblage


def test_pedagogy_tab_on_project_selected_is_noop(qtbot: QtBot) -> None:
    tab = PedagogyTab()
    qtbot.addWidget(tab.widget)
    tab.on_project_selected(None)  # ne lève pas
