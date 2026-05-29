"""Tests du VisualsController (logique testable + worker synchrone)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from PySide6.QtWidgets import QDialog, QMessageBox, QWidget
from pytestqt.qtbot import QtBot

from fahmi2.app.project_service import ProjectService
from fahmi2.app.secrets_service import SecretsService
from fahmi2.core.config.paths import AppPaths
from fahmi2.domain.enums import Language, PhaseStatus, RunStatus
from fahmi2.domain.generation import (
    GENERATION_OUTPUT_SUBDIR,
    GENERATION_WORKSPACE_SUBDIR,
    consolidated_doc_filename,
)
from fahmi2.domain.ids import RunId
from fahmi2.domain.run import Run
from fahmi2.domain.visuals import VisualsSettings
from fahmi2.infra.secrets.interface import InMemorySecretsStore
from fahmi2.infra.storage.fs_artifacts import FsArtifactStore
from fahmi2.infra.storage.sqlite_state import SqliteState
from fahmi2.ui import visuals_controller as vc_module
from fahmi2.ui.viewmodels.visuals_state import VisualsState
from fahmi2.ui.visuals_controller import VisualsController, _visuals_event_to_log
from fahmi2.ui.widgets.logs_dock import LogsDock
from fahmi2.ui.widgets.project_header_bar import ProjectHeaderBar
from fahmi2.ui.widgets.visuals_progress_view import VisualsProgressView
from fahmi2.visuals.events import (
    VisualsGenerationFinished,
    VisualsLanguageFinished,
    VisualsLanguageStarted,
)


def _app_paths(tmp_path: Path) -> AppPaths:
    return AppPaths(appdata=tmp_path / "appdata", localappdata=tmp_path / "local")


def _make_controller(
    qtbot: QtBot, tmp_path: Path, *, with_key: bool = True
) -> tuple[VisualsController, ProjectService, SqliteState]:
    state = SqliteState(tmp_path / "t.db")
    project_service = ProjectService(state)
    secrets_service = SecretsService(InMemorySecretsStore())
    if with_key:
        secrets_service.set_deepseek_api_key("test-key-1234")
    window = QWidget()
    qtbot.addWidget(window)
    header = ProjectHeaderBar()
    qtbot.addWidget(header)
    progress = VisualsProgressView()
    qtbot.addWidget(progress)
    logs = LogsDock()
    qtbot.addWidget(logs)
    controller = VisualsController(
        header_bar=header,
        progress_view=progress,
        logs_dock=logs,
        window=window,
        project_service=project_service,
        secrets_service=secrets_service,
        state=state,
        app_paths=_app_paths(tmp_path),
    )
    return controller, project_service, state


def test_event_to_log_mapping() -> None:
    now = datetime.now(tz=UTC)
    started = _visuals_event_to_log(
        VisualsLanguageStarted(timestamp=now, language=Language.FR)
    )
    assert started.code == "VISUALS_LANGUAGE_STARTED"
    finished = _visuals_event_to_log(
        VisualsLanguageFinished(
            timestamp=now,
            language=Language.FR,
            status=PhaseStatus.SUCCEEDED,
            cost_usd=0.1,
            error=None,
        )
    )
    assert finished.code == "VISUALS_LANGUAGE_FINISHED"
    overall = _visuals_event_to_log(
        VisualsGenerationFinished(
            timestamp=now, status=RunStatus.COMPLETED, total_cost_usd=0.2
        )
    )
    assert overall.code == "VISUALS_FINISHED"


def test_open_settings_persists_and_preserves_generation(
    qtbot: QtBot,
    tmp_path: Path,
    monkeypatch: Any,
    make_generation_settings: Any,
) -> None:
    controller, project_service, _ = _make_controller(qtbot, tmp_path)
    project = project_service.create_project(
        name="P",
        workspace_folder=tmp_path / "ws",
        generation=make_generation_settings(),
    )
    controller.on_project_selected(project.id)
    chosen = VisualsSettings(produce_diagrams=False)

    class _FakeDialog:
        def __init__(self, *args: Any, **kwargs: Any) -> None:
            del args, kwargs

        def exec(self) -> int:
            return QDialog.DialogCode.Accepted

        def get_visuals_settings(self) -> Any:
            return chosen

    monkeypatch.setattr(vc_module, "VisualsSettingsView", _FakeDialog)
    controller.open_visuals_settings()

    reloaded = project_service.get_project(project.id)
    assert reloaded is not None
    assert reloaded.visuals is not None
    assert reloaded.visuals.produce_diagrams is False
    assert reloaded.generation is not None  # généré préservé


def test_state_viewmodel_ready_after_source(
    qtbot: QtBot, tmp_path: Path, make_generation_settings: Any
) -> None:
    controller, project_service, state = _make_controller(qtbot, tmp_path)
    ws = tmp_path / "ws"
    project = project_service.create_project(
        name="P",
        workspace_folder=ws,
        generation=make_generation_settings(),
    )
    project = project.with_visuals(VisualsSettings())
    state.upsert_project(project)
    _seed_completed_run(state, project.id, make_generation_settings())
    _write_consolidated(ws, Language.FR)
    controller.on_project_selected(project.id)
    info = controller._state_vm.compute(project)  # noqa: SLF001
    assert info.state is VisualsState.READY


def test_on_project_selected_shows_preview(
    qtbot: QtBot, tmp_path: Path, make_generation_settings: Any
) -> None:
    controller, project_service, state = _make_controller(qtbot, tmp_path)
    project = project_service.create_project(
        name="P",
        workspace_folder=tmp_path / "ws",
        generation=make_generation_settings(),
    )
    project = project.with_visuals(VisualsSettings())
    state.upsert_project(project)
    controller.on_project_selected(project.id)
    # Une ligne par livrable activé (carte + diagrammes), même sans génération.
    assert controller._progress_view.row_count() == 2  # noqa: SLF001


def test_clear_current_project_resets_cockpit(
    qtbot: QtBot, tmp_path: Path, make_generation_settings: Any
) -> None:
    controller, project_service, state = _make_controller(qtbot, tmp_path)
    project = project_service.create_project(
        name="P",
        workspace_folder=tmp_path / "ws",
        generation=make_generation_settings(),
    )
    project = project.with_visuals(VisualsSettings())
    state.upsert_project(project)
    controller.on_project_selected(project.id)
    assert controller.current_project_id == project.id
    controller.clear_current_project()
    assert controller._progress_view.banner_text() == ""  # noqa: SLF001
    assert controller._progress_view.row_count() == 0  # noqa: SLF001
    assert controller.current_project_id is None


def test_reset_visuals_removes_dir_and_refreshes(
    qtbot: QtBot, tmp_path: Path, monkeypatch: Any, make_generation_settings: Any
) -> None:
    controller, project_service, state = _make_controller(qtbot, tmp_path)
    project = project_service.create_project(
        name="P",
        workspace_folder=tmp_path / "ws",
        generation=make_generation_settings(),
    )
    project = project.with_visuals(VisualsSettings())
    state.upsert_project(project)
    controller.on_project_selected(project.id)
    visuals_dir = tmp_path / "ws" / "visuals"
    (visuals_dir / "output").mkdir(parents=True, exist_ok=True)
    (visuals_dir / "manifest.json").write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        QMessageBox, "question", lambda *a, **k: QMessageBox.StandardButton.Yes
    )
    emitted: list[int] = []
    controller.run_state_changed.connect(lambda: emitted.append(1))
    controller.reset_visuals()
    assert not visuals_dir.exists()
    assert emitted


def _seed_completed_run(state: SqliteState, project_id: Any, settings: Any) -> None:
    state.upsert_run(
        Run(
            id=RunId.new(),
            project_id=project_id,
            started_at=datetime.now(tz=UTC),
            status=RunStatus.COMPLETED,
            settings_snapshot=settings,
        )
    )


def _write_consolidated(ws: Path, language: Language) -> None:
    doc = (
        ws
        / GENERATION_WORKSPACE_SUBDIR
        / GENERATION_OUTPUT_SUBDIR
        / consolidated_doc_filename(language)
    )
    FsArtifactStore().write_text_atomic(doc, "# Cours\n\n# 1. Bases\n\nContenu.\n")
