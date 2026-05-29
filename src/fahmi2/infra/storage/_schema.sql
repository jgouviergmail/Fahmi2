-- Fahmi2 SQLite schema v1
-- Toute modification doit s'accompagner d'une migration dans core/migrations/.

CREATE TABLE IF NOT EXISTS meta (
  key   TEXT PRIMARY KEY,
  value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS projects (
  id            TEXT PRIMARY KEY,
  name          TEXT NOT NULL,
  created_at    TEXT NOT NULL,
  settings_json TEXT NOT NULL,
  last_run_at   TEXT
);

CREATE TABLE IF NOT EXISTS runs (
  id                     TEXT PRIMARY KEY,
  project_id             TEXT NOT NULL,
  status                 TEXT NOT NULL,
  started_at             TEXT NOT NULL,
  finished_at            TEXT,
  cost_usd               REAL NOT NULL DEFAULT 0,
  settings_snapshot_json TEXT NOT NULL,
  FOREIGN KEY (project_id) REFERENCES projects (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_runs_project_id ON runs (project_id);

CREATE TABLE IF NOT EXISTS sources (
  id                TEXT PRIMARY KEY,
  run_id            TEXT NOT NULL,
  source_kind       TEXT NOT NULL DEFAULT 'video',
  source_location   TEXT NOT NULL,
  detected_language TEXT,
  FOREIGN KEY (run_id) REFERENCES runs (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_sources_run_id ON sources (run_id);

CREATE TABLE IF NOT EXISTS phase_executions (
  id                     INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id                 TEXT NOT NULL,
  phase_id               TEXT NOT NULL,
  source_id              TEXT,
  status                 TEXT NOT NULL,
  started_at             TEXT,
  finished_at            TEXT,
  artifact_path          TEXT,
  retry_count            INTEGER NOT NULL DEFAULT 0,
  cost_usd               REAL NOT NULL DEFAULT 0,
  -- Ventilation per-source du coût pour les phases batch qui ont des
  -- opérations attribuables (phase 5 fact-ledger / summary, phase 6
  -- traduction per source × langue). JSON {"source_id": cost, ...} ou NULL.
  per_source_costs_json  TEXT,
  error_json             TEXT,
  UNIQUE (run_id, phase_id, source_id),
  FOREIGN KEY (run_id) REFERENCES runs (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_phase_executions_run ON phase_executions (run_id);
CREATE INDEX IF NOT EXISTS idx_phase_executions_lookup
  ON phase_executions (run_id, phase_id, source_id);
