"""Tests du viewmodel d'état/fraîcheur de la pédagogie."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fahmi2.app.project_service import ProjectService
from fahmi2.domain.enums import Language, RunStatus, SupportType
from fahmi2.domain.generation import (
    GENERATION_OUTPUT_SUBDIR,
    GENERATION_WORKSPACE_SUBDIR,
    consolidated_doc_filename,
)
from fahmi2.domain.ids import RunId
from fahmi2.domain.pedagogy import PEDAGOGY_WORKSPACE_SUBDIR
from fahmi2.domain.run import Run
from fahmi2.infra.storage.fs_artifacts import FsArtifactStore
from fahmi2.infra.storage.sqlite_state import SqliteState
from fahmi2.pedagogy.artifact_writer import artifact_json_path
from fahmi2.pedagogy.manifest import (
    PedagogyManifest,
    compute_settings_hash,
    write_manifest,
)
from fahmi2.pedagogy.sources import source_mtime_ns
from fahmi2.ui.viewmodels.pedagogy_state import PedagogyState, PedagogyStateViewModel


def _write_consolidated(ws: Path, language: Language) -> Path:
    doc = (
        ws
        / GENERATION_WORKSPACE_SUBDIR
        / GENERATION_OUTPUT_SUBDIR
        / consolidated_doc_filename(language)
    )
    FsArtifactStore().write_text_atomic(doc, "# Cours\n\n# 1. Bases\n\nContenu.\n")
    return doc


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


def test_not_configured(tmp_path: Path, make_generation_settings: Any) -> None:
    state = SqliteState(tmp_path / "t.db")
    service = ProjectService(state)
    project = service.create_project(
        name="P", workspace_folder=tmp_path / "ws",
        generation=make_generation_settings(),
    )
    info = PedagogyStateViewModel(project_service=service).compute(project)
    assert info.state is PedagogyState.NOT_CONFIGURED
    assert info.can_generate is False


def test_generation_required_when_no_completed_run(
    tmp_path: Path, make_generation_settings: Any, make_pedagogy_settings: Any
) -> None:
    state = SqliteState(tmp_path / "t.db")
    service = ProjectService(state)
    project = service.create_project(
        name="P", workspace_folder=tmp_path / "ws",
        generation=make_generation_settings(), pedagogy=make_pedagogy_settings(),
    )
    info = PedagogyStateViewModel(project_service=service).compute(project)
    assert info.state is PedagogyState.GENERATION_REQUIRED
    assert info.can_generate is False


def test_ready_when_source_present_nothing_generated(
    tmp_path: Path, make_generation_settings: Any, make_pedagogy_settings: Any
) -> None:
    state = SqliteState(tmp_path / "t.db")
    service = ProjectService(state)
    ws = tmp_path / "ws"
    project = service.create_project(
        name="P", workspace_folder=ws,
        generation=make_generation_settings(),
        pedagogy=make_pedagogy_settings(languages=(Language.FR,)),
    )
    _seed_completed_run(state, project.id, make_generation_settings())
    _write_consolidated(ws, Language.FR)
    info = PedagogyStateViewModel(project_service=service).compute(project)
    assert info.state is PedagogyState.READY
    assert info.can_generate is True


def test_up_to_date_when_fresh(
    tmp_path: Path, make_generation_settings: Any, make_pedagogy_settings: Any
) -> None:
    state = SqliteState(tmp_path / "t.db")
    service = ProjectService(state)
    ws = tmp_path / "ws"
    pedagogy = make_pedagogy_settings(
        selected_supports=frozenset({SupportType.FLASHCARDS_CONCEPTS}),
        languages=(Language.FR,),
    )
    project = service.create_project(
        name="P", workspace_folder=ws,
        generation=make_generation_settings(), pedagogy=pedagogy,
    )
    _seed_completed_run(state, project.id, make_generation_settings())
    _write_consolidated(ws, Language.FR)
    gen_out = ws / GENERATION_WORKSPACE_SUBDIR / GENERATION_OUTPUT_SUBDIR
    pedagogy_dir = ws / PEDAGOGY_WORKSPACE_SUBDIR
    artifacts = FsArtifactStore()
    artifacts.write_json_atomic(
        artifact_json_path(pedagogy_dir, SupportType.FLASHCARDS_CONCEPTS, Language.FR),
        {"items": []},
    )
    manifest = PedagogyManifest()
    manifest.record(
        SupportType.FLASHCARDS_CONCEPTS,
        Language.FR,
        settings_hash=compute_settings_hash(pedagogy),
        source_mtime_ns=source_mtime_ns(gen_out, Language.FR),
    )
    write_manifest(artifacts, pedagogy_dir, manifest)
    info = PedagogyStateViewModel(project_service=service).compute(project)
    assert info.state is PedagogyState.UP_TO_DATE


def test_stale_when_settings_changed(
    tmp_path: Path, make_generation_settings: Any, make_pedagogy_settings: Any
) -> None:
    state = SqliteState(tmp_path / "t.db")
    service = ProjectService(state)
    ws = tmp_path / "ws"
    pedagogy = make_pedagogy_settings(
        selected_supports=frozenset({SupportType.FLASHCARDS_CONCEPTS}),
        languages=(Language.FR,),
    )
    project = service.create_project(
        name="P", workspace_folder=ws,
        generation=make_generation_settings(), pedagogy=pedagogy,
    )
    _seed_completed_run(state, project.id, make_generation_settings())
    _write_consolidated(ws, Language.FR)
    pedagogy_dir = ws / PEDAGOGY_WORKSPACE_SUBDIR
    artifacts = FsArtifactStore()
    artifacts.write_json_atomic(
        artifact_json_path(pedagogy_dir, SupportType.FLASHCARDS_CONCEPTS, Language.FR),
        {"items": []},
    )
    manifest = PedagogyManifest()
    manifest.record(
        SupportType.FLASHCARDS_CONCEPTS,
        Language.FR,
        settings_hash="ancien-hash-different",
        source_mtime_ns=123,
    )
    write_manifest(artifacts, pedagogy_dir, manifest)
    info = PedagogyStateViewModel(project_service=service).compute(project)
    assert info.state is PedagogyState.STALE
