"""Tests du viewmodel d'état/fraîcheur des Visualisations."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fahmi2.app.project_service import ProjectService
from fahmi2.domain.enums import Language, RunStatus
from fahmi2.domain.generation import (
    GENERATION_OUTPUT_SUBDIR,
    GENERATION_WORKSPACE_SUBDIR,
    consolidated_doc_filename,
)
from fahmi2.domain.ids import RunId
from fahmi2.domain.run import Run
from fahmi2.domain.visuals import (
    VISUALS_OUTPUT_SUBDIR,
    VISUALS_WORKSPACE_SUBDIR,
    VisualsSettings,
    diagrams_filename,
    knowledge_map_filename,
)
from fahmi2.infra.storage.fs_artifacts import FsArtifactStore
from fahmi2.infra.storage.sqlite_state import SqliteState
from fahmi2.ui.viewmodels.visuals_state import VisualsState, VisualsStateViewModel
from fahmi2.visuals.manifest import (
    VisualsManifest,
    compute_settings_hash,
    write_manifest,
)
from fahmi2.visuals.sources import source_mtime_ns

_STORE = FsArtifactStore()


def _output_dir(ws: Path) -> Path:
    return ws / GENERATION_WORKSPACE_SUBDIR / GENERATION_OUTPUT_SUBDIR


def _write_consolidated(ws: Path, language: Language) -> None:
    doc = _output_dir(ws) / consolidated_doc_filename(language)
    _STORE.write_text_atomic(doc, "# Cours\n\n# 1. Bases\n\nContenu du chapitre.\n")


def _seed_run(state: SqliteState, project_id: Any, settings: Any) -> None:
    state.upsert_run(
        Run(
            id=RunId.new(),
            project_id=project_id,
            started_at=datetime.now(tz=UTC),
            status=RunStatus.COMPLETED,
            settings_snapshot=settings,
        )
    )


def _configured_project(
    tmp_path: Path, make_generation_settings: Any
) -> tuple[ProjectService, Any]:
    state = SqliteState(tmp_path / "t.db")
    service = ProjectService(state)
    project = service.create_project(
        name="P", workspace_folder=tmp_path / "ws",
        generation=make_generation_settings(),
    )
    project = project.with_visuals(VisualsSettings())
    state.upsert_project(project)
    return service, project


def test_not_configured(tmp_path: Path, make_generation_settings: Any) -> None:
    state = SqliteState(tmp_path / "t.db")
    service = ProjectService(state)
    project = service.create_project(
        name="P", workspace_folder=tmp_path / "ws",
        generation=make_generation_settings(),
    )
    info = VisualsStateViewModel(project_service=service).compute(project)
    assert info.state is VisualsState.NOT_CONFIGURED
    assert info.can_generate is False


def test_generation_required_sans_run(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    service, project = _configured_project(tmp_path, make_generation_settings)
    info = VisualsStateViewModel(project_service=service).compute(project)
    assert info.state is VisualsState.GENERATION_REQUIRED


def test_generation_required_sans_document(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    service, project = _configured_project(tmp_path, make_generation_settings)
    _seed_run(service._state, project.id, project.generation)  # noqa: SLF001
    info = VisualsStateViewModel(project_service=service).compute(project)
    assert info.state is VisualsState.GENERATION_REQUIRED


def test_ready_quand_source_presente_sans_sortie(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    service, project = _configured_project(tmp_path, make_generation_settings)
    _seed_run(service._state, project.id, project.generation)  # noqa: SLF001
    _write_consolidated(tmp_path / "ws", Language.FR)
    info = VisualsStateViewModel(project_service=service).compute(project)
    assert info.state is VisualsState.READY
    assert info.can_generate is True


def _record_fresh_manifest(ws: Path, visuals: VisualsSettings) -> None:
    out_dir = ws / VISUALS_WORKSPACE_SUBDIR / VISUALS_OUTPUT_SUBDIR
    _STORE.write_text_atomic(out_dir / knowledge_map_filename(Language.FR), "<html>")
    _STORE.write_text_atomic(out_dir / diagrams_filename(Language.FR), "<html>")
    mtime = source_mtime_ns(_output_dir(ws), Language.FR)
    manifest = VisualsManifest()
    manifest.record(
        Language.FR,
        settings_hash=compute_settings_hash(visuals),
        structure_mtime_ns=mtime,
        glossary_mtime_ns=None,
        content_mtime_ns=mtime,
    )
    write_manifest(_STORE, ws / VISUALS_WORKSPACE_SUBDIR, manifest)


def test_up_to_date(tmp_path: Path, make_generation_settings: Any) -> None:
    service, project = _configured_project(tmp_path, make_generation_settings)
    _seed_run(service._state, project.id, project.generation)  # noqa: SLF001
    _write_consolidated(tmp_path / "ws", Language.FR)
    _record_fresh_manifest(tmp_path / "ws", project.visuals)
    info = VisualsStateViewModel(project_service=service).compute(project)
    assert info.state is VisualsState.UP_TO_DATE


def test_stale_quand_sorties_sans_manifeste(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    service, project = _configured_project(tmp_path, make_generation_settings)
    _seed_run(service._state, project.id, project.generation)  # noqa: SLF001
    _write_consolidated(tmp_path / "ws", Language.FR)
    out_dir = tmp_path / "ws" / VISUALS_WORKSPACE_SUBDIR / VISUALS_OUTPUT_SUBDIR
    _STORE.write_text_atomic(out_dir / knowledge_map_filename(Language.FR), "<html>")
    _STORE.write_text_atomic(out_dir / diagrams_filename(Language.FR), "<html>")
    info = VisualsStateViewModel(project_service=service).compute(project)
    assert info.state is VisualsState.STALE
