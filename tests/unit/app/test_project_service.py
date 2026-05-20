"""Tests de ProjectService."""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fahmi2.app.project_service import ProjectService
from fahmi2.domain.enums import RunStatus
from fahmi2.domain.ids import ProjectId, RunId
from fahmi2.domain.run import Run
from fahmi2.infra.storage.sqlite_state import SqliteState


def test_create_project_persists_and_returns(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    state = SqliteState(tmp_path / "t.db")
    service = ProjectService(state)
    project = service.create_project(
        name="Mon Cours",
        workspace_folder=tmp_path / "ws",
        generation=make_generation_settings(),
    )
    assert project.id.value
    loaded = service.get_project(project.id)
    assert loaded is not None
    assert loaded.name == "Mon Cours"
    assert loaded.generation is not None


def test_create_project_without_generation_is_none(
    tmp_path: Path,
) -> None:
    state = SqliteState(tmp_path / "t.db")
    service = ProjectService(state)
    project = service.create_project(name="Vide", workspace_folder=tmp_path / "ws")
    loaded = service.get_project(project.id)
    assert loaded is not None
    assert loaded.generation is None


def test_list_projects_returns_all(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    state = SqliteState(tmp_path / "t.db")
    service = ProjectService(state)
    service.create_project(
        name="A", workspace_folder=tmp_path / "a", generation=make_generation_settings()
    )
    service.create_project(
        name="B", workspace_folder=tmp_path / "b", generation=make_generation_settings()
    )
    names = {p.name for p in service.list_projects()}
    assert names == {"A", "B"}


def test_delete_project_removes_it(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    state = SqliteState(tmp_path / "t.db")
    service = ProjectService(state)
    project = service.create_project(
        name="X", workspace_folder=tmp_path / "ws", generation=make_generation_settings()
    )
    service.delete_project(project.id)
    assert service.get_project(project.id) is None


def test_get_unknown_project_returns_none(tmp_path: Path) -> None:
    state = SqliteState(tmp_path / "t.db")
    service = ProjectService(state)
    assert service.get_project(ProjectId.new()) is None


def test_list_runs_empty_for_new_project(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    state = SqliteState(tmp_path / "t.db")
    service = ProjectService(state)
    project = service.create_project(
        name="X", workspace_folder=tmp_path / "ws", generation=make_generation_settings()
    )
    assert service.list_runs(project.id) == []


def test_get_last_run_returns_none_when_empty(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    state = SqliteState(tmp_path / "t.db")
    service = ProjectService(state)
    project = service.create_project(
        name="X", workspace_folder=tmp_path / "ws", generation=make_generation_settings()
    )
    assert service.get_last_run(project.id) is None


def test_get_last_completed_run(tmp_path: Path, make_generation_settings: Any) -> None:
    state = SqliteState(tmp_path / "t.db")
    service = ProjectService(state)
    project = service.create_project(
        name="X", workspace_folder=tmp_path / "ws", generation=make_generation_settings()
    )
    settings = make_generation_settings()
    failed = Run(
        id=RunId.new(),
        project_id=project.id,
        started_at=datetime.now(tz=UTC),
        status=RunStatus.FAILED,
        settings_snapshot=settings,
    )
    completed = Run(
        id=RunId.new(),
        project_id=project.id,
        started_at=datetime.now(tz=UTC),
        status=RunStatus.COMPLETED,
        settings_snapshot=settings,
    )
    state.upsert_run(failed)
    state.upsert_run(completed)
    last = service.get_last_completed_run(project.id)
    assert last is not None
    assert last.id == completed.id


def test_get_last_completed_run_none_when_no_completed(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    state = SqliteState(tmp_path / "t.db")
    service = ProjectService(state)
    project = service.create_project(
        name="X", workspace_folder=tmp_path / "ws", generation=make_generation_settings()
    )
    assert service.get_last_completed_run(project.id) is None
