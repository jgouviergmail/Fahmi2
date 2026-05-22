"""Tests de la migration SQLite ``videos → sources`` / ``video_id → source_id``."""

import sqlite3
from pathlib import Path

from fahmi2.infra.storage.sqlite_state import SqliteState

_ULID = "01HZX9KQ7N8YV3JD4M2C6B5A0E"


def _make_legacy_db(path: Path) -> None:
    """Crée une base à l'ancien schéma (table ``videos`` / colonne ``video_id``)."""
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        INSERT INTO meta (key, value) VALUES ('schema_version', '1');
        CREATE TABLE projects (id TEXT PRIMARY KEY, name TEXT NOT NULL,
            created_at TEXT NOT NULL, settings_json TEXT NOT NULL, last_run_at TEXT);
        CREATE TABLE runs (id TEXT PRIMARY KEY, project_id TEXT NOT NULL,
            status TEXT NOT NULL, started_at TEXT NOT NULL, finished_at TEXT,
            cost_usd REAL NOT NULL DEFAULT 0, settings_snapshot_json TEXT NOT NULL);
        CREATE TABLE videos (id TEXT PRIMARY KEY, run_id TEXT NOT NULL,
            source_path TEXT NOT NULL, detected_language TEXT);
        CREATE TABLE phase_executions (id INTEGER PRIMARY KEY AUTOINCREMENT,
            run_id TEXT NOT NULL, phase_id TEXT NOT NULL, video_id TEXT,
            status TEXT NOT NULL, started_at TEXT, finished_at TEXT,
            artifact_path TEXT, retry_count INTEGER NOT NULL DEFAULT 0,
            cost_usd REAL NOT NULL DEFAULT 0, error_json TEXT,
            UNIQUE (run_id, phase_id, video_id));
        """
    )
    conn.execute(
        "INSERT INTO videos (id, run_id, source_path, detected_language) "
        "VALUES (?, 'r1', 'D:/x/01.mp4', 'fr')",
        (_ULID,),
    )
    conn.commit()
    conn.close()


def test_migration_renames_videos_to_sources(tmp_path: Path) -> None:
    db = tmp_path / "legacy.db"
    _make_legacy_db(db)

    SqliteState(db)  # ouverture déclenche la migration

    conn = sqlite3.connect(db)
    tables = {
        r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert "sources" in tables
    assert "videos" not in tables
    cols = {r[1] for r in conn.execute("PRAGMA table_info(sources)")}
    assert {"id", "run_id", "source_kind", "source_location", "detected_language"} <= cols
    pe_cols = {r[1] for r in conn.execute("PRAGMA table_info(phase_executions)")}
    assert "source_id" in pe_cols
    assert "video_id" not in pe_cols
    row = conn.execute("SELECT source_kind, source_location FROM sources").fetchone()
    assert row == ("video", "D:/x/01.mp4")  # legacy → kind 'video', chemin préservé
    conn.close()


def test_migration_is_idempotent(tmp_path: Path) -> None:
    db = tmp_path / "legacy.db"
    _make_legacy_db(db)
    SqliteState(db)
    SqliteState(db)  # 2e ouverture : ne doit pas lever
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0] == 1
    conn.close()


def test_fresh_db_has_sources_schema(tmp_path: Path) -> None:
    SqliteState(tmp_path / "fresh.db")
    conn = sqlite3.connect(tmp_path / "fresh.db")
    tables = {
        r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert "sources" in tables
    assert "videos" not in tables
    conn.close()
