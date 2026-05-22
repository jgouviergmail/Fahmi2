# Lot 1A — Fondation « source » polymorphe + migration SQLite (plan d'implémentation)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Poser le socle d'une *source d'entrée polymorphe* (`SourceKind`, `InputSource`, `SourceExecution`) en renommant `VideoExecution→SourceExecution` / `VideoId→SourceId` / `Run.videos→Run.sources` à travers tout le code, et migrer le schéma SQLite (`videos→sources`, `phase_executions.video_id→source_id`) de façon idempotente — **sans changer le comportement utilisateur**.

**Architecture:** Refactor de fondation pur. On introduit le value object `InputSource(kind, location)` qui remplace le `source_path: Path` nu (incapable de porter une URL). `SourceExecution` remplace `VideoExecution`. Le pipeline aval, le moteur et l'UI sont propagés mécaniquement. La persistance SQLite migre via une fonction de renommage de table/colonne (SQLite ≥ 3.25) appelée **avant** le chargement du DDL, idempotente. À la fin du lot, la suite de tests existante passe et l'app se comporte exactement comme avant (toutes les sources sont `SourceKind.VIDEO`).

**Tech Stack:** Python 3.12, dataclasses frozen, `sqlite3` (stdlib), pytest, ruff, mypy --strict. Interpréteur : `.venv\Scripts\python.exe`.

**Spec de référence:** `docs/superpowers/specs/2026-05-22-entrants-generation-elargis-design.md` (§3, §13).

**Note d'exécution:** plusieurs tâches forment un renommage transverse interdépendant : le « vert » global n'est atteint qu'à la fin de la Tâche 8. Les Tâches 1-2 (additives) sont committées isolément ; les Tâches 3-9 forment **un** commit de refactor (état rouge transitoire accepté entre elles).

---

## Mapping de renommage (référence pour toutes les tâches de propagation)

| Avant | Après |
|---|---|
| `domain/video.py` | `domain/source.py` (fichier déplacé) |
| `VideoExecution` | `SourceExecution` |
| `VideoId` | `SourceId` |
| `Run.videos` (attribut + kwarg) | `Run.sources` |
| `video.video_id` | `source.source_id` |
| `video.source_path` (lecture chemin) | `source.source.as_path` |
| param de handler `video: VideoExecution \| None` | `source: SourceExecution \| None` |
| kwarg moteur/state `video_id=` | `source_id=` |
| `PhaseCell.video_id` | `PhaseCell.source_id` |
| events `video_id=` (PhaseStarted/PhaseFinished/RetryAttempt + log event) | `source_id=` |
| SQL table `videos` | `sources` |
| SQL colonne `phase_executions.video_id` | `source_id` |
| `scan_input_folder` → `list[VideoExecution]` | `list[SourceExecution]` |

Critère de complétude du renommage : `rg "\bVideoExecution\b|\bVideoId\b|\.videos\b|\bvideo_id\b" src tests` ne renvoie plus aucune occurrence (hors chaînes SQL legacy de la fonction de migration et libellés UI volontaires).

---

## Tâche 1 : Enum `SourceKind`

**Files:**
- Modify: `src/fahmi2/domain/enums.py`
- Test: `tests/unit/domain/test_enums.py` (créer si absent)

- [ ] **Step 1: Écrire le test qui échoue**

```python
# tests/unit/domain/test_enums.py
from fahmi2.domain.enums import SourceKind


def test_source_kind_values():
    assert SourceKind.VIDEO.value == "video"
    assert SourceKind.AUDIO.value == "audio"
    assert SourceKind.DOCUMENT.value == "document"
    assert SourceKind.YOUTUBE.value == "youtube"
    assert {k.value for k in SourceKind} == {"video", "audio", "document", "youtube"}
```

- [ ] **Step 2: Lancer le test (échec attendu)**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/domain/test_enums.py -v`
Expected: FAIL — `ImportError: cannot import name 'SourceKind'`

- [ ] **Step 3: Ajouter l'enum**

Dans `src/fahmi2/domain/enums.py`, après la classe `PhaseId` (ou groupé avec les enums de génération) :

```python
class SourceKind(StrEnum):
    """Origine d'une source d'entrée de la génération."""

    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"
    YOUTUBE = "youtube"
```

- [ ] **Step 4: Lancer le test (succès attendu)**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/domain/test_enums.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/fahmi2/domain/enums.py tests/unit/domain/test_enums.py
git commit -m "feat(domain): ajoute l'enum SourceKind"
```

---

## Tâche 2 : Value object `InputSource`

**Files:**
- Create: `src/fahmi2/domain/source.py`
- Test: `tests/unit/domain/test_source.py`

- [ ] **Step 1: Écrire les tests qui échouent**

```python
# tests/unit/domain/test_source.py
from pathlib import Path

import pytest

from fahmi2.domain.enums import SourceKind
from fahmi2.domain.source import InputSource


def test_local_file_source():
    src = InputSource(kind=SourceKind.VIDEO, location="D:/cours/01-intro.mp4")
    assert src.is_remote is False
    assert src.as_path == Path("D:/cours/01-intro.mp4")
    assert src.order_key() == "01-intro.mp4"
    assert src.display_name() == "01-intro.mp4"


def test_youtube_source_is_remote():
    src = InputSource(kind=SourceKind.YOUTUBE, location="https://youtu.be/abc123")
    assert src.is_remote is True
    assert src.order_key() == "https://youtu.be/abc123"
    with pytest.raises(ValueError, match="distante"):
        _ = src.as_path
```

- [ ] **Step 2: Lancer (échec attendu)**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/domain/test_source.py -v`
Expected: FAIL — `ModuleNotFoundError: fahmi2.domain.source`

- [ ] **Step 3: Créer `domain/source.py` (value object seul pour l'instant)**

```python
"""Source d'entrée de la génération : ``InputSource`` (fichier ou URL) et
``SourceExecution`` (état d'exécution d'une source dans un Run)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from fahmi2.domain.enums import Language, PhaseId, PhaseStatus, SourceKind
from fahmi2.domain.ids import SourceId
from fahmi2.domain.phase import PhaseExecution


@dataclass(frozen=True)
class InputSource:
    """Une source d'entrée de la génération (fichier local ou URL distante).

    Attributes:
        kind: Type de source (vidéo, audio, document, YouTube).
        location: Chemin de fichier (POSIX/Windows) **ou** URL, selon ``kind``.
    """

    kind: SourceKind
    location: str

    @property
    def is_remote(self) -> bool:
        """``True`` pour une source distante (YouTube), ``False`` pour un fichier."""
        return self.kind is SourceKind.YOUTUBE

    @property
    def as_path(self) -> Path:
        """Chemin local de la source.

        Returns:
            Le ``Path`` de la source fichier.

        Raises:
            ValueError: Si la source est distante (pas de chemin local).
        """
        if self.is_remote:
            raise ValueError("Une source distante (YouTube) n'a pas de chemin local")
        return Path(self.location)

    def order_key(self) -> str:
        """Clé stable d'ordonnancement : nom de fichier (local) ou URL (distant)."""
        return self.location if self.is_remote else Path(self.location).name

    def display_name(self) -> str:
        """Libellé court pour l'UI et les logs."""
        return self.order_key()
```

> Note : `SourceId` (importé ci-dessus) est créé en Tâche 3 ; `SourceExecution`
> est ajouté en Tâche 3. Ce fichier ne compile complètement qu'après la Tâche 3.
> Pour faire passer le test isolé de cette tâche, **commenter temporairement**
> les imports `SourceId`/`PhaseExecution`/`field` et la future classe — ou
> enchaîner directement la Tâche 3 avant de lancer la suite. Recommandé :
> exécuter Tâches 2 et 3 d'affilée, tester à la fin de la Tâche 3.

- [ ] **Step 4: Lancer le test ciblé**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/domain/test_source.py -v`
Expected: PASS (après Tâche 3 si import `SourceId` requis)

- [ ] **Step 5: (commit groupé avec Tâche 3)**

---

## Tâche 3 : `SourceId` + `SourceExecution` + `Run.sources` (domain)

**Files:**
- Modify: `src/fahmi2/domain/ids.py`
- Modify: `src/fahmi2/domain/source.py` (ajout `SourceExecution`)
- Delete: `src/fahmi2/domain/video.py`
- Modify: `src/fahmi2/domain/run.py`
- Test: `tests/unit/domain/test_source.py` (ajout), supprimer `tests/unit/domain/test_video.py` s'il existe

- [ ] **Step 1: Renommer `VideoId` → `SourceId` dans `ids.py`**

Dans `src/fahmi2/domain/ids.py`, remplacer la classe `VideoId` par :

```python
@dataclass(frozen=True)
class SourceId(_UlidIdBase):
    """Identifiant stable d'une source d'entrée dans un Run."""
```

Et mettre à jour la docstring de module (ligne ~5) : `« ProjectId, RunId, SourceId »`.

- [ ] **Step 2: Ajouter `SourceExecution` à `domain/source.py`**

À la suite de `InputSource` :

```python
@dataclass(frozen=True)
class SourceExecution:
    """État d'exécution d'une source d'entrée dans un Run.

    Attributes:
        source_id: Identifiant stable de la source dans le projet.
        source: La source d'entrée (fichier ou URL).
        detected_language: Langue détectée (``None`` tant que l'ingestion STT
            n'a pas tourné ; pour un document, posée à la langue source).
        phase_executions: Mapping ``PhaseId → PhaseExecution`` pour les phases
            par-source (0, 1, 3, 4, 6, 7). Les phases batch (2, 5) sont au Run.
    """

    source_id: SourceId
    source: InputSource
    detected_language: Language | None = None
    phase_executions: dict[PhaseId, PhaseExecution] = field(default_factory=dict)

    def phase_status(self, phase_id: PhaseId) -> PhaseStatus:
        """Retourne le statut de la phase pour cette source.

        Args:
            phase_id: Phase à inspecter.

        Returns:
            Le statut, ou ``PhaseStatus.PENDING`` si la phase n'a pas commencé.
        """
        pe = self.phase_executions.get(phase_id)
        return pe.status if pe is not None else PhaseStatus.PENDING
```

- [ ] **Step 3: Ajouter le test `phase_status`**

```python
# tests/unit/domain/test_source.py — ajouter
from fahmi2.domain.enums import PhaseId, PhaseStatus
from fahmi2.domain.ids import SourceId
from fahmi2.domain.source import SourceExecution


def test_source_execution_phase_status_default_pending():
    se = SourceExecution(
        source_id=SourceId.new(),
        source=InputSource(kind=SourceKind.VIDEO, location="a.mp4"),
    )
    assert se.phase_status(PhaseId.STT) is PhaseStatus.PENDING
```

- [ ] **Step 4: Supprimer `domain/video.py`**

```bash
git rm src/fahmi2/domain/video.py
```

(Supprimer aussi `tests/unit/domain/test_video.py` s'il existe : `git rm tests/unit/domain/test_video.py`.)

- [ ] **Step 5: Renommer `Run.videos` → `Run.sources` dans `run.py`**

Dans `src/fahmi2/domain/run.py` :
- import : `from fahmi2.domain.source import SourceExecution` (au lieu de `domain.video import VideoExecution`) ;
- attribut : `sources: tuple[SourceExecution, ...] = ()` (au lieu de `videos`) ;
- mettre à jour la docstring (`videos` → `sources`).

- [ ] **Step 6: Lancer les tests domain**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/domain -v`
Expected: PASS pour `test_source.py` et `test_enums.py` ; le reste de la suite est encore rouge (propagation à venir) — c'est attendu.

---

## Tâche 4 : Migration SQLite (schéma + renommage table/colonne + mapping)

**Files:**
- Modify: `src/fahmi2/infra/storage/_schema.sql`
- Modify: `src/fahmi2/infra/storage/sqlite_state.py`
- Test: `tests/unit/infra/storage/test_sqlite_state.py` (existant) + `tests/unit/infra/storage/test_migration_sources.py` (créer)

- [ ] **Step 1: Mettre à jour `_schema.sql`**

Remplacer le bloc `CREATE TABLE ... videos ...` par :

```sql
CREATE TABLE IF NOT EXISTS sources (
  id                TEXT PRIMARY KEY,
  run_id            TEXT NOT NULL,
  source_kind       TEXT NOT NULL DEFAULT 'video',
  source_location   TEXT NOT NULL,
  detected_language TEXT,
  FOREIGN KEY (run_id) REFERENCES runs (id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_sources_run_id ON sources (run_id);
```

Dans `phase_executions`, renommer la colonne `video_id` → `source_id`, la contrainte `UNIQUE (run_id, phase_id, video_id)` → `UNIQUE (run_id, phase_id, source_id)`, et l'index `idx_phase_executions_lookup` → `ON phase_executions (run_id, phase_id, source_id)`.

- [ ] **Step 2: Écrire le test de migration (base legacy → migrée)**

```python
# tests/unit/infra/storage/test_migration_sources.py
import sqlite3
from pathlib import Path

from fahmi2.infra.storage.sqlite_state import SqliteState


def _make_legacy_db(path: Path) -> None:
    """Crée une base à l'ancien schéma (tables videos / phase_executions.video_id)."""
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
        INSERT INTO videos (id, run_id, source_path, detected_language)
            VALUES ('01HՊ', 'r1', 'D:/x/01.mp4', 'fr');
        """
    )
    # ULID valide pour l'id source (26 chars Crockford) :
    conn.execute("DELETE FROM videos")
    conn.execute(
        "INSERT INTO videos (id, run_id, source_path, detected_language) "
        "VALUES ('01HZX9KQ7N8YV3JD4M2C6B5A0E', 'r1', 'D:/x/01.mp4', 'fr')"
    )
    conn.commit()
    conn.close()


def test_migration_renames_videos_to_sources(tmp_path: Path) -> None:
    db = tmp_path / "legacy.db"
    _make_legacy_db(db)

    SqliteState(db)  # ouverture = migration

    conn = sqlite3.connect(db)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "sources" in tables
    assert "videos" not in tables
    cols = {r[1] for r in conn.execute("PRAGMA table_info(sources)")}
    assert {"id", "run_id", "source_kind", "source_location", "detected_language"} <= cols
    pe_cols = {r[1] for r in conn.execute("PRAGMA table_info(phase_executions)")}
    assert "source_id" in pe_cols and "video_id" not in pe_cols
    row = conn.execute("SELECT source_kind, source_location FROM sources").fetchone()
    assert row == ("video", "D:/x/01.mp4")  # legacy → kind 'video', path préservé
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
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "sources" in tables and "videos" not in tables
    conn.close()
```

- [ ] **Step 3: Lancer (échec attendu)**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/infra/storage/test_migration_sources.py -v`
Expected: FAIL — `sources` absente / `videos` toujours présente.

- [ ] **Step 4: Implémenter la migration + le mapping dans `sqlite_state.py`**

(a) Imports : remplacer `from fahmi2.domain.ids import ProjectId, RunId, VideoId` par `... import ProjectId, RunId, SourceId` ; remplacer `from fahmi2.domain.video import VideoExecution` par `from fahmi2.domain.source import InputSource, SourceExecution` ; ajouter `SourceKind` à l'import de `domain.enums`.

(b) `PhaseCell` : renommer `video_id: VideoId | None` → `source_id: SourceId | None`.

(c) Ajouter la fonction de migration (appelée **avant** le DDL) :

```python
    @staticmethod
    def _migrate_videos_to_sources(conn: sqlite3.Connection) -> None:
        """Migre l'ancien schéma (table ``videos`` / colonne ``video_id``) vers
        ``sources`` / ``source_id``. Idempotente : ne fait rien si déjà migré.

        Doit être appelée AVANT le chargement du DDL (qui crée ``sources`` en
        ``IF NOT EXISTS``), sinon le renommage entrerait en conflit.
        """
        tables = {
            r[0]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        if "videos" in tables and "sources" not in tables:
            conn.execute("ALTER TABLE videos RENAME TO sources")
            conn.execute(
                "ALTER TABLE sources RENAME COLUMN source_path TO source_location"
            )
            conn.execute(
                "ALTER TABLE sources ADD COLUMN source_kind TEXT NOT NULL "
                "DEFAULT 'video'"
            )
        pe_cols = {
            r[1] for r in conn.execute("PRAGMA table_info(phase_executions)")
        }
        if "video_id" in pe_cols and "source_id" not in pe_cols:
            conn.execute(
                "ALTER TABLE phase_executions RENAME COLUMN video_id TO source_id"
            )
        conn.commit()
```

(d) Dans `_init_database`, insérer l'appel **avant** `executescript` :

```python
    def _init_database(self) -> None:
        conn = self._get_connection()
        self._migrate_videos_to_sources(conn)
        ddl = self._load_schema_ddl()
        conn.executescript(ddl)
        self._apply_soft_migrations(conn)
        ...
```

(e) `upsert_run` : remplacer la boucle `for video in run.videos` par :

```python
        for src in run.sources:
            conn.execute(
                """
                INSERT INTO sources (
                    id, run_id, source_kind, source_location, detected_language
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    source_kind       = excluded.source_kind,
                    source_location   = excluded.source_location,
                    detected_language = excluded.detected_language
                """,
                (
                    src.source_id.value,
                    run.id.value,
                    str(src.source.kind),
                    src.source.location,
                    str(src.detected_language) if src.detected_language else None,
                ),
            )
```

(f) `_hydrate_run` + `_row_to_video_execution` → `_row_to_source_execution` :

```python
    def _hydrate_run(self, run: Run) -> Run:
        rows = self._get_connection().execute(
            "SELECT id, source_kind, source_location, detected_language "
            "FROM sources WHERE run_id = ? ORDER BY rowid",
            (run.id.value,),
        ).fetchall()
        sources = tuple(self._row_to_source_execution(row) for row in rows)
        if not sources:
            return run
        return replace(run, sources=sources)

    @staticmethod
    def _row_to_source_execution(row: tuple[Any, ...]) -> SourceExecution:
        source_id_str, kind_str, location_str, detected_language_str = row
        detected_language = (
            Language(detected_language_str) if detected_language_str else None
        )
        return SourceExecution(
            source_id=SourceId(value=source_id_str),
            source=InputSource(kind=SourceKind(kind_str), location=location_str),
            detected_language=detected_language,
        )
```

(g) `upsert_phase_execution`, `get_phase_status`, `list_phase_cells` : remplacer le paramètre/kwarg `video_id` par `source_id` et la colonne SQL `video_id` par `source_id` (3 requêtes : DELETE batch, INSERT ... `source_id`, `ON CONFLICT(run_id, phase_id, source_id)`, `WHERE ... source_id IS ?`). Dans `list_phase_cells`, construire `PhaseCell(source_id=SourceId(value=row[1]) if row[1] else None, ...)`.

- [ ] **Step 5: Lancer les tests de migration + stockage**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/infra/storage -v`
Expected: `test_migration_sources.py` PASS ; `test_sqlite_state.py` peut nécessiter une adaptation (kwarg `video_id=`→`source_id=`, `Run(videos=…)`→`Run(sources=…)`) — la traiter en Tâche 7.

---

## Tâche 5 : Propagation du renommage — `pipeline/`

**Files (Modify):**
- `src/fahmi2/pipeline/events.py`
- `src/fahmi2/pipeline/phase_handler.py`
- `src/fahmi2/pipeline/engine.py`
- `src/fahmi2/pipeline/handlers/phase_0_stt.py` … `phase_7_coherence.py`

- [ ] **Step 1: `events.py`** — renommer le champ `video_id` → `source_id` (type `SourceId | None`) dans `PhaseStarted`, `PhaseFinished`, `RetryAttempt` ; mettre à jour les imports (`SourceId`).

- [ ] **Step 2: `phase_handler.py`** — dans `PhaseContext` et la signature abstraite `execute(self, ctx, *, source: SourceExecution | None)`, renommer le paramètre `video`→`source` et l'import `VideoExecution`→`SourceExecution`. (Le champ `PhaseContext.ingestion` est ajouté au **Lot 1B**, pas ici.)

- [ ] **Step 3: `engine.py`** — appliquer le mapping : `ctx.run.videos`→`ctx.run.sources`, paramètre `video`→`source`, `video.video_id`→`source.source_id`, kwargs `video_id=`→`source_id=`, import `SourceExecution`. La lambda devient `lambda source: self._execute_one(handler, ctx, source=source)`.

- [ ] **Step 4: handlers `phase_0`..`phase_7`** — pour chacun :
  - signature `*, video: VideoExecution | None` → `*, source: SourceExecution | None` ;
  - garde `if video is None` → `if source is None` (et messages d'erreur `requires a SourceExecution`) ;
  - `video.video_id.value` → `source.source_id.value` ;
  - dans `phase_0_stt.py` : `ctx.ffmpeg.extract(video.source_path, …)` → `ctx.ffmpeg.extract(source.source.as_path, …)` ;
  - dans `phase_5_consolidation.py` : `_load_all_structured(ctx.workspace, ctx.run.videos)` → `... ctx.run.sources` ; renommer la variable interne `videos`→`sources`, `video_id`→`source_id`, `_row_to_video_execution` n'existe pas ici (OK), garder les clés de dict mais renommer sémantiquement (`structured_by_video`→`structured_by_source` est optionnel — au minimum compiler).
  - dans `phase_2`/`phase_6`/`phase_7` : `ctx.run.videos`→`ctx.run.sources`, `v.video_id`→`s.source_id`.

- [ ] **Step 5: Vérifier la compilation du package pipeline**

Run: `.venv\Scripts\python.exe -m mypy src/fahmi2/pipeline`
Expected: aucune erreur liée à `Video*` (les erreurs résiduelles d'autres couches sont traitées en Tâches 6-7).

---

## Tâche 6 : Propagation du renommage — `app/` & `ui/`

**Files (Modify):**
- `src/fahmi2/app/run_orchestrator.py`
- `src/fahmi2/app/video_scanner.py`
- `src/fahmi2/ui/generation_controller.py`
- `src/fahmi2/ui/viewmodels/run_matrix.py`
- `src/fahmi2/ui/viewmodels/stats_strip.py`
- `src/fahmi2/ui/widgets/stats_strip.py`
- `src/fahmi2/core/logging/event.py` (si champ `video_id`)
- `src/fahmi2/domain/glossary.py` (vérifier les 3 occurrences `video` — adapter si ce sont des références d'exécution, ignorer si ce sont des libellés de contenu)

- [ ] **Step 1: `video_scanner.py`** — adaptation **minimale** (l'élargissement extensions = Lot 1B). `scan_input_folder` retourne désormais `list[SourceExecution]` :

```python
from fahmi2.domain.enums import SourceKind
from fahmi2.domain.ids import SourceId
from fahmi2.domain.source import InputSource, SourceExecution

# ... dans le return final :
return [
    SourceExecution(
        source_id=SourceId.new(),
        source=InputSource(kind=SourceKind.VIDEO, location=str(p)),
    )
    for p in candidates
]
```

- [ ] **Step 2: `run_orchestrator.py`** — `videos = scan_input_folder(...)` reste ; `Run(..., videos=tuple(videos))` → `Run(..., sources=tuple(videos))`. Renommer la variable locale `videos`→`sources` pour la clarté.

- [ ] **Step 3: `generation_controller.py`** — mapping : `Run(... videos=)`→`sources=` si présent ; `v.source_path`→`v.source.as_path` (ligne ~698, estimation : `ffmpeg.probe_duration_seconds(v.source.as_path) for v in sources`) ; `scan_input_folder` variable `videos`→`sources` ; events `video_id`→`source_id` partout où consommés (`_to_log_event`, refresh matrice).

- [ ] **Step 4: viewmodels `run_matrix.py` / `stats_strip.py` + widget** — appliquer le mapping `video`/`video_id`/`videos`→`source`/`source_id`/`sources`. Conserver les **libellés UI** (textes affichés) tels quels pour l'instant (le libellé « Transcription / Ingestion » est posé au Lot 1B).

- [ ] **Step 5: `core/logging/event.py`** — si un champ `video_id` existe dans un événement de log, le renommer `source_id`.

- [ ] **Step 6: Vérifier**

Run: `.venv\Scripts\python.exe -m mypy src`
Expected: aucune erreur résiduelle `Video*`.

---

## Tâche 7 : Adapter les tests existants & fixtures

**Files (Modify):** tous les tests référant `Video*` (cf. grep) : `tests/unit/pipeline/test_engine.py`, `tests/unit/pipeline/handlers/*`, `tests/unit/pipeline/handlers/_helpers.py`, `tests/unit/app/test_run_orchestrator.py`, `tests/unit/app/test_video_scanner.py`, `tests/unit/infra/storage/test_sqlite_state.py`, `tests/e2e/test_full_pipeline.py`, et tout autre remonté par grep.

- [ ] **Step 1: Repérer les tests à adapter**

Run: `rg -l "VideoExecution|VideoId|\.videos\b|video_id|source_path" tests`

- [ ] **Step 2: Appliquer le mapping de renommage** dans chaque test : `VideoExecution(video_id=…, source_path=Path(...))` → `SourceExecution(source_id=…, source=InputSource(kind=SourceKind.VIDEO, location=...))` ; `Run(videos=…)`→`Run(sources=…)` ; helpers `video_id=`→`source_id=` ; assertions sur events `video_id`→`source_id`.

- [ ] **Step 3: Helper `_helpers.py`** — adapter le builder de `PhaseContext`/sources de test au nouveau modèle (paramètre `source` au lieu de `video`).

- [ ] **Step 4: Lancer toute la suite**

Run: `.venv\Scripts\python.exe -m pytest`
Expected: PASS (vert global retrouvé).

---

## Tâche 8 : Repasse qualité finale & commit du refactor

- [ ] **Step 1: Vérifier l'absence d'occurrences résiduelles**

Run: `rg "\bVideoExecution\b|\bVideoId\b|\.videos\b|\bvideo_id\b" src tests`
Expected: aucune occurrence (hors libellés UI volontaires et chaînes SQL de `_migrate_videos_to_sources`).

- [ ] **Step 2: Suite + lint + types**

Run:
```
.venv\Scripts\python.exe -m pytest
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy src tests
```
Expected: tout vert.

- [ ] **Step 3: Commit du refactor (Tâches 2-7)**

```bash
git add -A
git commit -m "refactor(domain): SourceExecution/SourceId/InputSource + migration SQLite videos->sources"
```

---

## Self-review (à exécuter par le rédacteur après écriture)

- **Couverture spec §3** : `SourceKind` (T1), `InputSource` (T2), `SourceExecution`/`SourceId`/`Run.sources` (T3) ✓.
- **Couverture spec §13** : migration `videos→sources` + `video_id→source_id`, idempotente, test base legacy + idempotence + base neuve (T4) ✓.
- **Type consistency** : `source_id`/`source`/`sources` cohérents entre domain, sqlite, events, engine, handlers, tests ✓.
- **Pas de nouveau comportement utilisateur** (extensions audio, ingestion, ordonnancement = lots suivants) ✓.

## Dépendances vers les lots suivants
- **Lot 1B** ajoute `PhaseContext.ingestion`, la couche `infra/ingestion/`, la délégation de la phase 0 et `build_input_sources` (extensions audio).
- Les champs `youtube_urls`/`reformulate_documents`/`source_order`/`excluded_sources` de `GenerationSettings` arrivent aux lots 2-4.
