"""Tests du SqliteState : ouverture, schéma, CRUD, concurrence, migration."""

import json
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from fahmi2.core.errors.error_info import ErrorInfo
from fahmi2.core.errors.exceptions import StorageError
from fahmi2.core.errors.severity import Severity
from fahmi2.domain.enums import ExportFormat, PhaseId, PhaseStatus, RunStatus
from fahmi2.domain.ids import ProjectId, RunId, SourceId
from fahmi2.domain.pedagogy import DEFAULT_PEDAGOGY_LLM_WORKERS
from fahmi2.domain.phase import PhaseExecution
from fahmi2.domain.project import Project
from fahmi2.domain.run import Run
from fahmi2.infra.storage.sqlite_state import (
    SCHEMA_VERSION,
    SqliteState,
    _deserialize_generation_settings,
    _deserialize_pedagogy_settings,
    _serialize_generation_settings,
    _serialize_pedagogy_settings,
)


def _ts(s: str = "2026-05-19T12:00:00") -> datetime:
    return datetime.fromisoformat(s).replace(tzinfo=UTC)


def _make_project(make_generation_settings: Any) -> Project:
    return Project(
        id=ProjectId.new(),
        name="Test Project",
        workspace_folder=Path("./workspace"),
        created_at=_ts(),
        generation=make_generation_settings(),
    )


def _make_run(project: Project) -> Run:
    assert project.generation is not None
    return Run(
        id=RunId.new(),
        project_id=project.id,
        started_at=_ts(),
        status=RunStatus.CREATED,
        settings_snapshot=project.generation,
    )


# --- Tests ouverture / schéma -------------------------------------------------


def test_open_creates_database_file(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    with SqliteState(db_path):
        pass
    assert db_path.exists()


def test_wal_mode_enabled(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    with SqliteState(db_path) as state:
        cur = state._get_connection().execute("PRAGMA journal_mode")  # noqa: SLF001
        mode = cur.fetchone()[0]
    assert mode.lower() == "wal"


def test_schema_version_initialized(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    with SqliteState(db_path) as state:
        assert state.read_schema_version() == SCHEMA_VERSION


def test_reopen_existing_db_does_not_fail(tmp_path: Path) -> None:
    db_path = tmp_path / "test.db"
    with SqliteState(db_path):
        pass
    with SqliteState(db_path) as state:
        assert state.read_schema_version() == SCHEMA_VERSION


# --- Tests CRUD projects ------------------------------------------------------


def test_upsert_and_get_project(tmp_path: Path, make_generation_settings: Any) -> None:
    with SqliteState(tmp_path / "t.db") as state:
        project = _make_project(make_generation_settings)
        state.upsert_project(project)
        retrieved = state.get_project(project.id)
        assert retrieved is not None
        assert retrieved.id == project.id
        assert retrieved.name == project.name
        assert retrieved.workspace_folder == project.workspace_folder
        assert retrieved.generation is not None


def test_generation_export_formats_round_trip(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    with SqliteState(tmp_path / "t.db") as state:
        project = Project(
            id=ProjectId.new(),
            name="Export",
            workspace_folder=Path("./ws"),
            created_at=_ts(),
            generation=make_generation_settings(
                export_formats=frozenset({ExportFormat.PDF, ExportFormat.HTML})
            ),
        )
        state.upsert_project(project)
        retrieved = state.get_project(project.id)
        assert retrieved is not None
        assert retrieved.generation is not None
        assert retrieved.generation.export_formats == frozenset(
            {ExportFormat.PDF, ExportFormat.HTML}
        )


def test_generation_deserialize_lenient_without_export_formats(
    make_generation_settings: Any,
) -> None:
    # Un blob v2 antérieur (sans export_formats) retombe sur l'ensemble vide.
    payload = _serialize_generation_settings(make_generation_settings())
    del payload["export_formats"]
    gen = _deserialize_generation_settings(payload)
    assert gen.export_formats == frozenset()


def test_get_unknown_project_returns_none(tmp_path: Path) -> None:
    with SqliteState(tmp_path / "t.db") as state:
        assert state.get_project(ProjectId.new()) is None


def test_list_projects(tmp_path: Path, make_generation_settings: Any) -> None:
    with SqliteState(tmp_path / "t.db") as state:
        p1 = _make_project(make_generation_settings)
        p2 = _make_project(make_generation_settings)
        state.upsert_project(p1)
        state.upsert_project(p2)
        ids = {p.id for p in state.list_projects()}
        assert ids == {p1.id, p2.id}


def test_delete_project(tmp_path: Path, make_generation_settings: Any) -> None:
    with SqliteState(tmp_path / "t.db") as state:
        p = _make_project(make_generation_settings)
        state.upsert_project(p)
        state.delete_project(p.id)
        assert state.get_project(p.id) is None


def test_upsert_project_is_idempotent(tmp_path: Path, make_generation_settings: Any) -> None:
    with SqliteState(tmp_path / "t.db") as state:
        p = _make_project(make_generation_settings)
        state.upsert_project(p)
        state.upsert_project(p)
        assert len(state.list_projects()) == 1


# --- Tests CRUD runs ----------------------------------------------------------


def test_upsert_and_get_run(tmp_path: Path, make_generation_settings: Any) -> None:
    with SqliteState(tmp_path / "t.db") as state:
        project = _make_project(make_generation_settings)
        state.upsert_project(project)
        run = _make_run(project)
        state.upsert_run(run)
        retrieved = state.get_run(run.id)
        assert retrieved is not None
        assert retrieved.id == run.id
        assert retrieved.status is RunStatus.CREATED


def test_list_runs_for_project(tmp_path: Path, make_generation_settings: Any) -> None:
    with SqliteState(tmp_path / "t.db") as state:
        project = _make_project(make_generation_settings)
        state.upsert_project(project)
        r1 = _make_run(project)
        r2 = _make_run(project)
        state.upsert_run(r1)
        state.upsert_run(r2)
        ids = {r.id for r in state.list_runs_for_project(project.id)}
        assert ids == {r1.id, r2.id}


# --- Tests phase_executions ---------------------------------------------------


def test_upsert_and_get_phase_execution(tmp_path: Path, make_generation_settings: Any) -> None:
    with SqliteState(tmp_path / "t.db") as state:
        project = _make_project(make_generation_settings)
        state.upsert_project(project)
        run = _make_run(project)
        state.upsert_run(run)

        pe = PhaseExecution(
            phase_id=PhaseId.STT,
            status=PhaseStatus.SUCCEEDED,
            started_at=_ts(),
            finished_at=_ts("2026-05-19T12:01:00"),
            retry_count=2,
            cost_usd=0.05,
        )
        vid = SourceId.new()
        state.upsert_phase_execution(run.id, pe, source_id=vid)

        status = state.get_phase_status(run.id, PhaseId.STT, source_id=vid)
        assert status is PhaseStatus.SUCCEEDED


def test_phase_execution_batch_no_source_id(tmp_path: Path, make_generation_settings: Any) -> None:
    with SqliteState(tmp_path / "t.db") as state:
        project = _make_project(make_generation_settings)
        state.upsert_project(project)
        run = _make_run(project)
        state.upsert_run(run)
        pe = PhaseExecution(
            phase_id=PhaseId.GLOSSARY_RECONCILIATION, status=PhaseStatus.RUNNING
        )
        state.upsert_phase_execution(run.id, pe, source_id=None)
        assert (
            state.get_phase_status(
                run.id, PhaseId.GLOSSARY_RECONCILIATION, source_id=None
            )
            is PhaseStatus.RUNNING
        )


def test_phase_execution_upsert_updates_status(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    with SqliteState(tmp_path / "t.db") as state:
        project = _make_project(make_generation_settings)
        state.upsert_project(project)
        run = _make_run(project)
        state.upsert_run(run)
        vid = SourceId.new()
        pe1 = PhaseExecution(phase_id=PhaseId.STT, status=PhaseStatus.RUNNING)
        state.upsert_phase_execution(run.id, pe1, source_id=vid)
        pe2 = PhaseExecution(phase_id=PhaseId.STT, status=PhaseStatus.SUCCEEDED)
        state.upsert_phase_execution(run.id, pe2, source_id=vid)
        assert (
            state.get_phase_status(run.id, PhaseId.STT, source_id=vid)
            is PhaseStatus.SUCCEEDED
        )


def test_phase_execution_batch_upsert_replaces_previous_row(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    """Reg : SQLite traite NULL comme distinct -> upsert batch doit gerer NULL."""
    with SqliteState(tmp_path / "t.db") as state:
        project = _make_project(make_generation_settings)
        state.upsert_project(project)
        run = _make_run(project)
        state.upsert_run(run)
        pe1 = PhaseExecution(
            phase_id=PhaseId.CONSOLIDATION, status=PhaseStatus.RUNNING
        )
        pe2 = PhaseExecution(
            phase_id=PhaseId.CONSOLIDATION, status=PhaseStatus.SUCCEEDED
        )
        state.upsert_phase_execution(run.id, pe1, source_id=None)
        state.upsert_phase_execution(run.id, pe2, source_id=None)
        executions = [
            e for e in state.list_phase_executions(run.id)
            if e.phase_id is PhaseId.CONSOLIDATION
        ]
        assert len(executions) == 1
        assert executions[0].status is PhaseStatus.SUCCEEDED


def test_phase_execution_with_error_round_trip(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    with SqliteState(tmp_path / "t.db") as state:
        project = _make_project(make_generation_settings)
        state.upsert_project(project)
        run = _make_run(project)
        state.upsert_run(run)
        err = ErrorInfo(
            code="LLM.RATE_LIMIT",
            user_message="oups",
            severity=Severity.WARNING,
            technical_details={"status": 429},
            traceback="trace",
        )
        pe = PhaseExecution(
            phase_id=PhaseId.STT,
            status=PhaseStatus.FAILED,
            error=err,
        )
        vid = SourceId.new()
        state.upsert_phase_execution(run.id, pe, source_id=vid)
        executions = state.list_phase_executions(run.id)
        assert len(executions) == 1
        loaded = executions[0]
        assert loaded.error is not None
        assert loaded.error.code == "LLM.RATE_LIMIT"


def test_get_phase_status_missing_returns_none(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    with SqliteState(tmp_path / "t.db") as state:
        project = _make_project(make_generation_settings)
        state.upsert_project(project)
        run = _make_run(project)
        state.upsert_run(run)
        assert state.get_phase_status(run.id, PhaseId.STT, source_id=None) is None


def test_list_phase_cells_returns_status_and_cost(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    with SqliteState(tmp_path / "t.db") as state:
        project = _make_project(make_generation_settings)
        state.upsert_project(project)
        run = _make_run(project)
        state.upsert_run(run)
        vid = SourceId.new()
        state.upsert_phase_execution(
            run.id,
            PhaseExecution(
                phase_id=PhaseId.STT, status=PhaseStatus.SUCCEEDED, cost_usd=0.07
            ),
            source_id=vid,
        )
        state.upsert_phase_execution(
            run.id,
            PhaseExecution(
                phase_id=PhaseId.GLOSSARY_RECONCILIATION,
                status=PhaseStatus.SUCCEEDED,
                cost_usd=0.20,
            ),
            source_id=None,
        )
        cells = state.list_phase_cells(run.id)
        by_key = {(c.phase_id, c.source_id): c for c in cells}
        assert by_key[(PhaseId.STT, vid)].cost_usd == 0.07
        assert by_key[(PhaseId.STT, vid)].status is PhaseStatus.SUCCEEDED
        assert by_key[(PhaseId.GLOSSARY_RECONCILIATION, None)].cost_usd == 0.20


def test_delete_runs_for_project_keeps_project(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    with SqliteState(tmp_path / "t.db") as state:
        project = _make_project(make_generation_settings)
        state.upsert_project(project)
        run = _make_run(project)
        state.upsert_run(run)
        state.upsert_phase_execution(
            run.id,
            PhaseExecution(
                phase_id=PhaseId.STT, status=PhaseStatus.SUCCEEDED, cost_usd=0.07
            ),
            source_id=SourceId.new(),
        )

        state.delete_runs_for_project(project.id)

        # Le projet est conservé, mais ses runs (et phases en cascade) effacés.
        assert state.get_project(project.id) is not None
        assert state.list_runs_for_project(project.id) == []
        assert state.get_run(run.id) is None
        assert state.list_phase_cells(run.id) == []


# --- Test de concurrence ------------------------------------------------------


def test_concurrent_phase_execution_writes(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    n_threads = 4
    writes_per_thread = 100
    db_path = tmp_path / "t.db"

    with SqliteState(db_path) as state:
        project = _make_project(make_generation_settings)
        state.upsert_project(project)
        run = _make_run(project)
        state.upsert_run(run)
        run_id = run.id

    errors: list[BaseException] = []

    def _worker(worker_id: int) -> None:
        try:
            with SqliteState(db_path) as state:
                for i in range(writes_per_thread):
                    pe = PhaseExecution(
                        phase_id=PhaseId.REFORMULATION,
                        status=PhaseStatus.SUCCEEDED,
                        retry_count=worker_id * writes_per_thread + i,
                    )
                    vid = SourceId.new()
                    state.upsert_phase_execution(run_id, pe, source_id=vid)
        except BaseException as exc:  # noqa: BLE001
            errors.append(exc)

    threads = [threading.Thread(target=_worker, args=(i,)) for i in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == [], f"Unexpected errors: {errors}"

    with SqliteState(db_path) as state:
        all_pe = state.list_phase_executions(run_id)
    assert len(all_pe) == n_threads * writes_per_thread


# --- Tests migration v1 -> v2 -------------------------------------------------


def _legacy_v1_blob() -> str:
    """Blob v1 « à plat » (ancien ProjectSettings, avec name + workspace_folder)."""
    return json.dumps(
        {
            "name": "Ancien projet",
            "input_folder": "D:/Cours",
            "workspace_folder": "D:/Cours/.fahmi2",
            "source_language": "fr",
            "output_languages": ["fr"],
            "style_preset": "standard",
            "style_directives": "",
            "stt_provider": "openai_cloud",
            "llm_model": "deepseek-v4-flash",
            "phases_config": {
                p: {
                    "thinking_enabled": False,
                    "reasoning_effort": None,
                    "temperature": 1.0,
                    "max_retries": 3,
                }
                for p in (
                    "phase_1_term_extraction",
                    "phase_2_glossary_reconciliation",
                    "phase_3_reformulation",
                    "phase_4_structuration",
                    "phase_5_consolidation",
                    "phase_6_translation",
                    "phase_7_coherence",
                )
            },
            "cost_ceiling_usd": None,
            "parallelism": {"stt_cloud_workers": 3, "llm_workers": 4},
            "delete_audio_after_stt": True,
        },
        ensure_ascii=False,
    )


def test_loads_legacy_v1_project_blob(tmp_path: Path) -> None:
    """Un blob v1 « à plat » se charge en Project v2 (migration à la lecture)."""
    with SqliteState(tmp_path / "legacy.db") as state:
        pid = ProjectId.new()
        state._get_connection().execute(  # noqa: SLF001 — test d'accès direct
            "INSERT INTO projects (id, name, created_at, settings_json, last_run_at) "
            "VALUES (?, ?, ?, ?, NULL)",
            (pid.value, "Ancien projet", _ts().isoformat(), _legacy_v1_blob()),
        )
        state._get_connection().commit()  # noqa: SLF001

        project = state.get_project(pid)
        assert project is not None
        assert project.name == "Ancien projet"
        assert project.workspace_folder.as_posix() == "D:/Cours/.fahmi2"
        assert project.generation is not None
        assert project.generation.input_folder.as_posix() == "D:/Cours"


def test_corrupt_project_blob_raises_storage_error(tmp_path: Path) -> None:
    with SqliteState(tmp_path / "corrupt.db") as state:
        pid = ProjectId.new()
        state._get_connection().execute(  # noqa: SLF001
            "INSERT INTO projects (id, name, created_at, settings_json) "
            "VALUES (?, ?, ?, ?)",
            (pid.value, "x", _ts().isoformat(), "{not json"),
        )
        state._get_connection().commit()  # noqa: SLF001
        with pytest.raises(StorageError, match="STORAGE.PROJECT_BLOB_INVALID"):
            state.get_project(pid)


def test_pedagogy_settings_round_trip(
    tmp_path: Path, make_generation_settings: Any, make_pedagogy_settings: Any
) -> None:
    ped = make_pedagogy_settings()
    with SqliteState(tmp_path / "t.db") as state:
        project = Project(
            id=ProjectId.new(),
            name="P",
            workspace_folder=Path("./ws"),
            created_at=_ts(),
            generation=make_generation_settings(),
            pedagogy=ped,
        )
        state.upsert_project(project)
        loaded = state.get_project(project.id)
        assert loaded is not None
        assert loaded.pedagogy is not None
        assert loaded.pedagogy.selected_supports == ped.selected_supports
        assert loaded.pedagogy.export_formats == ped.export_formats


def test_legacy_v1_blob_has_no_pedagogy(tmp_path: Path) -> None:
    with SqliteState(tmp_path / "legacy.db") as state:
        pid = ProjectId.new()
        state._get_connection().execute(  # noqa: SLF001
            "INSERT INTO projects (id, name, created_at, settings_json) "
            "VALUES (?, ?, ?, ?)",
            (pid.value, "Ancien", _ts().isoformat(), _legacy_v1_blob()),
        )
        state._get_connection().commit()  # noqa: SLF001
        project = state.get_project(pid)
        assert project is not None
        assert project.pedagogy is None


def test_pedagogy_llm_workers_round_trip(make_pedagogy_settings: Any) -> None:
    ped = make_pedagogy_settings(llm_workers=8)
    payload = _serialize_pedagogy_settings(ped)
    assert payload["llm_workers"] == 8
    assert _deserialize_pedagogy_settings(payload).llm_workers == 8


def test_pedagogy_llm_workers_missing_uses_default(
    make_pedagogy_settings: Any,
) -> None:
    payload = _serialize_pedagogy_settings(make_pedagogy_settings())
    del payload["llm_workers"]  # simule un blob écrit avant l'ajout du champ
    restored = _deserialize_pedagogy_settings(payload)
    assert restored.llm_workers == DEFAULT_PEDAGOGY_LLM_WORKERS
