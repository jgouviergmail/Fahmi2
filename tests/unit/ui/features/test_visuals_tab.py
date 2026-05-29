"""Smoke test de l'onglet VisualsTab réel."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtWidgets import QWidget
from pytestqt.qtbot import QtBot

from fahmi2.app.project_service import ProjectService
from fahmi2.app.secrets_service import SecretsService
from fahmi2.core.config.paths import AppPaths
from fahmi2.infra.secrets.interface import InMemorySecretsStore
from fahmi2.infra.storage.sqlite_state import SqliteState
from fahmi2.ui.features.feature import FeatureId
from fahmi2.ui.features.visuals_tab import VisualsTab
from fahmi2.ui.widgets.logs_dock import LogsDock


def test_visuals_tab_constructs_and_handles_selection(
    qtbot: QtBot, tmp_path: Path, make_generation_settings: Any
) -> None:
    window = QWidget()
    qtbot.addWidget(window)
    logs = LogsDock()
    qtbot.addWidget(logs)
    state = SqliteState(tmp_path / "t.db")
    project_service = ProjectService(state)
    tab = VisualsTab(
        logs_dock=logs,
        window=window,
        project_service=project_service,
        secrets_service=SecretsService(InMemorySecretsStore()),
        state=state,
        app_paths=AppPaths(appdata=tmp_path / "a", localappdata=tmp_path / "l"),
    )
    qtbot.addWidget(tab.widget)
    assert tab.feature_id is FeatureId.VISUALS
    assert tab.title == "Visualisations"
    assert tab.widget is not None

    project = project_service.create_project(
        name="P",
        workspace_folder=tmp_path / "ws",
        generation=make_generation_settings(),
    )
    # Ne doit pas lever (projet non configuré pour les visualisations).
    tab.on_project_selected(project.id)
    tab.on_project_selected(None)
