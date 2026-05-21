"""Tests de la sidebar projets (icônes de statut G/P + sélection)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from pytestqt.qtbot import QtBot

from fahmi2.domain.enums import RunStatus
from fahmi2.domain.ids import ProjectId
from fahmi2.domain.project import Project
from fahmi2.ui.status_labels import run_status_icon
from fahmi2.ui.widgets.projects_sidebar import ProjectListEntry, ProjectsSidebar


def _project(name: str) -> Project:
    return Project(
        id=ProjectId.new(),
        name=name,
        workspace_folder=Path("."),
        created_at=datetime.now(tz=UTC),
    )


def test_set_projects_prefixes_status_icons(qtbot: QtBot) -> None:
    sidebar = ProjectsSidebar()
    qtbot.addWidget(sidebar)
    project = _project("Cours")
    sidebar.set_projects(
        [ProjectListEntry(project, RunStatus.COMPLETED, RunStatus.RUNNING)]
    )
    label = sidebar.item(0).text()
    assert run_status_icon(RunStatus.COMPLETED) in label
    assert run_status_icon(RunStatus.RUNNING) in label
    assert "Cours" in label


def test_update_statuses_preserves_selection(qtbot: QtBot) -> None:
    sidebar = ProjectsSidebar()
    qtbot.addWidget(sidebar)
    project = _project("Cours")
    sidebar.set_projects(
        [ProjectListEntry(project, RunStatus.CREATED, RunStatus.CREATED)]
    )
    sidebar.select_project(project.id)
    # Met à jour le statut sans reconstruire : la sélection est préservée.
    sidebar.update_statuses(
        [ProjectListEntry(project, RunStatus.RUNNING, RunStatus.CREATED)]
    )
    assert sidebar.current_project_id() == project.id
    assert run_status_icon(RunStatus.RUNNING) in sidebar.item(0).text()


def test_current_project_id_none_when_empty(qtbot: QtBot) -> None:
    sidebar = ProjectsSidebar()
    qtbot.addWidget(sidebar)
    sidebar.set_projects([])
    assert sidebar.current_project_id() is None
