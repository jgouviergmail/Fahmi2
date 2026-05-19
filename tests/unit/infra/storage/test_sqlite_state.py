"""Tests du SqliteState : ouverture, schéma, CRUD, concurrence."""

import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fahmi2.core.errors.error_info import ErrorInfo
from fahmi2.core.errors.severity import Severity
from fahmi2.domain.enums import Language, PhaseId, PhaseStatus, RunStatus
from fahmi2.domain.glossary import Term
from fahmi2.domain.ids import ProjectId, RunId, VideoId
from fahmi2.domain.phase import PhaseExecution
from fahmi2.domain.project import Project
from fahmi2.domain.run import Run
from fahmi2.infra.storage.sqlite_state import SCHEMA_VERSION, SqliteState


def _ts(s: str = "2026-05-19T12:00:00") -> datetime:
    return datetime.fromisoformat(s).replace(tzinfo=UTC)


def _make_project(make_settings: Any) -> Project:
    return Project(
        id=ProjectId.new(),
        settings=make_settings(),
        created_at=_ts(),
    )


def _make_run(project: Project) -> Run:
    return Run(
        id=RunId.new(),
        project_id=project.id,
        started_at=_ts(),
        status=RunStatus.CREATED,
        settings_snapshot=project.settings,
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


def test_upsert_and_get_project(tmp_path: Path, make_settings: Any) -> None:
    with SqliteState(tmp_path / "t.db") as state:
        project = _make_project(make_settings)
        state.upsert_project(project)
        retrieved = state.get_project(project.id)
        assert retrieved is not None
        assert retrieved.id == project.id
        assert retrieved.settings.name == project.settings.name


def test_get_unknown_project_returns_none(tmp_path: Path) -> None:
    with SqliteState(tmp_path / "t.db") as state:
        assert state.get_project(ProjectId.new()) is None


def test_list_projects(tmp_path: Path, make_settings: Any) -> None:
    with SqliteState(tmp_path / "t.db") as state:
        p1 = _make_project(make_settings)
        p2 = _make_project(make_settings)
        state.upsert_project(p1)
        state.upsert_project(p2)
        ids = {p.id for p in state.list_projects()}
        assert ids == {p1.id, p2.id}


def test_delete_project(tmp_path: Path, make_settings: Any) -> None:
    with SqliteState(tmp_path / "t.db") as state:
        p = _make_project(make_settings)
        state.upsert_project(p)
        state.delete_project(p.id)
        assert state.get_project(p.id) is None


def test_upsert_project_is_idempotent(tmp_path: Path, make_settings: Any) -> None:
    with SqliteState(tmp_path / "t.db") as state:
        p = _make_project(make_settings)
        state.upsert_project(p)
        state.upsert_project(p)
        assert len(state.list_projects()) == 1


# --- Tests CRUD runs ----------------------------------------------------------


def test_upsert_and_get_run(tmp_path: Path, make_settings: Any) -> None:
    with SqliteState(tmp_path / "t.db") as state:
        project = _make_project(make_settings)
        state.upsert_project(project)
        run = _make_run(project)
        state.upsert_run(run)
        retrieved = state.get_run(run.id)
        assert retrieved is not None
        assert retrieved.id == run.id
        assert retrieved.status is RunStatus.CREATED


def test_list_runs_for_project(tmp_path: Path, make_settings: Any) -> None:
    with SqliteState(tmp_path / "t.db") as state:
        project = _make_project(make_settings)
        state.upsert_project(project)
        r1 = _make_run(project)
        r2 = _make_run(project)
        state.upsert_run(r1)
        state.upsert_run(r2)
        ids = {r.id for r in state.list_runs_for_project(project.id)}
        assert ids == {r1.id, r2.id}


# --- Tests phase_executions ---------------------------------------------------


def test_upsert_and_get_phase_execution(tmp_path: Path, make_settings: Any) -> None:
    with SqliteState(tmp_path / "t.db") as state:
        project = _make_project(make_settings)
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
        vid = VideoId.new()
        state.upsert_phase_execution(run.id, pe, video_id=vid)

        status = state.get_phase_status(run.id, PhaseId.STT, video_id=vid)
        assert status is PhaseStatus.SUCCEEDED


def test_phase_execution_batch_no_video_id(tmp_path: Path, make_settings: Any) -> None:
    with SqliteState(tmp_path / "t.db") as state:
        project = _make_project(make_settings)
        state.upsert_project(project)
        run = _make_run(project)
        state.upsert_run(run)
        pe = PhaseExecution(
            phase_id=PhaseId.GLOSSARY_RECONCILIATION, status=PhaseStatus.RUNNING
        )
        state.upsert_phase_execution(run.id, pe, video_id=None)
        assert (
            state.get_phase_status(
                run.id, PhaseId.GLOSSARY_RECONCILIATION, video_id=None
            )
            is PhaseStatus.RUNNING
        )


def test_phase_execution_upsert_updates_status(
    tmp_path: Path, make_settings: Any
) -> None:
    with SqliteState(tmp_path / "t.db") as state:
        project = _make_project(make_settings)
        state.upsert_project(project)
        run = _make_run(project)
        state.upsert_run(run)
        vid = VideoId.new()
        pe1 = PhaseExecution(phase_id=PhaseId.STT, status=PhaseStatus.RUNNING)
        state.upsert_phase_execution(run.id, pe1, video_id=vid)
        pe2 = PhaseExecution(phase_id=PhaseId.STT, status=PhaseStatus.SUCCEEDED)
        state.upsert_phase_execution(run.id, pe2, video_id=vid)
        assert (
            state.get_phase_status(run.id, PhaseId.STT, video_id=vid)
            is PhaseStatus.SUCCEEDED
        )


def test_phase_execution_batch_upsert_replaces_previous_row(
    tmp_path: Path, make_settings: Any
) -> None:
    """Reg : SQLite traite NULL comme distinct -> upsert batch doit gerer NULL."""
    with SqliteState(tmp_path / "t.db") as state:
        project = _make_project(make_settings)
        state.upsert_project(project)
        run = _make_run(project)
        state.upsert_run(run)
        pe1 = PhaseExecution(
            phase_id=PhaseId.CONSOLIDATION, status=PhaseStatus.RUNNING
        )
        pe2 = PhaseExecution(
            phase_id=PhaseId.CONSOLIDATION, status=PhaseStatus.SUCCEEDED
        )
        state.upsert_phase_execution(run.id, pe1, video_id=None)
        state.upsert_phase_execution(run.id, pe2, video_id=None)
        executions = [
            e for e in state.list_phase_executions(run.id)
            if e.phase_id is PhaseId.CONSOLIDATION
        ]
        assert len(executions) == 1
        assert executions[0].status is PhaseStatus.SUCCEEDED


def test_phase_execution_with_error_round_trip(
    tmp_path: Path, make_settings: Any
) -> None:
    with SqliteState(tmp_path / "t.db") as state:
        project = _make_project(make_settings)
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
        vid = VideoId.new()
        state.upsert_phase_execution(run.id, pe, video_id=vid)
        executions = state.list_phase_executions(run.id)
        assert len(executions) == 1
        loaded = executions[0]
        assert loaded.error is not None
        assert loaded.error.code == "LLM.RATE_LIMIT"


def test_get_phase_status_missing_returns_none(
    tmp_path: Path, make_settings: Any
) -> None:
    with SqliteState(tmp_path / "t.db") as state:
        project = _make_project(make_settings)
        state.upsert_project(project)
        run = _make_run(project)
        state.upsert_run(run)
        assert state.get_phase_status(run.id, PhaseId.STT, video_id=None) is None


# --- Tests glossary -----------------------------------------------------------


def test_upsert_and_list_glossary_terms(
    tmp_path: Path, make_settings: Any
) -> None:
    with SqliteState(tmp_path / "t.db") as state:
        project = _make_project(make_settings)
        state.upsert_project(project)
        run = _make_run(project)
        state.upsert_run(run)
        vid = VideoId.new()
        term = Term(
            term="PIB",
            definition="produit intérieur brut",
            sources=(vid,),
            aliases=("Produit Intérieur Brut",),
            cross_lang={Language.EN: "GDP"},
        )
        state.upsert_glossary_term(run.id, Language.FR, term)
        terms = state.list_glossary_terms(run.id, Language.FR)
        assert len(terms) == 1
        loaded = terms[0]
        assert loaded.term == "PIB"
        assert loaded.aliases == ("Produit Intérieur Brut",)
        assert loaded.cross_lang == {Language.EN: "GDP"}
        assert loaded.sources == (vid,)


def test_glossary_terms_filtered_by_language(
    tmp_path: Path, make_settings: Any
) -> None:
    with SqliteState(tmp_path / "t.db") as state:
        project = _make_project(make_settings)
        state.upsert_project(project)
        run = _make_run(project)
        state.upsert_run(run)
        state.upsert_glossary_term(run.id, Language.FR, Term(term="A", definition="a"))
        state.upsert_glossary_term(run.id, Language.EN, Term(term="B", definition="b"))
        assert [t.term for t in state.list_glossary_terms(run.id, Language.FR)] == ["A"]
        assert [t.term for t in state.list_glossary_terms(run.id, Language.EN)] == ["B"]


# --- Test de concurrence ------------------------------------------------------


def test_concurrent_phase_execution_writes(
    tmp_path: Path, make_settings: Any
) -> None:
    n_threads = 4
    writes_per_thread = 100
    db_path = tmp_path / "t.db"

    with SqliteState(db_path) as state:
        project = _make_project(make_settings)
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
                    vid = VideoId.new()
                    state.upsert_phase_execution(run_id, pe, video_id=vid)
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
