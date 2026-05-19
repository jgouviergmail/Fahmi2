"""``SqliteState`` — adaptateur de persistance SQLite avec mode WAL.

Caractéristiques clés :

- Mode WAL activé via ``PRAGMA journal_mode = WAL`` pour autoriser les écritures
  concurrentes par plusieurs threads sans bloquer les lectures.
- Une connexion par thread (``threading.local``) : on évite le partage de
  connexion entre threads (source classique de bugs subtils).
- ``busy_timeout`` long pour gérer les rares ``SQLITE_BUSY`` transitoires.
- Foreign keys activées.
- Schéma DDL bundlé dans ``_schema.sql``, chargé via ``importlib.resources``.

Le module expose la constante ``SCHEMA_VERSION`` qui correspond à la version
applicative attendue ; le ``MigrationRunner`` se chargera de migrer les
anciennes versions.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from collections.abc import Iterable
from dataclasses import replace
from datetime import datetime
from importlib.resources import files
from pathlib import Path
from types import TracebackType
from typing import Any

from fahmi2.core.errors.error_info import ErrorInfo
from fahmi2.core.errors.severity import Severity
from fahmi2.domain.enums import (
    Language,
    LLMModel,
    PhaseId,
    PhaseStatus,
    ReasoningEffort,
    RunStatus,
    SttProvider,
    StylePreset,
)
from fahmi2.domain.glossary import Term
from fahmi2.domain.ids import ProjectId, RunId, VideoId
from fahmi2.domain.phase import PhaseConfig, PhaseExecution
from fahmi2.domain.project import ParallelismConfig, Project, ProjectSettings
from fahmi2.domain.run import Run
from fahmi2.domain.video import VideoExecution

SCHEMA_VERSION = 1

_SCHEMA_RESOURCE_PACKAGE = "fahmi2.infra.storage"
_SCHEMA_RESOURCE_NAME = "_schema.sql"
_META_KEY_SCHEMA_VERSION = "schema_version"
_BUSY_TIMEOUT_MS = 5000
_WAL_MODE = "wal"
_SYNCHRONOUS_NORMAL = "NORMAL"


def _datetime_to_iso(value: datetime) -> str:
    return value.isoformat()


def _datetime_from_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _datetime_from_iso_or_none(value: str | None) -> datetime | None:
    if value is None:
        return None
    return _datetime_from_iso(value)


def _serialize_settings(settings: ProjectSettings) -> str:
    payload: dict[str, Any] = {
        "name": settings.name,
        "input_folder": str(settings.input_folder),
        "workspace_folder": str(settings.workspace_folder),
        "source_language": str(settings.source_language),
        "output_languages": [str(lang) for lang in settings.output_languages],
        "style_preset": str(settings.style_preset),
        "style_directives": settings.style_directives,
        "stt_provider": str(settings.stt_provider),
        "llm_model": str(settings.llm_model),
        "phases_config": {
            str(pid): {
                "thinking_enabled": cfg.thinking_enabled,
                "reasoning_effort": (
                    str(cfg.reasoning_effort)
                    if cfg.reasoning_effort is not None
                    else None
                ),
                "temperature": cfg.temperature,
                "max_retries": cfg.max_retries,
            }
            for pid, cfg in settings.phases_config.items()
        },
        "cost_ceiling_usd": settings.cost_ceiling_usd,
        "parallelism": {
            "stt_cloud_workers": settings.parallelism.stt_cloud_workers,
            "llm_workers": settings.parallelism.llm_workers,
        },
        "delete_audio_after_stt": settings.delete_audio_after_stt,
    }
    return json.dumps(payload, ensure_ascii=False)


def _deserialize_settings(raw: str) -> ProjectSettings:
    payload: dict[str, Any] = json.loads(raw)
    phases_config = {
        PhaseId(pid_str): PhaseConfig(
            thinking_enabled=bool(
                cfg.get("thinking_enabled", cfg.get("enabled_thinking", False))
            ),
            reasoning_effort=(
                ReasoningEffort(cfg["reasoning_effort"])
                if cfg.get("reasoning_effort")
                else None
            ),
            temperature=cfg["temperature"],
            max_retries=cfg["max_retries"],
        )
        for pid_str, cfg in payload["phases_config"].items()
    }
    return ProjectSettings(
        name=payload["name"],
        input_folder=Path(payload["input_folder"]),
        workspace_folder=Path(payload["workspace_folder"]),
        source_language=Language(payload["source_language"]),
        output_languages=tuple(Language(s) for s in payload["output_languages"]),
        style_preset=StylePreset(payload["style_preset"]),
        style_directives=payload["style_directives"],
        stt_provider=SttProvider(payload["stt_provider"]),
        llm_model=LLMModel(payload["llm_model"]),
        phases_config=phases_config,
        cost_ceiling_usd=payload["cost_ceiling_usd"],
        parallelism=ParallelismConfig(
            stt_cloud_workers=payload["parallelism"]["stt_cloud_workers"],
            llm_workers=payload["parallelism"]["llm_workers"],
        ),
        delete_audio_after_stt=payload["delete_audio_after_stt"],
    )


def _serialize_error_info(error: ErrorInfo | None) -> str | None:
    if error is None:
        return None
    return json.dumps(error.to_dict(), ensure_ascii=False)


def _deserialize_error_info(raw: str | None) -> ErrorInfo | None:
    if raw is None:
        return None
    payload = json.loads(raw)
    return ErrorInfo(
        code=payload["code"],
        user_message=payload["user_message"],
        severity=Severity(payload["severity"]),
        technical_details=dict(payload.get("technical_details", {})),
        traceback=payload.get("traceback"),
    )


class SqliteState:
    """Adaptateur SQLite avec WAL, une connexion par thread, busy_timeout long.

    Utilisable comme context manager : ferme la connexion du thread courant à
    la sortie. Sur la 1re ouverture d'une nouvelle DB, applique le schéma et
    initialise ``meta.schema_version``.
    """

    def __init__(self, db_path: Path) -> None:
        """Ouvre la base et applique le schéma si nécessaire.

        Args:
            db_path: Chemin du fichier ``.db``.
        """
        self._db_path = db_path
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._tls = threading.local()
        self._init_database()

    def __enter__(self) -> SqliteState:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    def close(self) -> None:
        """Ferme la connexion locale au thread courant (idempotent)."""
        conn: sqlite3.Connection | None = getattr(self._tls, "conn", None)
        if conn is not None:
            conn.close()
            self._tls.conn = None

    # ------------------------------------------------------------------ schema

    def read_schema_version(self) -> int:
        """Lit la version du schéma dans la table ``meta``.

        Returns:
            La version persistée.
        """
        row = self._get_connection().execute(
            "SELECT value FROM meta WHERE key = ?", (_META_KEY_SCHEMA_VERSION,)
        ).fetchone()
        return int(row[0])

    # ----------------------------------------------------------------- projects

    def upsert_project(self, project: Project) -> None:
        """Insère ou met à jour un projet.

        Args:
            project: Projet à persister.
        """
        self._get_connection().execute(
            """
            INSERT INTO projects (id, name, created_at, settings_json, last_run_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name          = excluded.name,
                created_at    = excluded.created_at,
                settings_json = excluded.settings_json,
                last_run_at   = excluded.last_run_at
            """,
            (
                project.id.value,
                project.settings.name,
                _datetime_to_iso(project.created_at),
                _serialize_settings(project.settings),
                _datetime_to_iso(project.last_run_at) if project.last_run_at else None,
            ),
        )
        self._get_connection().commit()

    def get_project(self, project_id: ProjectId) -> Project | None:
        """Récupère un projet par son identifiant.

        Args:
            project_id: Identifiant.

        Returns:
            Le projet, ou ``None``.
        """
        row = self._get_connection().execute(
            "SELECT id, created_at, settings_json, last_run_at FROM projects WHERE id = ?",
            (project_id.value,),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_project(row)

    def list_projects(self) -> list[Project]:
        """Liste tous les projets.

        Returns:
            Liste de tous les projets persistés.
        """
        rows = self._get_connection().execute(
            "SELECT id, created_at, settings_json, last_run_at FROM projects "
            "ORDER BY created_at"
        ).fetchall()
        return [self._row_to_project(row) for row in rows]

    def delete_project(self, project_id: ProjectId) -> None:
        """Supprime un projet (les runs liés sont cascades).

        Args:
            project_id: Identifiant.
        """
        self._get_connection().execute(
            "DELETE FROM projects WHERE id = ?", (project_id.value,)
        )
        self._get_connection().commit()

    # --------------------------------------------------------------------- runs

    def upsert_run(self, run: Run) -> None:
        """Insère ou met à jour un Run et ses ``VideoExecution`` associées.

        Args:
            run: Run à persister.
        """
        conn = self._get_connection()
        conn.execute(
            """
            INSERT INTO runs (
                id, project_id, status, started_at, finished_at, cost_usd,
                settings_snapshot_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                status                 = excluded.status,
                finished_at            = excluded.finished_at,
                cost_usd               = excluded.cost_usd,
                settings_snapshot_json = excluded.settings_snapshot_json
            """,
            (
                run.id.value,
                run.project_id.value,
                str(run.status),
                _datetime_to_iso(run.started_at),
                _datetime_to_iso(run.finished_at) if run.finished_at else None,
                run.cost_usd,
                _serialize_settings(run.settings_snapshot),
            ),
        )
        for video in run.videos:
            conn.execute(
                """
                INSERT INTO videos (id, run_id, source_path, detected_language)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    source_path       = excluded.source_path,
                    detected_language = excluded.detected_language
                """,
                (
                    video.video_id.value,
                    run.id.value,
                    str(video.source_path),
                    str(video.detected_language) if video.detected_language else None,
                ),
            )
        conn.commit()

    def get_run(self, run_id: RunId) -> Run | None:
        """Récupère un Run par son identifiant.

        Args:
            run_id: Identifiant.

        Returns:
            Le run, ou ``None``.
        """
        row = self._get_connection().execute(
            "SELECT id, project_id, status, started_at, finished_at, cost_usd, "
            "settings_snapshot_json FROM runs WHERE id = ?",
            (run_id.value,),
        ).fetchone()
        if row is None:
            return None
        return self._hydrate_run(self._row_to_run(row))

    def list_runs_for_project(self, project_id: ProjectId) -> list[Run]:
        """Liste tous les Runs liés à un Projet.

        Args:
            project_id: Identifiant du projet parent.

        Returns:
            Liste ordonnée par date de démarrage croissante.
        """
        rows = self._get_connection().execute(
            "SELECT id, project_id, status, started_at, finished_at, cost_usd, "
            "settings_snapshot_json FROM runs WHERE project_id = ? "
            "ORDER BY started_at",
            (project_id.value,),
        ).fetchall()
        return [self._hydrate_run(self._row_to_run(row)) for row in rows]

    def _hydrate_run(self, run: Run) -> Run:
        """Recharge les ``VideoExecution`` associées à un ``Run`` depuis SQLite.

        Args:
            run: Run sans vidéos hydratées (sortie directe de ``_row_to_run``).

        Returns:
            Un ``Run`` immutable avec ses ``VideoExecution`` rechargées dans
            l'ordre de persistance.
        """
        rows = self._get_connection().execute(
            "SELECT id, source_path, detected_language FROM videos "
            "WHERE run_id = ? ORDER BY rowid",
            (run.id.value,),
        ).fetchall()
        videos = tuple(self._row_to_video_execution(row) for row in rows)
        if not videos:
            return run
        return replace(run, videos=videos)

    @staticmethod
    def _row_to_video_execution(row: tuple[Any, ...]) -> VideoExecution:
        """Construit une ``VideoExecution`` depuis une ligne SQL.

        Args:
            row: ``(id, source_path, detected_language)``.

        Returns:
            ``VideoExecution`` reconstituée (sans ses phase_executions, qui
            sont accédées séparément via les méthodes ``get_phase_status`` /
            ``list_phase_executions``).
        """
        video_id_str, source_path_str, detected_language_str = row
        detected_language = (
            Language(detected_language_str) if detected_language_str else None
        )
        return VideoExecution(
            video_id=VideoId(value=video_id_str),
            source_path=Path(source_path_str),
            detected_language=detected_language,
        )

    # ----------------------------------------------------------- phase_executions

    def upsert_phase_execution(
        self,
        run_id: RunId,
        phase_execution: PhaseExecution,
        *,
        video_id: VideoId | None,
    ) -> None:
        """Insère ou met à jour une PhaseExecution.

        SQLite traite ``NULL`` comme distinct dans les contraintes ``UNIQUE``
        : un ``ON CONFLICT(run_id, phase_id, video_id)`` ne se déclenche
        donc jamais pour les phases batch (où ``video_id IS NULL``), ce qui
        accumulerait silencieusement plusieurs lignes. On gère explicitement
        les deux cas : ``ON CONFLICT`` quand ``video_id`` est défini,
        ``DELETE + INSERT`` quand il est ``NULL``.

        Args:
            run_id: Run propriétaire.
            phase_execution: État de la phase.
            video_id: Vidéo associée (``None`` pour les phases batch 2 & 5).
        """
        conn = self._get_connection()
        params = (
            run_id.value,
            str(phase_execution.phase_id),
            video_id.value if video_id else None,
            str(phase_execution.status),
            _datetime_to_iso(phase_execution.started_at)
            if phase_execution.started_at
            else None,
            _datetime_to_iso(phase_execution.finished_at)
            if phase_execution.finished_at
            else None,
            str(phase_execution.artifact_path)
            if phase_execution.artifact_path
            else None,
            phase_execution.retry_count,
            phase_execution.cost_usd,
            _serialize_error_info(phase_execution.error),
        )
        if video_id is None:
            # Phase batch : on garantit l'unicité par (run_id, phase_id, NULL)
            # avec un DELETE explicite, l'INSERT suit toujours.
            conn.execute(
                "DELETE FROM phase_executions "
                "WHERE run_id = ? AND phase_id = ? AND video_id IS NULL",
                (run_id.value, str(phase_execution.phase_id)),
            )
            conn.execute(
                """
                INSERT INTO phase_executions (
                    run_id, phase_id, video_id, status, started_at, finished_at,
                    artifact_path, retry_count, cost_usd, error_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                params,
            )
        else:
            conn.execute(
                """
                INSERT INTO phase_executions (
                    run_id, phase_id, video_id, status, started_at, finished_at,
                    artifact_path, retry_count, cost_usd, error_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id, phase_id, video_id) DO UPDATE SET
                    status        = excluded.status,
                    started_at    = excluded.started_at,
                    finished_at   = excluded.finished_at,
                    artifact_path = excluded.artifact_path,
                    retry_count   = excluded.retry_count,
                    cost_usd      = excluded.cost_usd,
                    error_json    = excluded.error_json
                """,
                params,
            )
        conn.commit()

    def get_phase_status(
        self,
        run_id: RunId,
        phase_id: PhaseId,
        *,
        video_id: VideoId | None,
    ) -> PhaseStatus | None:
        """Lit le statut d'une PhaseExecution.

        Args:
            run_id: Run propriétaire.
            phase_id: Phase.
            video_id: Vidéo associée ou ``None`` (phase batch).

        Returns:
            Le ``PhaseStatus``, ou ``None`` si l'entrée n'existe pas.
        """
        row = self._get_connection().execute(
            "SELECT status FROM phase_executions "
            "WHERE run_id = ? AND phase_id = ? AND video_id IS ?",
            (run_id.value, str(phase_id), video_id.value if video_id else None),
        ).fetchone()
        if row is None:
            return None
        return PhaseStatus(row[0])

    def list_phase_executions(self, run_id: RunId) -> list[PhaseExecution]:
        """Liste toutes les PhaseExecution d'un Run.

        Args:
            run_id: Run propriétaire.

        Returns:
            Liste des exécutions de phase, ordonnée par id interne.
        """
        rows = self._get_connection().execute(
            "SELECT phase_id, status, started_at, finished_at, artifact_path, "
            "retry_count, cost_usd, error_json FROM phase_executions "
            "WHERE run_id = ? ORDER BY id",
            (run_id.value,),
        ).fetchall()
        return [self._row_to_phase_execution(row) for row in rows]

    # ------------------------------------------------------------- glossary_terms

    def upsert_glossary_term(
        self,
        run_id: RunId,
        language: Language,
        term: Term,
    ) -> None:
        """Insère ou met à jour un terme du glossaire.

        Args:
            run_id: Run propriétaire.
            language: Langue du glossaire.
            term: Terme à persister.
        """
        self._get_connection().execute(
            """
            INSERT INTO glossary_terms (
                run_id, language, term, definition, acronym,
                sources_json, aliases_json, cross_lang_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(run_id, language, term) DO UPDATE SET
                definition      = excluded.definition,
                acronym         = excluded.acronym,
                sources_json    = excluded.sources_json,
                aliases_json    = excluded.aliases_json,
                cross_lang_json = excluded.cross_lang_json
            """,
            (
                run_id.value,
                str(language),
                term.term,
                term.definition,
                term.acronym,
                json.dumps([s.value for s in term.sources], ensure_ascii=False),
                json.dumps(list(term.aliases), ensure_ascii=False),
                json.dumps(
                    {str(k): v for k, v in term.cross_lang.items()},
                    ensure_ascii=False,
                ),
            ),
        )
        self._get_connection().commit()

    def list_glossary_terms(self, run_id: RunId, language: Language) -> list[Term]:
        """Liste les termes du glossaire pour un Run et une langue.

        Args:
            run_id: Run propriétaire.
            language: Langue.

        Returns:
            Liste des termes ordonnée par ``term`` croissant.
        """
        rows = self._get_connection().execute(
            "SELECT term, definition, acronym, sources_json, aliases_json, "
            "cross_lang_json FROM glossary_terms "
            "WHERE run_id = ? AND language = ? ORDER BY term",
            (run_id.value, str(language)),
        ).fetchall()
        return [self._row_to_term(row) for row in rows]

    # ----------------------------------------------------------------- internals

    def _get_connection(self) -> sqlite3.Connection:
        conn: sqlite3.Connection | None = getattr(self._tls, "conn", None)
        if conn is None:
            conn = self._open_connection()
            self._tls.conn = conn
        return conn

    def _open_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self._db_path, isolation_level=None)
        conn.execute(f"PRAGMA journal_mode = {_WAL_MODE}")
        conn.execute(f"PRAGMA synchronous = {_SYNCHRONOUS_NORMAL}")
        conn.execute(f"PRAGMA busy_timeout = {_BUSY_TIMEOUT_MS}")
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def _init_database(self) -> None:
        conn = self._get_connection()
        ddl = self._load_schema_ddl()
        conn.executescript(ddl)
        self._apply_soft_migrations(conn)
        existing = conn.execute(
            "SELECT value FROM meta WHERE key = ?", (_META_KEY_SCHEMA_VERSION,)
        ).fetchone()
        if existing is None:
            conn.execute(
                "INSERT INTO meta (key, value) VALUES (?, ?)",
                (_META_KEY_SCHEMA_VERSION, str(SCHEMA_VERSION)),
            )

    @staticmethod
    def _apply_soft_migrations(conn: sqlite3.Connection) -> None:
        """Applique les migrations légères additives sur une DB pré-existante.

        Limitées aux ``ALTER TABLE ... ADD COLUMN`` qui sont rétrocompatibles
        et ne perdent aucune donnée. Les changements de schéma plus invasifs
        passent par le ``MigrationRunner`` formel.

        Args:
            conn: Connexion SQLite ouverte sur la DB.
        """
        existing_cols = {
            row[1]
            for row in conn.execute("PRAGMA table_info(glossary_terms)").fetchall()
        }
        if "acronym" not in existing_cols:
            conn.execute("ALTER TABLE glossary_terms ADD COLUMN acronym TEXT")

        # Nettoyage rétroactif : SQLite a permis l'accumulation de doublons sur
        # les phases batch (video_id NULL) tant que upsert_phase_execution ne
        # gérait pas explicitement le NULL. On garde uniquement la ligne la
        # plus récente (id MAX) par (run_id, phase_id) avec video_id NULL.
        conn.execute(
            """
            DELETE FROM phase_executions
            WHERE video_id IS NULL
              AND id NOT IN (
                SELECT MAX(id) FROM phase_executions
                WHERE video_id IS NULL
                GROUP BY run_id, phase_id
              )
            """
        )

    @staticmethod
    def _load_schema_ddl() -> str:
        return (
            files(_SCHEMA_RESOURCE_PACKAGE)
            .joinpath(_SCHEMA_RESOURCE_NAME)
            .read_text(encoding="utf-8")
        )

    # ----------------------------------------------------- row → entity helpers

    @staticmethod
    def _row_to_project(row: tuple[Any, ...]) -> Project:
        project_id, created_at_str, settings_json, last_run_at_str = row
        return Project(
            id=ProjectId(value=project_id),
            settings=_deserialize_settings(settings_json),
            created_at=_datetime_from_iso(created_at_str),
            last_run_at=_datetime_from_iso_or_none(last_run_at_str),
        )

    @staticmethod
    def _row_to_run(row: tuple[Any, ...]) -> Run:
        (
            run_id,
            project_id,
            status_str,
            started_at_str,
            finished_at_str,
            cost_usd,
            settings_json,
        ) = row
        return Run(
            id=RunId(value=run_id),
            project_id=ProjectId(value=project_id),
            started_at=_datetime_from_iso(started_at_str),
            status=RunStatus(status_str),
            settings_snapshot=_deserialize_settings(settings_json),
            finished_at=_datetime_from_iso_or_none(finished_at_str),
            cost_usd=cost_usd,
        )

    @staticmethod
    def _row_to_phase_execution(row: tuple[Any, ...]) -> PhaseExecution:
        (
            phase_id_str,
            status_str,
            started_at_str,
            finished_at_str,
            artifact_path_str,
            retry_count,
            cost_usd,
            error_json,
        ) = row
        return PhaseExecution(
            phase_id=PhaseId(phase_id_str),
            status=PhaseStatus(status_str),
            started_at=_datetime_from_iso_or_none(started_at_str),
            finished_at=_datetime_from_iso_or_none(finished_at_str),
            artifact_path=Path(artifact_path_str) if artifact_path_str else None,
            retry_count=retry_count,
            cost_usd=cost_usd,
            error=_deserialize_error_info(error_json),
        )

    @staticmethod
    def _row_to_term(row: tuple[Any, ...]) -> Term:
        (
            term_str,
            definition,
            acronym,
            sources_json,
            aliases_json,
            cross_lang_json,
        ) = row
        sources: Iterable[str] = json.loads(sources_json)
        aliases: Iterable[str] = json.loads(aliases_json)
        cross_lang_raw: dict[str, str] = json.loads(cross_lang_json)
        return Term(
            term=term_str,
            definition=definition,
            acronym=acronym,
            sources=tuple(VideoId(value=sid) for sid in sources),
            aliases=tuple(aliases),
            cross_lang={Language(k): v for k, v in cross_lang_raw.items()},
        )
