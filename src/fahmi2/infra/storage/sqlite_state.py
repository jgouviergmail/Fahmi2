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
from dataclasses import dataclass, replace
from datetime import datetime
from importlib.resources import files
from pathlib import Path
from types import TracebackType
from typing import Any

from fahmi2.core.errors.error_info import ErrorInfo
from fahmi2.core.errors.exceptions import StorageError
from fahmi2.core.errors.severity import Severity
from fahmi2.domain.enums import (
    BloomObjective,
    ExportFormat,
    Language,
    LLMModel,
    PhaseId,
    PhaseStatus,
    ReasoningEffort,
    RunStatus,
    SourceKind,
    SttProvider,
    StylePreset,
    SupportDensity,
    SupportType,
    TargetAudience,
)
from fahmi2.domain.generation import GenerationSettings, ParallelismConfig
from fahmi2.domain.ids import ProjectId, RunId, SourceId
from fahmi2.domain.pedagogy import DEFAULT_PEDAGOGY_LLM_WORKERS, PedagogySettings
from fahmi2.domain.phase import PhaseConfig, PhaseExecution
from fahmi2.domain.project import Project
from fahmi2.domain.run import Run
from fahmi2.domain.source import InputSource, SourceExecution

SCHEMA_VERSION = 1

_SCHEMA_RESOURCE_PACKAGE = "fahmi2.infra.storage"
_SCHEMA_RESOURCE_NAME = "_schema.sql"
_META_KEY_SCHEMA_VERSION = "schema_version"
_BUSY_TIMEOUT_MS = 5000
_WAL_MODE = "wal"
_SYNCHRONOUS_NORMAL = "NORMAL"

# Format du blob ``projects.settings_json`` : v2 = par fonctionnalité.
_BLOB_VERSION = 2
_BLOB_KEY_VERSION = "version"
_BLOB_KEY_WORKSPACE = "workspace_folder"
_BLOB_KEY_GENERATION = "generation"
_BLOB_KEY_PEDAGOGY = "pedagogy"


@dataclass(frozen=True)
class PhaseCell:
    """Statut + coût d'une exécution de phase pour une ``(phase, source)``.

    Attributes:
        phase_id: Phase.
        source_id: Source (``None`` pour une phase batch).
        status: Statut.
        cost_usd: Coût en USD.
        retry_count: Nombre de retries.
    """

    phase_id: PhaseId
    source_id: SourceId | None
    status: PhaseStatus
    cost_usd: float
    retry_count: int


def _datetime_to_iso(value: datetime) -> str:
    return value.isoformat()


def _datetime_from_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)


def _datetime_from_iso_or_none(value: str | None) -> datetime | None:
    if value is None:
        return None
    return _datetime_from_iso(value)


def _serialize_generation_settings(gen: GenerationSettings) -> dict[str, Any]:
    """Sérialise un ``GenerationSettings`` en dict JSON-compatible.

    Args:
        gen: Réglages de génération.

    Returns:
        Dict prêt à être encodé en JSON (sans nom ni emplacement).
    """
    return {
        "input_folder": str(gen.input_folder),
        "source_language": str(gen.source_language),
        "output_languages": [str(lang) for lang in gen.output_languages],
        "style_preset": str(gen.style_preset),
        "style_directives": gen.style_directives,
        "stt_provider": str(gen.stt_provider),
        "llm_model": str(gen.llm_model),
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
            for pid, cfg in gen.phases_config.items()
        },
        "cost_ceiling_usd": gen.cost_ceiling_usd,
        "parallelism": {
            "stt_cloud_workers": gen.parallelism.stt_cloud_workers,
            "llm_workers": gen.parallelism.llm_workers,
        },
        "delete_audio_after_stt": gen.delete_audio_after_stt,
        "export_formats": sorted(f.value for f in gen.export_formats),
        "reformulate_documents": gen.reformulate_documents,
        "youtube_urls": list(gen.youtube_urls),
        "source_order": list(gen.source_order),
        "excluded_sources": list(gen.excluded_sources),
    }


def _deserialize_generation_settings(payload: dict[str, Any]) -> GenerationSettings:
    """Désérialise un ``GenerationSettings`` depuis un dict.

    Les clés inconnues (ex. ``name``/``workspace_folder`` d'un ancien blob v1 à
    plat) sont ignorées : seules les clés de génération sont lues.

    Args:
        payload: Dict (sous-objet ``generation`` v2, ou blob v1 complet).

    Returns:
        Le ``GenerationSettings`` reconstitué.

    Raises:
        KeyError: Si une clé requise manque (capturée par l'appelant).
        ValueError: Si une valeur d'enum est invalide (capturée par l'appelant).
    """
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
    return GenerationSettings(
        input_folder=Path(payload["input_folder"]),
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
        export_formats=frozenset(
            ExportFormat(f) for f in payload.get("export_formats", [])
        ),
        reformulate_documents=bool(payload.get("reformulate_documents", True)),
        youtube_urls=tuple(payload.get("youtube_urls", [])),
        source_order=tuple(payload.get("source_order", [])),
        excluded_sources=tuple(payload.get("excluded_sources", [])),
    )


def _serialize_pedagogy_settings(ped: PedagogySettings) -> dict[str, Any]:
    """Sérialise un ``PedagogySettings`` en dict JSON-compatible.

    Args:
        ped: Réglages pédagogiques.

    Returns:
        Dict prêt à être encodé en JSON.
    """
    return {
        "selected_supports": sorted(s.value for s in ped.selected_supports),
        "separate_correction": sorted(s.value for s in ped.separate_correction),
        "target_audience": str(ped.target_audience),
        "bloom_objective": str(ped.bloom_objective),
        "pedagogy_directives": ped.pedagogy_directives,
        "languages": [str(lang) for lang in ped.languages],
        "density": str(ped.density),
        "llm_model": str(ped.llm_model),
        "llm_config": {
            "thinking_enabled": ped.llm_config.thinking_enabled,
            "reasoning_effort": (
                str(ped.llm_config.reasoning_effort)
                if ped.llm_config.reasoning_effort is not None
                else None
            ),
            "temperature": ped.llm_config.temperature,
            "max_retries": ped.llm_config.max_retries,
        },
        "cost_ceiling_usd": ped.cost_ceiling_usd,
        "export_formats": sorted(f.value for f in ped.export_formats),
        "llm_workers": ped.llm_workers,
    }


def _known_support_types(values: list[str]) -> frozenset[SupportType]:
    """Convertit des valeurs de support en ``SupportType``, ignorant les inconnus.

    Tolère les réglages persistés référant un support retiré (ex. l'ancien
    ``flashcards_glossary``) : la valeur inconnue est ignorée plutôt que de lever.

    Args:
        values: Valeurs brutes (chaînes) issues du blob persisté.

    Returns:
        Les ``SupportType`` reconnus.
    """
    known = {s.value for s in SupportType}
    return frozenset(SupportType(v) for v in values if v in known)


def _deserialize_pedagogy_settings(payload: dict[str, Any]) -> PedagogySettings:
    """Désérialise un ``PedagogySettings`` depuis un dict.

    Args:
        payload: Sous-objet ``pedagogy`` du blob v2.

    Returns:
        Le ``PedagogySettings`` reconstitué.

    Raises:
        KeyError: Si une clé requise manque (capturée par l'appelant).
        ValueError: Si une valeur d'enum est invalide (capturée par l'appelant).
    """
    cfg = payload["llm_config"]
    return PedagogySettings(
        selected_supports=_known_support_types(payload["selected_supports"]),
        separate_correction=_known_support_types(payload["separate_correction"]),
        target_audience=TargetAudience(payload["target_audience"]),
        bloom_objective=BloomObjective(payload["bloom_objective"]),
        pedagogy_directives=payload["pedagogy_directives"],
        languages=tuple(Language(s) for s in payload["languages"]),
        density=SupportDensity(payload["density"]),
        llm_model=LLMModel(payload["llm_model"]),
        llm_config=PhaseConfig(
            thinking_enabled=bool(cfg.get("thinking_enabled", False)),
            reasoning_effort=(
                ReasoningEffort(cfg["reasoning_effort"])
                if cfg.get("reasoning_effort")
                else None
            ),
            temperature=cfg["temperature"],
            max_retries=cfg["max_retries"],
        ),
        cost_ceiling_usd=payload["cost_ceiling_usd"],
        export_formats=frozenset(ExportFormat(f) for f in payload["export_formats"]),
        llm_workers=int(payload.get("llm_workers", DEFAULT_PEDAGOGY_LLM_WORKERS)),
    )


def _serialize_project_blob(project: Project) -> str:
    """Sérialise le blob v2 ``settings_json`` d'un projet.

    Args:
        project: Projet à sérialiser.

    Returns:
        Chaîne JSON ``{version, workspace_folder, generation, pedagogy}``.
    """
    payload: dict[str, Any] = {
        _BLOB_KEY_VERSION: _BLOB_VERSION,
        _BLOB_KEY_WORKSPACE: str(project.workspace_folder),
        _BLOB_KEY_GENERATION: (
            _serialize_generation_settings(project.generation)
            if project.generation is not None
            else None
        ),
        _BLOB_KEY_PEDAGOGY: (
            _serialize_pedagogy_settings(project.pedagogy)
            if project.pedagogy is not None
            else None
        ),
    }
    return json.dumps(payload, ensure_ascii=False)


def _deserialize_project_blob(
    raw: str,
) -> tuple[Path, GenerationSettings | None, PedagogySettings | None]:
    """Désérialise le blob d'un projet (v2, ou v1 à plat migré à la lecture).

    Un blob **sans** clé ``version`` est traité comme v1 « à plat » : son contenu
    est l'ancien ``ProjectSettings``, dont on extrait l'emplacement et la
    génération (les clés ``name``/``workspace_folder`` sont ignorées par
    ``_deserialize_generation_settings``). Un blob v1 n'a pas de pédagogie
    (``pedagogy = None``).

    Args:
        raw: Chaîne JSON stockée en base.

    Returns:
        ``(workspace_folder, generation_or_none, pedagogy_or_none)``.

    Raises:
        StorageError: Si le blob est illisible ou incomplet.
    """
    try:
        payload: dict[str, Any] = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        raise StorageError(
            code="STORAGE.PROJECT_BLOB_INVALID",
            user_message=(
                "Les réglages d'un projet sont illisibles en base. Le projet "
                "ne peut pas être chargé."
            ),
            severity=Severity.ERROR,
            technical_details={"raw_prefix": raw[:200]},
        ) from exc
    try:
        workspace_folder = Path(payload[_BLOB_KEY_WORKSPACE])
        if _BLOB_KEY_VERSION not in payload:
            generation: GenerationSettings | None = _deserialize_generation_settings(
                payload
            )
        else:
            gen_payload = payload.get(_BLOB_KEY_GENERATION)
            generation = (
                _deserialize_generation_settings(gen_payload)
                if gen_payload is not None
                else None
            )
        ped_payload = payload.get(_BLOB_KEY_PEDAGOGY)
        pedagogy = (
            _deserialize_pedagogy_settings(ped_payload)
            if ped_payload is not None
            else None
        )
    except (KeyError, ValueError) as exc:
        raise StorageError(
            code="STORAGE.PROJECT_BLOB_INVALID",
            user_message=(
                "Les réglages d'un projet sont incomplets ou invalides en base."
            ),
            severity=Severity.ERROR,
            technical_details={"missing_or_invalid": str(exc)},
        ) from exc
    return workspace_folder, generation, pedagogy


def _serialize_run_snapshot(gen: GenerationSettings) -> str:
    """Sérialise le snapshot de réglages d'un Run (= ``GenerationSettings``).

    Args:
        gen: Réglages figés au démarrage du run.

    Returns:
        Chaîne JSON.
    """
    return json.dumps(_serialize_generation_settings(gen), ensure_ascii=False)


def _deserialize_run_snapshot(raw: str) -> GenerationSettings:
    """Désérialise le snapshot d'un Run (tolère les blobs v1 à plat).

    Args:
        raw: Chaîne JSON stockée.

    Returns:
        Le ``GenerationSettings`` figé.

    Raises:
        StorageError: Si le snapshot est illisible ou incomplet.
    """
    try:
        payload: dict[str, Any] = json.loads(raw)
        return _deserialize_generation_settings(payload)
    except (json.JSONDecodeError, TypeError, KeyError, ValueError) as exc:
        raise StorageError(
            code="STORAGE.RUN_SNAPSHOT_INVALID",
            user_message="Le snapshot de réglages d'un run est illisible en base.",
            severity=Severity.ERROR,
            technical_details={"raw_prefix": raw[:200]},
        ) from exc


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
                project.name,
                _datetime_to_iso(project.created_at),
                _serialize_project_blob(project),
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
            "SELECT id, name, created_at, settings_json, last_run_at "
            "FROM projects WHERE id = ?",
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
            "SELECT id, name, created_at, settings_json, last_run_at FROM projects "
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

    def delete_runs_for_project(self, project_id: ProjectId) -> None:
        """Supprime tous les runs d'un projet (sans supprimer le projet).

        Les ``sources`` et ``phase_executions`` liées sont supprimées par cascade
        (``ON DELETE CASCADE``). Utilisé par la « Réinitialisation » de la
        Génération (le projet est conservé, son historique d'exécution effacé).

        Args:
            project_id: Projet dont les runs sont supprimés.
        """
        conn = self._get_connection()
        conn.execute("DELETE FROM runs WHERE project_id = ?", (project_id.value,))
        conn.commit()

    # --------------------------------------------------------------------- runs

    def upsert_run(self, run: Run) -> None:
        """Insère ou met à jour un Run et ses ``SourceExecution`` associées.

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
                _serialize_run_snapshot(run.settings_snapshot),
            ),
        )
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
        """Recharge les ``SourceExecution`` associées à un ``Run`` depuis SQLite.

        Args:
            run: Run sans sources hydratées (sortie directe de ``_row_to_run``).

        Returns:
            Un ``Run`` immutable avec ses ``SourceExecution`` rechargées dans
            l'ordre de persistance.
        """
        rows = self._get_connection().execute(
            "SELECT id, source_kind, source_location, detected_language FROM sources "
            "WHERE run_id = ? ORDER BY rowid",
            (run.id.value,),
        ).fetchall()
        sources = tuple(self._row_to_source_execution(row) for row in rows)
        if not sources:
            return run
        return replace(run, sources=sources)

    @staticmethod
    def _row_to_source_execution(row: tuple[Any, ...]) -> SourceExecution:
        """Construit une ``SourceExecution`` depuis une ligne SQL.

        Args:
            row: ``(id, source_kind, source_location, detected_language)``.

        Returns:
            ``SourceExecution`` reconstituée (sans ses phase_executions, qui
            sont accédées séparément via les méthodes ``get_phase_status`` /
            ``list_phase_executions``).
        """
        source_id_str, kind_str, location_str, detected_language_str = row
        detected_language = (
            Language(detected_language_str) if detected_language_str else None
        )
        return SourceExecution(
            source_id=SourceId(value=source_id_str),
            source=InputSource(kind=SourceKind(kind_str), location=location_str),
            detected_language=detected_language,
        )

    # ----------------------------------------------------------- phase_executions

    def upsert_phase_execution(
        self,
        run_id: RunId,
        phase_execution: PhaseExecution,
        *,
        source_id: SourceId | None,
    ) -> None:
        """Insère ou met à jour une PhaseExecution.

        SQLite traite ``NULL`` comme distinct dans les contraintes ``UNIQUE``
        : un ``ON CONFLICT(run_id, phase_id, source_id)`` ne se déclenche
        donc jamais pour les phases batch (où ``source_id IS NULL``), ce qui
        accumulerait silencieusement plusieurs lignes. On gère explicitement
        les deux cas : ``ON CONFLICT`` quand ``source_id`` est défini,
        ``DELETE + INSERT`` quand il est ``NULL``.

        Args:
            run_id: Run propriétaire.
            phase_execution: État de la phase.
            source_id: Source associée (``None`` pour les phases batch 2 & 5).
        """
        conn = self._get_connection()
        params = (
            run_id.value,
            str(phase_execution.phase_id),
            source_id.value if source_id else None,
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
        if source_id is None:
            # Phase batch : on garantit l'unicité par (run_id, phase_id, NULL)
            # avec un DELETE explicite, l'INSERT suit toujours.
            conn.execute(
                "DELETE FROM phase_executions "
                "WHERE run_id = ? AND phase_id = ? AND source_id IS NULL",
                (run_id.value, str(phase_execution.phase_id)),
            )
            conn.execute(
                """
                INSERT INTO phase_executions (
                    run_id, phase_id, source_id, status, started_at, finished_at,
                    artifact_path, retry_count, cost_usd, error_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                params,
            )
        else:
            conn.execute(
                """
                INSERT INTO phase_executions (
                    run_id, phase_id, source_id, status, started_at, finished_at,
                    artifact_path, retry_count, cost_usd, error_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(run_id, phase_id, source_id) DO UPDATE SET
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
        source_id: SourceId | None,
    ) -> PhaseStatus | None:
        """Lit le statut d'une PhaseExecution.

        Args:
            run_id: Run propriétaire.
            phase_id: Phase.
            source_id: Source associée ou ``None`` (phase batch).

        Returns:
            Le ``PhaseStatus``, ou ``None`` si l'entrée n'existe pas.
        """
        row = self._get_connection().execute(
            "SELECT status FROM phase_executions "
            "WHERE run_id = ? AND phase_id = ? AND source_id IS ?",
            (run_id.value, str(phase_id), source_id.value if source_id else None),
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

    def list_phase_cells(self, run_id: RunId) -> list[PhaseCell]:
        """Liste le statut + coût par ``(phase, source)`` d'un Run.

        Args:
            run_id: Run propriétaire.

        Returns:
            Une ``PhaseCell`` par exécution (``source_id`` ``None`` = phase batch).
        """
        rows = self._get_connection().execute(
            "SELECT phase_id, source_id, status, cost_usd, retry_count "
            "FROM phase_executions WHERE run_id = ? ORDER BY id",
            (run_id.value,),
        ).fetchall()
        return [
            PhaseCell(
                phase_id=PhaseId(row[0]),
                source_id=SourceId(value=row[1]) if row[1] else None,
                status=PhaseStatus(row[2]),
                cost_usd=row[3],
                retry_count=row[4],
            )
            for row in rows
        ]

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
        self._migrate_videos_to_sources(conn)
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
    def _migrate_videos_to_sources(conn: sqlite3.Connection) -> None:
        """Migre l'ancien schéma (table ``videos`` / colonne ``video_id``) vers
        ``sources`` / ``source_id``. Idempotente : ne fait rien si déjà migré.

        Doit être appelée **avant** le chargement du DDL (qui crée ``sources``
        en ``IF NOT EXISTS``), sinon le renommage de table entrerait en conflit
        avec une table ``sources`` vide fraîchement créée.

        Args:
            conn: Connexion SQLite ouverte sur la DB.
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

    @staticmethod
    def _apply_soft_migrations(conn: sqlite3.Connection) -> None:
        """Applique les migrations légères additives sur une DB pré-existante.

        Limitées aux ``ALTER TABLE ... ADD COLUMN`` qui sont rétrocompatibles
        et ne perdent aucune donnée. Les changements de schéma plus invasifs
        passent par le ``MigrationRunner`` formel.

        Args:
            conn: Connexion SQLite ouverte sur la DB.
        """
        # La table glossary_terms (intention de socle jamais branchée) est
        # retirée : le glossaire est lu sur disque comme les autres documents
        # générés (glossary_master.json).
        conn.execute("DROP TABLE IF EXISTS glossary_terms")

        # Nettoyage rétroactif : SQLite a permis l'accumulation de doublons sur
        # les phases batch (source_id NULL) tant que upsert_phase_execution ne
        # gérait pas explicitement le NULL. On garde uniquement la ligne la
        # plus récente (id MAX) par (run_id, phase_id) avec source_id NULL.
        conn.execute(
            """
            DELETE FROM phase_executions
            WHERE source_id IS NULL
              AND id NOT IN (
                SELECT MAX(id) FROM phase_executions
                WHERE source_id IS NULL
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
        project_id, name, created_at_str, settings_json, last_run_at_str = row
        workspace_folder, generation, pedagogy = _deserialize_project_blob(
            settings_json
        )
        return Project(
            id=ProjectId(value=project_id),
            name=name,
            workspace_folder=workspace_folder,
            created_at=_datetime_from_iso(created_at_str),
            last_run_at=_datetime_from_iso_or_none(last_run_at_str),
            generation=generation,
            pedagogy=pedagogy,
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
            settings_snapshot=_deserialize_run_snapshot(settings_json),
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

