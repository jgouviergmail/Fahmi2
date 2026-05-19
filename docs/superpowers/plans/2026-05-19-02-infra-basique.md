# Plan 02 — Infra basique : storage + secrets Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans inline (no subagents). Steps use checkbox (`- [ ]`) syntax.

**Goal:** Implémenter les adaptateurs d'infrastructure de base : stockage SQLite (mode WAL, 1 conn/thread), artefacts fichier (writes atomiques), secrets DPAPI (avec fallback in-memory pour tests).

**Architecture:** Trois ports/adapters indépendants dans `infra/`. Chaque adapter expose une interface `Protocol` permettant le mock dans les tests des couches supérieures.

**Tech Stack:** `sqlite3` stdlib, `pywin32` (DPAPI), `pathlib`, `json`, `tempfile`, `threading`.

**Référence spec :** sections 6.3 (FsArtifactStore, DPAPISecretsStore, SqliteState).

---

## File structure

```
src/fahmi2/infra/
├── __init__.py
├── storage/
│   ├── __init__.py
│   ├── fs_artifacts.py      ← Task 1
│   └── sqlite_state.py      ← Tasks 2 + 3 + 4
└── secrets/
    ├── __init__.py
    ├── interface.py         ← Task 5 (SecretsStore Protocol + InMemorySecretsStore)
    └── dpapi_store.py       ← Task 6 (DPAPISecretsStore Windows)

tests/unit/infra/
├── __init__.py
├── storage/
│   ├── __init__.py
│   ├── test_fs_artifacts.py
│   └── test_sqlite_state.py
└── secrets/
    ├── __init__.py
    ├── test_secrets_interface.py
    └── test_dpapi_store.py        (skipped sur non-Windows)
```

---

### Task 1: `fs_artifacts.py` — writes atomiques

**Files:**
- Create: `src/fahmi2/infra/__init__.py`, `src/fahmi2/infra/storage/__init__.py`
- Create: `src/fahmi2/infra/storage/fs_artifacts.py`
- Test: `tests/unit/infra/__init__.py`, `tests/unit/infra/storage/__init__.py`, `tests/unit/infra/storage/test_fs_artifacts.py`

- [ ] **Step 1 : Tests failing**

Tests à écrire :
- `write_text_atomic(path, content)` : écrit dans `.tmp` puis rename
- `write_bytes_atomic(path, content)` : idem pour binaire
- `write_json_atomic(path, data)` : JSON `ensure_ascii=False` + `indent=2`
- crée le dossier parent si nécessaire
- en cas d'erreur d'écriture, le fichier final n'est pas modifié
- thread safety (utilisation concurrente sur fichiers différents)

- [ ] **Step 2 : Impl `FsArtifactStore`** avec ces 3 méthodes. Constantes `_TMP_SUFFIX = ".tmp"`, `_JSON_INDENT = 2`.

- [ ] **Step 3 : Verify + commit** `feat(infra/storage): FsArtifactStore avec writes atomiques`.

---

### Task 2: SecretsStore interface + InMemorySecretsStore

**Files:**
- Create: `src/fahmi2/infra/secrets/__init__.py`, `src/fahmi2/infra/secrets/interface.py`
- Test: `tests/unit/infra/secrets/__init__.py`, `tests/unit/infra/secrets/test_secrets_interface.py`

- [ ] **Step 1 : Tests failing**

Tests pour `InMemorySecretsStore` :
- `set("openai_api_key", "sk-xxx")` puis `get("openai_api_key") == "sk-xxx"`
- `get("missing") is None`
- `delete` supprime
- `keys()` liste les clés présentes
- Protocol `SecretsStore` vérifiable via isinstance

- [ ] **Step 2 : Impl** `SecretsStore` Protocol + `InMemorySecretsStore` (dataclass internal dict).

- [ ] **Step 3 : Verify + commit** `feat(infra/secrets): interface SecretsStore + InMemorySecretsStore`.

---

### Task 3: DPAPISecretsStore (Windows réel)

**Files:**
- Create: `src/fahmi2/infra/secrets/dpapi_store.py`
- Test: `tests/unit/infra/secrets/test_dpapi_store.py`

Sur Windows uniquement (sinon tests skippés via `@pytest.mark.skipif(sys.platform != "win32", ...)`).

- [ ] **Step 1 : Tests failing** (round-trip set/get sur tmp_path, persistance entre 2 instances, delete idempotent)

- [ ] **Step 2 : Impl** `DPAPISecretsStore(secrets_path: Path)` :
  - Format binaire : header magic `FAHMI2SEC\x01` + JSON chiffré DPAPI
  - `win32crypt.CryptProtectData(plaintext, entropy, ...)`
  - Entropie applicative = constante (sel), donc chiffrement lié à l'utilisateur Windows
  - Load au démarrage, save après chaque set/delete
  - Atomic via `FsArtifactStore.write_bytes_atomic` (réutilisation)

- [ ] **Step 3 : Verify + commit** `feat(infra/secrets): DPAPISecretsStore (Windows DPAPI)`.

---

### Task 4: SqliteState (schéma + ouverture WAL)

**Files:**
- Create: `src/fahmi2/infra/storage/sqlite_state.py`
- Create: `src/fahmi2/infra/storage/_schema.sql` (DDL bundlée)
- Test: `tests/unit/infra/storage/test_sqlite_state.py`

- [ ] **Step 1 : Tests failing**

Tests :
- Ouverture crée le fichier et applique le schéma
- WAL activé après ouverture (`PRAGMA journal_mode` retourne `wal`)
- Réouverture sur DB existante ne casse rien
- `schema_version` initialisée à 1 dans la table `meta`

- [ ] **Step 2 : Créer `_schema.sql`** avec tables : `meta`, `projects`, `runs`, `videos`, `phase_executions`, `glossary_terms`. Conforme à la spec.

- [ ] **Step 3 : Impl `SqliteState`** :
  - `__init__(db_path: Path)` — applique PRAGMA WAL + busy_timeout 5000 + foreign_keys ON
  - `_get_connection()` — `threading.local()`, lazy
  - `close()` — ferme la conn du thread courant
  - context manager
  - Méthode `read_schema_version() -> int`
  - Constantes `_WAL_MODE = "wal"`, `_BUSY_TIMEOUT_MS = 5000`, etc.

- [ ] **Step 4 : Verify + commit** `feat(infra/storage): SqliteState avec mode WAL et 1 conn/thread`.

---

### Task 5: SqliteState — opérations CRUD de base

**Files:**
- Modify: `src/fahmi2/infra/storage/sqlite_state.py`
- Test: `tests/unit/infra/storage/test_sqlite_state.py`

- [ ] **Step 1 : Tests failing** (CRUD projects/runs/videos/phase_executions/glossary_terms — round-trips simples)

- [ ] **Step 2 : Impl méthodes** :
  - `upsert_project(project: Project) -> None`
  - `get_project(project_id: ProjectId) -> Project | None`
  - `list_projects() -> list[Project]`
  - `delete_project(project_id) -> None`
  - `upsert_run(run: Run) -> None`
  - `get_run(run_id) -> Run | None`
  - `list_runs_for_project(project_id) -> list[Run]`
  - `upsert_phase_execution(run_id, phase_exec, video_id=None) -> None`
  - `get_phase_status(run_id, phase_id, video_id=None) -> PhaseStatus | None`
  - `list_phase_executions(run_id) -> list[PhaseExecution]`
  - `upsert_glossary_term(run_id, language, term) -> None`
  - `list_glossary_terms(run_id, language) -> list[Term]`
  - Sérialisation : `ProjectSettings`, `ErrorInfo`, `sources` (liste de VideoId) → JSON via méthodes privées `_serialize_*` / `_deserialize_*`

- [ ] **Step 3 : Verify + commit** `feat(infra/storage): operations CRUD SqliteState`.

---

### Task 6: SqliteState — test de concurrence

**Files:**
- Test: `tests/unit/infra/storage/test_sqlite_state.py` (ajout)

- [ ] **Step 1 : Test failing** — 4 threads × 100 upserts phase_executions, vérifier cohérence finale (400 lignes, aucune exception).

- [ ] **Step 2 : Vérifier que l'impl supporte** (sinon ajuster retry/busy_timeout). Si SQLITE_BUSY transitoire, retry interne déjà géré par busy_timeout=5000ms.

- [ ] **Step 3 : Verify + commit** `test(infra/storage): test de concurrence 4 threads SqliteState`.

---

### Task 7: Vérification approfondie Plan 02

- [ ] Suite complète + ruff + mypy --strict + couverture
- [ ] Audit qualité code (DRY, naming, docstrings, constantes, helpers privés)
- [ ] Tag git `milestone-02-infra-basique`
