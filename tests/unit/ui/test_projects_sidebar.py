"""Tests de la sidebar projets (rendu custom + sélection + mise à jour live)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from PySide6.QtWidgets import QLabel
from pytestqt.qtbot import QtBot

from fahmi2.domain.enums import RunStatus
from fahmi2.domain.ids import ProjectId
from fahmi2.domain.project import Project
from fahmi2.ui.widgets.projects_sidebar import ProjectListEntry, ProjectsSidebar


def _project(name: str) -> Project:
    return Project(
        id=ProjectId.new(),
        name=name,
        workspace_folder=Path("."),
        created_at=datetime.now(tz=UTC),
    )


def _name_label_text(sidebar: ProjectsSidebar, row: int) -> str:
    """Retourne le texte du label de nom du projet à la ligne ``row``."""
    widget = sidebar.itemWidget(sidebar.item(row))
    assert widget is not None
    labels = widget.findChildren(QLabel)
    # Le label de nom porte ``objectName="projectListName"``.
    for label in labels:
        if label.objectName() == "projectListName":
            return label.text()
    raise AssertionError("nom du projet introuvable dans le widget")


def _subtitle_text(sidebar: ProjectsSidebar, row: int) -> str:
    """Retourne le texte du sous-libellé à la ligne ``row``."""
    widget = sidebar.itemWidget(sidebar.item(row))
    assert widget is not None
    labels = widget.findChildren(QLabel)
    for label in labels:
        if label.objectName() == "projectListSubtitle":
            return label.text()
    raise AssertionError("sous-libellé introuvable dans le widget")


def test_set_projects_renders_name_and_subtitle(qtbot: QtBot) -> None:
    """Chaque entrée rend un widget custom avec nom + sous-libellé en clair."""
    sidebar = ProjectsSidebar()
    qtbot.addWidget(sidebar)
    project = _project("Cours")
    sidebar.set_projects(
        [ProjectListEntry(project, RunStatus.COMPLETED, RunStatus.RUNNING)]
    )
    assert sidebar.count() == 1
    assert _name_label_text(sidebar, 0) == "Cours"
    subtitle = _subtitle_text(sidebar, 0)
    # « Génération terminée · Supports en cours » (cas lowercased)
    assert "génération" in subtitle.lower()
    assert "supports" in subtitle.lower()


def test_update_statuses_preserves_selection_and_refreshes_subtitle(
    qtbot: QtBot,
) -> None:
    """``update_statuses`` met à jour le sous-libellé sans casser la sélection."""
    sidebar = ProjectsSidebar()
    qtbot.addWidget(sidebar)
    project = _project("Cours")
    sidebar.set_projects(
        [ProjectListEntry(project, RunStatus.CREATED, RunStatus.CREATED)]
    )
    sidebar.select_project(project.id)
    sidebar.update_statuses(
        [ProjectListEntry(project, RunStatus.RUNNING, RunStatus.CREATED)]
    )
    assert sidebar.current_project_id() == project.id
    subtitle = _subtitle_text(sidebar, 0)
    assert "en cours" in subtitle.lower()


def test_current_project_id_none_when_empty(qtbot: QtBot) -> None:
    """Liste vide → pas de projet sélectionné."""
    sidebar = ProjectsSidebar()
    qtbot.addWidget(sidebar)
    sidebar.set_projects([])
    assert sidebar.current_project_id() is None
