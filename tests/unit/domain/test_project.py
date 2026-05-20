"""Tests de l'entité ``Project`` (identité minimale)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fahmi2.domain.ids import ProjectId
from fahmi2.domain.project import Project


def test_project_minimal_defaults() -> None:
    pid = ProjectId.new()
    created = datetime(2026, 5, 19, 12, 0, 0, tzinfo=UTC)
    project = Project(
        id=pid,
        name="Cours",
        workspace_folder=Path("./ws"),
        created_at=created,
    )
    assert project.id is pid
    assert project.name == "Cours"
    assert project.workspace_folder == Path("./ws")
    assert project.created_at == created
    assert project.generation is None
    assert project.last_run_at is None
    assert project.runs == ()


def test_project_with_generation(make_generation_settings: Any) -> None:
    project = Project(
        id=ProjectId.new(),
        name="Cours",
        workspace_folder=Path("./ws"),
        created_at=datetime.now(tz=UTC),
        generation=make_generation_settings(),
    )
    assert project.generation is not None
