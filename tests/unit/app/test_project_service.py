"""Tests de ProjectService."""

from pathlib import Path
from typing import Any

from fahmi2.app.project_service import ProjectService
from fahmi2.domain.ids import ProjectId
from fahmi2.infra.storage.sqlite_state import SqliteState


def test_create_project_persists_and_returns(
    tmp_path: Path, make_settings: Any
) -> None:
    state = SqliteState(tmp_path / "t.db")
    service = ProjectService(state)
    project = service.create_project(make_settings(name="Mon Cours"))
    assert project.id.value
    loaded = service.get_project(project.id)
    assert loaded is not None
    assert loaded.settings.name == "Mon Cours"


def test_list_projects_returns_all(tmp_path: Path, make_settings: Any) -> None:
    state = SqliteState(tmp_path / "t.db")
    service = ProjectService(state)
    service.create_project(make_settings(name="A"))
    service.create_project(make_settings(name="B"))
    projects = service.list_projects()
    names = {p.settings.name for p in projects}
    assert names == {"A", "B"}


def test_delete_project_removes_it(tmp_path: Path, make_settings: Any) -> None:
    state = SqliteState(tmp_path / "t.db")
    service = ProjectService(state)
    project = service.create_project(make_settings())
    service.delete_project(project.id)
    assert service.get_project(project.id) is None


def test_get_unknown_project_returns_none(tmp_path: Path) -> None:
    state = SqliteState(tmp_path / "t.db")
    service = ProjectService(state)
    assert service.get_project(ProjectId.new()) is None


def test_list_runs_empty_for_new_project(
    tmp_path: Path, make_settings: Any
) -> None:
    state = SqliteState(tmp_path / "t.db")
    service = ProjectService(state)
    project = service.create_project(make_settings())
    assert service.list_runs(project.id) == []


def test_get_last_run_returns_none_when_empty(
    tmp_path: Path, make_settings: Any
) -> None:
    state = SqliteState(tmp_path / "t.db")
    service = ProjectService(state)
    project = service.create_project(make_settings())
    assert service.get_last_run(project.id) is None
