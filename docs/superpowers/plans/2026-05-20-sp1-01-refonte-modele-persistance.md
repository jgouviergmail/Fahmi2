# SP1 · Plan 01 — Refonte du modèle + persistance + migration

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (exécution
> inline, par lots avec points de contrôle) — pas de subagents (préférence projet).
> Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scinder `ProjectSettings` en `GenerationSettings` + `Project` minimal (nom +
emplacement), persister le tout en blob JSON v2 avec migration lenient v1→v2, **sans
changer le comportement fonctionnel de la génération**.

**Architecture:** Renommage/scission transverse domaine → persistance → application →
UI minimale, mené en une tranche cohérente qui laisse `pytest`/`ruff`/`mypy` au vert.
La migration v1→v2 se fait **à la lecture** du blob (aucun `ALTER TABLE`, aucun
déplacement de fichier — décision « repartir propre »).

**Tech Stack:** Python 3.12, `@dataclass(frozen=True)`, SQLite (blob JSON), pytest,
ruff, mypy `--strict`, PySide6 (UI inchangée dans ce plan).

**Rappels directives projet (à respecter à chaque étape) :** pas de magic value (tout
en constante), docstrings Google (Args/Returns/Raises) + docstring de module, réutiliser
les helpers/patterns existants, DRY/YAGNI/KISS/SRP, nommage cohérent. L'interpréteur est
`.venv\Scripts\python.exe`.

---

## Task 1 : Créer `domain/generation.py` (`GenerationSettings` + `ParallelismConfig`)

**Files:**
- Create: `src/fahmi2/domain/generation.py`
- Test: `tests/unit/domain/test_generation.py`
- Modify (suppression du contenu déplacé) : `src/fahmi2/domain/project.py` (Task 2)

- [ ] **Step 1 : Écrire le test d'invariants de `GenerationSettings` (échoue)**

```python
# tests/unit/domain/test_generation.py
"""Tests des invariants de ``GenerationSettings``."""

from __future__ import annotations

from pathlib import Path

import pytest

from fahmi2.domain.enums import Language, LLMModel, PhaseId, SttProvider, StylePreset
from fahmi2.domain.generation import (
    GENERATION_WORKSPACE_SUBDIR,
    GenerationSettings,
    ParallelismConfig,
)
from fahmi2.domain.phase import PhaseConfig


def _valid_phases() -> dict[PhaseId, PhaseConfig]:
    return {pid: PhaseConfig() for pid in PhaseId if pid is not PhaseId.STT}


def _make(**overrides: object) -> GenerationSettings:
    base: dict[str, object] = {
        "input_folder": Path("./input"),
        "source_language": Language.FR,
        "output_languages": (Language.FR,),
        "style_preset": StylePreset.STANDARD,
        "style_directives": "",
        "stt_provider": SttProvider.OPENAI_CLOUD,
        "llm_model": LLMModel.DEEPSEEK_V4_FLASH,
        "phases_config": _valid_phases(),
        "cost_ceiling_usd": None,
        "parallelism": ParallelismConfig(),
        "delete_audio_after_stt": True,
    }
    base.update(overrides)
    return GenerationSettings(**base)  # type: ignore[arg-type]


def test_generation_subdir_constant() -> None:
    assert GENERATION_WORKSPACE_SUBDIR == "generation"


def test_valid_settings_construct() -> None:
    settings = _make()
    assert settings.source_language is Language.FR


def test_source_language_must_be_in_outputs() -> None:
    with pytest.raises(ValueError, match="source_language"):
        _make(source_language=Language.EN, output_languages=(Language.FR,))


def test_phases_config_must_cover_llm_phases() -> None:
    incomplete = {PhaseId.REFORMULATION: PhaseConfig()}
    with pytest.raises(ValueError, match="phases_config"):
        _make(phases_config=incomplete)


def test_negative_ceiling_rejected() -> None:
    with pytest.raises(ValueError, match="cost_ceiling_usd"):
        _make(cost_ceiling_usd=-1.0)
```

- [ ] **Step 2 : Lancer le test (échoue : module absent)**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/domain/test_generation.py -q`
Expected: FAIL — `ModuleNotFoundError: fahmi2.domain.generation`.

- [ ] **Step 3 : Créer le module `generation.py`**

```python
# src/fahmi2/domain/generation.py
"""Entités de la fonctionnalité Génération : ``GenerationSettings``, ``ParallelismConfig``.

``GenerationSettings`` regroupe tous les paramètres métier de la génération (vidéos →
document consolidé). Le nom et l'emplacement du projet n'en font **pas** partie : ils
sont portés par ``Project`` (identité minimale, cf. ``domain.project``).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fahmi2.domain.enums import (
    Language,
    LLMModel,
    PhaseId,
    SttProvider,
    StylePreset,
)
from fahmi2.domain.phase import PhaseConfig

_DEFAULT_STT_CLOUD_WORKERS = 3
_DEFAULT_LLM_WORKERS = 4
_LLM_PHASES: frozenset[PhaseId] = frozenset(
    p for p in PhaseId if p is not PhaseId.STT
)

#: Sous-dossier du workspace dédié aux artefacts de la fonctionnalité Génération.
GENERATION_WORKSPACE_SUBDIR = "generation"


@dataclass(frozen=True)
class ParallelismConfig:
    """Configuration de parallélisme du pipeline.

    Note:
        STT local est toujours séquentiel (1 GPU). Seuls STT cloud et LLM sont
        parallélisables.

    Attributes:
        stt_cloud_workers: Workers concurrents pour le STT cloud (>= 1).
        llm_workers: Workers concurrents pour les appels LLM (>= 1).
    """

    stt_cloud_workers: int = _DEFAULT_STT_CLOUD_WORKERS
    llm_workers: int = _DEFAULT_LLM_WORKERS

    def __post_init__(self) -> None:
        if self.stt_cloud_workers < 1:
            raise ValueError("stt_cloud_workers must be >= 1")
        if self.llm_workers < 1:
            raise ValueError("llm_workers must be >= 1")


@dataclass(frozen=True)
class GenerationSettings:
    """Paramètres de la fonctionnalité Génération (vidéos → document consolidé).

    Les phases LLM (1..7) doivent toutes être configurées dans ``phases_config``.
    ``output_languages`` doit toujours contenir ``source_language``.

    Attributes:
        input_folder: Dossier d'entrée contenant les vidéos.
        source_language: Langue source du contenu.
        output_languages: Tuple des langues de sortie demandées.
        style_preset: Style de rendu.
        style_directives: Directives stylistiques libres (peuvent être vides).
        stt_provider: Provider STT (local ou cloud).
        llm_model: Modèle DeepSeek utilisé.
        phases_config: Configuration des phases LLM 1..7.
        cost_ceiling_usd: Plafond de coût (``None`` = pas de plafond).
        parallelism: Configuration de parallélisme.
        delete_audio_after_stt: Si ``True``, l'audio extrait est supprimé après STT.
    """

    input_folder: Path
    source_language: Language
    output_languages: tuple[Language, ...]
    style_preset: StylePreset
    style_directives: str
    stt_provider: SttProvider
    llm_model: LLMModel
    phases_config: dict[PhaseId, PhaseConfig]
    cost_ceiling_usd: float | None
    parallelism: ParallelismConfig
    delete_audio_after_stt: bool

    def __post_init__(self) -> None:
        if not self.output_languages:
            raise ValueError("output_languages must contain at least one language")
        if self.source_language not in self.output_languages:
            raise ValueError(
                f"output_languages must contain source_language "
                f"({self.source_language})"
            )
        configured = set(self.phases_config)
        expected = set(_LLM_PHASES)
        if configured != expected:
            missing = sorted(expected - configured)
            extra = sorted(configured - expected)
            raise ValueError(
                "phases_config must cover exactly LLM phases (1..7). "
                f"Missing: {missing}, Extra: {extra}"
            )
        if self.cost_ceiling_usd is not None and self.cost_ceiling_usd < 0:
            raise ValueError(
                f"cost_ceiling_usd must be >= 0 or None, got {self.cost_ceiling_usd}"
            )
```

- [ ] **Step 4 : Lancer le test (passe)**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/domain/test_generation.py -q`
Expected: PASS (5 tests).

*(Pas de commit isolé : `project.py` importe encore l'ancien type — on commit à la fin
de la tranche, Task 8, quand tout est vert.)*

---

## Task 2 : Réduire `Project` à l'identité minimale

**Files:**
- Modify: `src/fahmi2/domain/project.py`
- Test: `tests/unit/domain/test_project.py`

- [ ] **Step 1 : Réécrire `project.py`** (supprimer `ParallelismConfig`/`ProjectSettings`,
  désormais dans `generation.py` ; `Project` minimal)

```python
# src/fahmi2/domain/project.py
"""Entité ``Project`` — identité minimale (nom + emplacement) + réglages par fonctionnalité.

Un ``Project`` ne porte que son **nom** et son **emplacement** (``workspace_folder``,
fixé à la création et immuable). Les paramètres métier vivent dans des blocs de
réglages dédiés par fonctionnalité — ici ``generation`` (cf. ``domain.generation``).
``generation`` vaut ``None`` tant que la fonctionnalité n'est pas configurée.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from fahmi2.domain.generation import GenerationSettings
from fahmi2.domain.ids import ProjectId, RunId


@dataclass(frozen=True)
class Project:
    """Projet utilisateur persistant avec son historique de runs.

    Attributes:
        id: Identifiant stable du projet.
        name: Nom utilisateur du projet.
        workspace_folder: Emplacement de travail (artefacts/sortie), immuable
            après création.
        created_at: Date de création.
        last_run_at: Date du dernier run terminé (``None`` si jamais lancé).
        runs: Historique des ULID de Run associés au projet.
        generation: Réglages de la fonctionnalité Génération, ou ``None`` tant
            qu'elle n'est pas configurée.
    """

    id: ProjectId
    name: str
    workspace_folder: Path
    created_at: datetime
    last_run_at: datetime | None = None
    runs: tuple[RunId, ...] = ()
    generation: GenerationSettings | None = None
```

- [ ] **Step 2 : Mettre à jour `tests/unit/domain/test_project.py`**

Remplacer les tests qui validaient `ProjectSettings` (ils vivent désormais dans
`test_generation.py`) par des tests du `Project` minimal. Contenu cible :

```python
# tests/unit/domain/test_project.py
"""Tests de l'entité ``Project`` (identité minimale)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from fahmi2.domain.ids import ProjectId
from fahmi2.domain.project import Project


def test_project_minimal_defaults() -> None:
    project = Project(
        id=ProjectId.new(),
        name="Cours",
        workspace_folder=Path("./ws"),
        created_at=datetime.now(tz=UTC),
    )
    assert project.generation is None
    assert project.runs == ()
    assert project.last_run_at is None
```

- [ ] **Step 3 : Vérifier la cohérence d'import** (le reste casse encore — normal)

Run: `.venv\Scripts\python.exe -m pytest tests/unit/domain/test_project.py tests/unit/domain/test_generation.py -q`
Expected: PASS pour ces deux fichiers (les autres couches seront corrigées Tasks 3–7).

---

## Task 3 : Retyper `Run.settings_snapshot`

**Files:**
- Modify: `src/fahmi2/domain/run.py`
- Test: `tests/unit/domain/test_run.py`

- [ ] **Step 1 : Modifier l'import et le type dans `run.py`**

Remplacer l'import `from fahmi2.domain.project import ProjectSettings` par
`from fahmi2.domain.generation import GenerationSettings`, et le champ :

```python
    settings_snapshot: GenerationSettings
```

Mettre à jour la docstring de l'attribut (`Copie immuable des GenerationSettings à t0.`).

- [ ] **Step 2 : Adapter `tests/unit/domain/test_run.py`**

Remplacer toute construction `ProjectSettings(...)` / usage de `make_settings` par
`make_generation_settings` (fixture livrée en Task 7) ; `settings_snapshot=` reçoit un
`GenerationSettings`. (Si le test construisait un `Project`, utiliser `make_project`.)

- [ ] **Step 3 : (différé)** la suite complète passera en Task 8.

---

## Task 4 : Persistance — sérialisation v2 + migration lenient v1→v2

**Files:**
- Modify: `src/fahmi2/infra/storage/sqlite_state.py`
- Test: `tests/unit/infra/storage/test_sqlite_state.py`

- [ ] **Step 1 : Écrire d'abord le test de migration v1→v2 (échoue)**

Ajouter à `test_sqlite_state.py` :

```python
def test_loads_legacy_v1_project_blob(tmp_path, make_generation_settings) -> None:
    """Un blob v1 « à plat » (avec name/workspace_folder) se charge en Project v2."""
    import json
    from datetime import UTC, datetime

    from fahmi2.domain.ids import ProjectId
    from fahmi2.infra.storage.sqlite_state import SqliteState

    db = tmp_path / "legacy.db"
    state = SqliteState(db)
    pid = ProjectId.new()
    # Blob v1 = ancien ProjectSettings sérialisé à plat (avec name + workspace_folder).
    legacy_blob = json.dumps(
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
    state._get_connection().execute(  # noqa: SLF001 — test d'accès direct
        "INSERT INTO projects (id, name, created_at, settings_json, last_run_at) "
        "VALUES (?, ?, ?, ?, NULL)",
        (pid.value, "Ancien projet", datetime.now(tz=UTC).isoformat(), legacy_blob),
    )
    state._get_connection().commit()  # noqa: SLF001

    project = state.get_project(pid)
    assert project is not None
    assert project.name == "Ancien projet"
    assert project.workspace_folder.as_posix() == "D:/Cours/.fahmi2"
    assert project.generation is not None
    assert project.generation.input_folder.as_posix() == "D:/Cours"


def test_corrupt_project_blob_raises_storage_error(tmp_path) -> None:
    from datetime import UTC, datetime

    from fahmi2.core.errors.exceptions import StorageError
    from fahmi2.domain.ids import ProjectId
    from fahmi2.infra.storage.sqlite_state import SqliteState

    state = SqliteState(tmp_path / "corrupt.db")
    pid = ProjectId.new()
    state._get_connection().execute(  # noqa: SLF001
        "INSERT INTO projects (id, name, created_at, settings_json) VALUES (?, ?, ?, ?)",
        (pid.value, "x", datetime.now(tz=UTC).isoformat(), "{not json"),
    )
    state._get_connection().commit()  # noqa: SLF001
    with pytest.raises(StorageError, match="STORAGE.PROJECT_BLOB_INVALID"):
        state.get_project(pid)
```

- [ ] **Step 2 : Lancer (échoue : sérialisation v2 absente)**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/infra/storage/test_sqlite_state.py -q`
Expected: FAIL.

- [ ] **Step 3 : Réécrire la (dé)sérialisation dans `sqlite_state.py`**

Mettre à jour les imports (remplacer `ProjectSettings` par `GenerationSettings`,
`ParallelismConfig`, et importer `StorageError`, `Project`) :

```python
from fahmi2.core.errors.exceptions import StorageError
from fahmi2.domain.generation import GenerationSettings, ParallelismConfig
from fahmi2.domain.project import Project
```

Constantes (en tête, près de `_META_KEY_SCHEMA_VERSION`) :

```python
_BLOB_VERSION = 2
_BLOB_KEY_VERSION = "version"
_BLOB_KEY_WORKSPACE = "workspace_folder"
_BLOB_KEY_GENERATION = "generation"
_BLOB_KEY_PEDAGOGY = "pedagogy"
```

Remplacer `_serialize_settings` / `_deserialize_settings` par :

```python
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
        KeyError, ValueError: Si une clé requise manque ou est invalide
            (capturées par l'appelant et converties en ``StorageError``).
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
        _BLOB_KEY_PEDAGOGY: None,
    }
    return json.dumps(payload, ensure_ascii=False)


def _deserialize_project_blob(raw: str) -> tuple[Path, GenerationSettings | None]:
    """Désérialise le blob d'un projet (v2, ou v1 à plat migré à la lecture).

    Un blob **sans** clé ``version`` est traité comme v1 « à plat » : son
    contenu est l'ancien ``ProjectSettings``, dont on extrait l'emplacement et la
    génération (les clés ``name``/``workspace_folder`` sont ignorées par
    ``_deserialize_generation_settings``).

    Args:
        raw: Chaîne JSON stockée en base.

    Returns:
        ``(workspace_folder, generation_or_none)``.

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
    except (KeyError, ValueError) as exc:
        raise StorageError(
            code="STORAGE.PROJECT_BLOB_INVALID",
            user_message=(
                "Les réglages d'un projet sont incomplets ou invalides en base."
            ),
            severity=Severity.ERROR,
            technical_details={"missing_or_invalid": str(exc)},
        ) from exc
    return workspace_folder, generation


def _serialize_run_snapshot(gen: GenerationSettings) -> str:
    """Sérialise le snapshot de réglages d'un Run (= GenerationSettings).

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
```

- [ ] **Step 4 : Adapter `upsert_project`, les SELECT et `_row_to_project`**

`upsert_project` — la valeur du nom vient du champ `project.name`, le blob de
`_serialize_project_blob` :

```python
            (
                project.id.value,
                project.name,
                _datetime_to_iso(project.created_at),
                _serialize_project_blob(project),
                _datetime_to_iso(project.last_run_at) if project.last_run_at else None,
            ),
```

`get_project` et `list_projects` : ajouter `name` au SELECT.

```python
        # get_project
        "SELECT id, name, created_at, settings_json, last_run_at FROM projects WHERE id = ?",
        # list_projects
        "SELECT id, name, created_at, settings_json, last_run_at FROM projects ORDER BY created_at"
```

`_row_to_project` :

```python
    @staticmethod
    def _row_to_project(row: tuple[Any, ...]) -> Project:
        project_id, name, created_at_str, settings_json, last_run_at_str = row
        workspace_folder, generation = _deserialize_project_blob(settings_json)
        return Project(
            id=ProjectId(value=project_id),
            name=name,
            workspace_folder=workspace_folder,
            created_at=_datetime_from_iso(created_at_str),
            last_run_at=_datetime_from_iso_or_none(last_run_at_str),
            generation=generation,
        )
```

- [ ] **Step 5 : Adapter `upsert_run` et `_row_to_run` au snapshot**

Dans `upsert_run`, remplacer `_serialize_settings(run.settings_snapshot)` par
`_serialize_run_snapshot(run.settings_snapshot)`. Dans `_row_to_run`, remplacer
`settings_snapshot=_deserialize_settings(settings_json)` par
`settings_snapshot=_deserialize_run_snapshot(settings_json)`.

- [ ] **Step 6 : Lancer les tests de persistance (passent)**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/infra/storage/test_sqlite_state.py -q`
Expected: PASS (dont les 2 nouveaux tests de migration/robustesse). Adapter les tests
existants du fichier qui construisaient un `Project(settings=...)` → nouveau modèle
(`make_project`).

---

## Task 5 : Couche application (`ProjectService`, `RunOrchestrator`)

**Files:**
- Modify: `src/fahmi2/app/project_service.py`
- Modify: `src/fahmi2/app/run_orchestrator.py`
- Test: `tests/unit/app/test_project_service.py`, `tests/unit/app/test_run_orchestrator.py`

- [ ] **Step 1 : `ProjectService.create_project` — nouvelle signature**

```python
    def create_project(
        self,
        *,
        name: str,
        workspace_folder: Path,
        generation: GenerationSettings | None = None,
    ) -> Project:
        """Crée et persiste un nouveau ``Project`` (identité minimale).

        Args:
            name: Nom du projet.
            workspace_folder: Emplacement de travail (immuable après création).
            generation: Réglages de génération, ou ``None`` (à configurer plus tard).

        Returns:
            Le ``Project`` créé.
        """
        project = Project(
            id=ProjectId.new(),
            name=name,
            workspace_folder=workspace_folder,
            created_at=datetime.now(tz=UTC),
            generation=generation,
        )
        self._state.upsert_project(project)
        return project
```

Mettre à jour les imports du module (`from fahmi2.domain.generation import
GenerationSettings`, `from pathlib import Path`; retirer `ProjectSettings`).

- [ ] **Step 2 : `RunOrchestrator.create_run` — lire `project.generation`**

```python
    def create_run(self, project: Project) -> Run:
        if project.generation is None:
            raise ConfigError(
                code="CONFIG.GENERATION_NOT_CONFIGURED",
                user_message=(
                    "La génération n'est pas configurée pour ce projet. "
                    "Renseignez d'abord ses réglages."
                ),
                severity=Severity.ERROR,
            )
        videos = scan_input_folder(project.generation.input_folder)
        run = Run(
            id=RunId.new(),
            project_id=project.id,
            started_at=datetime.now(tz=UTC),
            status=RunStatus.CREATED,
            settings_snapshot=project.generation,
            videos=tuple(videos),
        )
        self._state.upsert_run(run)
        return run
```

Ajouter les imports `ConfigError`, `Severity`. Mettre à jour la docstring `Raises`.

- [ ] **Step 3 : `RunOrchestrator.execute` — reconstruire le `Project` minimal**

Remplacer le bloc de reconstruction (≈ lignes 150-160) par :

```python
        project = self._project_service.get_project(running_run.project_id)
        if project is not None:
            self._project_service.update_project(
                Project(
                    id=project.id,
                    name=project.name,
                    workspace_folder=project.workspace_folder,
                    created_at=project.created_at,
                    last_run_at=finished_run.finished_at,
                    runs=(*project.runs, finished_run.id),
                    generation=project.generation,
                )
            )
```

- [ ] **Step 4 : Adapter les tests app + lancer**

Dans `test_project_service.py` / `test_run_orchestrator.py` : remplacer
`create_project(settings)` par `create_project(name=..., workspace_folder=...,
generation=make_generation_settings())` ; pour un projet non configuré, tester que
`create_run` lève `ConfigError` (`CONFIG.GENERATION_NOT_CONFIGURED`).

Run: `.venv\Scripts\python.exe -m pytest tests/unit/app -q`
Expected: PASS.

---

## Task 6 : UI minimale — adapter les sites d'usage (sans changer l'UX)

> Objectif : l'app compile et se comporte **comme avant**, sur le nouveau modèle.
> Le passage aux onglets et la scission du dialogue viennent aux plans 02–03.

**Files (modify):**
- `src/fahmi2/ui/widgets/projects_sidebar.py`
- `src/fahmi2/ui/run_controller.py`
- `src/fahmi2/ui/dialogs/new_project_dialog.py`
- `src/fahmi2/ui/app_main.py`

- [ ] **Step 1 : `projects_sidebar.py:76`** — `project.settings.name` → `project.name`.

- [ ] **Step 2 : `run_controller.py` — sites énumérés**

  - L. 240 : `project.settings.name` → `project.name`.
  - L. 805 / 860 : `project.settings.stt_provider` → `project.generation.stt_provider`
    (ces chemins ne sont atteints qu'au lancement, où `generation` est non-`None` —
    cf. garde Step 4).
  - L. 376 : `cost_ceiling_usd=project.settings.cost_ceiling_usd` →
    `project.generation.cost_ceiling_usd`.
  - Dérivation du workspace dans `start_run` (construction du `PhaseContext`, ≈ L.480-494) :
    remplacer `run.settings_snapshot.workspace_folder` et `…/"output"` par un
    dérivé du projet courant :

```python
        from fahmi2.domain.generation import GENERATION_WORKSPACE_SUBDIR  # noqa: PLC0415

        gen_workspace = (
            self._current_project.workspace_folder / GENERATION_WORKSPACE_SUBDIR
        )
        ctx = PhaseContext(
            run=run,
            settings=run.settings_snapshot,
            workspace=gen_workspace,
            output_dir=gen_workspace / "output",
            ...
        )
```

  - `_current_output_dir` (L.642) :

```python
        from fahmi2.domain.generation import GENERATION_WORKSPACE_SUBDIR  # noqa: PLC0415

        return (
            self._current_project.workspace_folder
            / GENERATION_WORKSPACE_SUBDIR
            / "output"
        )
```

- [ ] **Step 3 : `estimate_cost` et `_show_preview_for_project`** — lire
  `project.generation` avec garde `None`

Dans `estimate_cost`, après récupération du projet courant :

```python
        if self._current_project.generation is None:
            QMessageBox.information(
                self._main_window,
                "Génération non configurée",
                "Configurez d'abord les réglages de génération de ce projet.",
            )
            return
        settings = self._current_project.generation
```

(et `scan_input_folder(settings.input_folder)` ensuite). Idem dans
`_show_preview_for_project` : si `project.generation is None`, appeler `self._reset_views()`
et `return` avant le scan ; sinon `scan_input_folder(project.generation.input_folder)`.
Mettre à jour `_refresh_views_with_last_run` pour ne pas planter si `generation is None`
(l'aperçu est simplement vide).

- [ ] **Step 4 : `_validate_keys`** — `project.settings.stt_provider` →
  `project.generation.stt_provider` (avec garde : si `generation is None`, message
  « Génération non configurée » et `return False`).

- [ ] **Step 5 : `new_project_dialog.py` — produire (nom, emplacement, GenerationSettings)**

Le dialogue reste un formulaire unique pour ce plan. Remplacer la construction de
`ProjectSettings` par un `GenerationSettings` + exposer nom et emplacement. On conserve
le comportement actuel : l'emplacement dérive du dossier vidéos.

```python
from fahmi2.domain.generation import GenerationSettings, ParallelismConfig

_WORKSPACE_SUBDIR_NAME = ".fahmi2"

# dans _on_accept(), à la place de self._result_settings = ProjectSettings(...) :
        self._result_name = name
        self._result_workspace = Path(input_folder_text) / _WORKSPACE_SUBDIR_NAME
        self._result_generation = GenerationSettings(
            input_folder=Path(input_folder_text),
            source_language=source_lang,
            output_languages=output_langs,
            style_preset=style,
            style_directives=directives,
            stt_provider=stt_provider,
            llm_model=llm_model,
            phases_config=self._phase_configs_widget.get_phase_configs(),
            cost_ceiling_usd=cost_ceiling,
            parallelism=ParallelismConfig(),
            delete_audio_after_stt=True,
        )
        self.accept()
```

Exposer trois accesseurs en remplacement de `get_settings()` :

```python
    def get_name(self) -> str | None:
        return getattr(self, "_result_name", None)

    def get_workspace_folder(self) -> Path | None:
        return getattr(self, "_result_workspace", None)

    def get_generation_settings(self) -> GenerationSettings | None:
        return getattr(self, "_result_generation", None)
```

Adapter `_populate_from_settings` pour recevoir un `GenerationSettings` + un nom + un
dossier d'entrée (mode édition) ; renommer le paramètre `initial_settings` →
`initial_generation` et ajouter `initial_name`/`initial_input_folder` selon besoin
(le champ « nom » et « dossier d'entrée » restent pré-remplis comme aujourd'hui).

- [ ] **Step 6 : `app_main.py` — flux création/édition + suppression**

  - L.133 : `project.settings.name` → `project.name`.
  - `_open_new_project` :

```python
        dialog = NewProjectDialog(hardware, parent=window)
        if dialog.exec() == NewProjectDialog.DialogCode.Accepted:
            name = dialog.get_name()
            workspace = dialog.get_workspace_folder()
            generation = dialog.get_generation_settings()
            if name and workspace and generation is not None:
                created = project_service.create_project(
                    name=name, workspace_folder=workspace, generation=generation
                )
                _refresh_sidebar()
                window.projects_sidebar.select_project(created.id)
```

  - `_edit_project` : reconstruire un `Project` minimal en préservant
    `id/created_at/last_run_at/runs` et en remplaçant `generation` :

```python
            updated = Project(
                id=project.id,
                name=dialog.get_name() or project.name,
                workspace_folder=project.workspace_folder,
                created_at=project.created_at,
                last_run_at=project.last_run_at,
                runs=project.runs,
                generation=dialog.get_generation_settings() or project.generation,
            )
            project_service.update_project(updated)
```

  Mettre à jour l'appel `NewProjectDialog(... initial_settings=project.settings)` →
  passer `initial_generation=project.generation`, `initial_name=project.name`,
  `initial_input_folder=project.generation.input_folder if project.generation else None`.

---

## Task 7 : Fixtures de test + balayage des sites

**Files:**
- Modify: `tests/conftest.py`
- Modify: les fichiers de tests listés ci-dessous.

- [ ] **Step 1 : Réécrire `conftest.py`**

```python
"""Pytest fixtures globales pour Fahmi2."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from fahmi2.domain.enums import (
    Language,
    LLMModel,
    PhaseId,
    SttProvider,
    StylePreset,
)
from fahmi2.domain.generation import GenerationSettings, ParallelismConfig
from fahmi2.domain.ids import ProjectId
from fahmi2.domain.phase import PhaseConfig
from fahmi2.domain.project import Project


@pytest.fixture
def make_generation_settings() -> Any:
    """Fabrique des ``GenerationSettings`` valides (kwargs de surcharge).

    Returns:
        Fonction renvoyant un ``GenerationSettings`` validé.
    """

    def _factory(**overrides: Any) -> GenerationSettings:
        base: dict[str, Any] = {
            "input_folder": Path("./input"),
            "source_language": Language.FR,
            "output_languages": (Language.FR,),
            "style_preset": StylePreset.STANDARD,
            "style_directives": "",
            "stt_provider": SttProvider.OPENAI_CLOUD,
            "llm_model": LLMModel.DEEPSEEK_V4_FLASH,
            "phases_config": {
                pid: PhaseConfig() for pid in PhaseId if pid is not PhaseId.STT
            },
            "cost_ceiling_usd": None,
            "parallelism": ParallelismConfig(),
            "delete_audio_after_stt": True,
        }
        base.update(overrides)
        return GenerationSettings(**base)

    return _factory


@pytest.fixture
def make_project(make_generation_settings: Any) -> Any:
    """Fabrique un ``Project`` minimal valide (kwargs de surcharge).

    Args:
        make_generation_settings: Fixture de fabrication des réglages génération.

    Returns:
        Fonction renvoyant un ``Project`` (avec ``generation`` par défaut).
    """

    def _factory(**overrides: Any) -> Project:
        base: dict[str, Any] = {
            "id": ProjectId.new(),
            "name": "Test Project",
            "workspace_folder": Path("./workspace"),
            "created_at": datetime.now(tz=UTC),
            "generation": make_generation_settings(),
        }
        base.update(overrides)
        return Project(**base)

    return _factory
```

- [ ] **Step 2 : Balayer les sites d'appel** (règles de transformation)

Pour chacun des fichiers ci-dessous : `make_settings` → `make_generation_settings` ;
toute construction `ProjectSettings(...)` → `GenerationSettings(...)` (retirer
`name`/`workspace_folder`) ; tout `Project(settings=...)` → `make_project(...)` ou
`Project(name=..., workspace_folder=..., generation=...)` ; `settings_snapshot=` reçoit
un `GenerationSettings`.

Fichiers à adapter :
`tests/unit/pipeline/handlers/test_phase_5_consolidation.py`,
`test_phase_6_translation.py`, `test_phase_3_reformulation.py`,
`test_phase_7_coherence.py`, `test_phase_4_structuration.py`,
`test_phase_2_glossary_reconciliation.py`, `test_phase_1_term_extraction.py`,
`test_phase_0_stt.py`, `tests/unit/pipeline/handlers/_helpers.py`,
`tests/unit/pipeline/test_engine.py`, `tests/e2e/test_full_pipeline.py`,
`tests/unit/app/test_run_orchestrator.py`, `tests/unit/app/test_glossary_reconciler.py`,
`tests/unit/app/test_project_service.py`, `tests/unit/ui/test_widgets_smoke.py`,
`tests/unit/ui/viewmodels/test_stats_strip.py`,
`tests/unit/ui/viewmodels/test_run_matrix.py`, `tests/unit/domain/test_run.py`,
`tests/unit/infra/storage/test_sqlite_state.py`.

> Note : les handlers lisent `ctx.settings.<champ>` — ces champs existent à l'identique
> dans `GenerationSettings`, donc les `_helpers.py` qui construisent un `PhaseContext`
> n'ont qu'à passer un `GenerationSettings` à `settings=`.

- [ ] **Step 3 : Suite complète**

Run: `.venv\Scripts\python.exe -m pytest -q`
Expected: PASS (toute la suite). Corriger les sites manqués jusqu'au vert.

---

## Task 8 : Passes qualité + commit de la tranche

- [ ] **Step 1 : Ruff**

Run: `.venv\Scripts\python.exe -m ruff check .`
Expected: `All checks passed!` (corriger sinon).

- [ ] **Step 2 : Mypy strict**

Run: `.venv\Scripts\python.exe -m mypy src tests`
Expected: `Success: no issues found`. Points de vigilance :
- `project.generation` est `GenerationSettings | None` → narrowing requis avant accès
  (gardes ajoutées en Task 6).
- Aucun import résiduel de `ProjectSettings` (mypy/ruff le signaleraient).

- [ ] **Step 3 : Lancer l'app en dev (fumée manuelle)**

Run: `.venv\Scripts\python.exe -m fahmi2.ui.app_main`
Vérifier : création d'un projet, aperçu des vidéos, estimation de coût, lancement d'un
run, « Ouvrir le dossier de sortie » pointe désormais sous `…\.fahmi2\generation\output`.

- [ ] **Step 4 : Commit**

```bash
git add -A
git commit -m "refactor(domain): scinder ProjectSettings en GenerationSettings + Project minimal (SP1/01)"
```

---

## Self-review (couverture spec SP1 — périmètre du plan 01)

- **§2.1 `GenerationSettings`** → Task 1. **§2.2 `Project` minimal + immuabilité
  emplacement** → Task 2 + Task 6 (emplacement non ré-exposé en édition). **§2.3 `Run`
  retypé** → Task 3. **§3 persistance v2 + migration lenient + robustesse** → Task 4.
  **§4 workspace `generation/`** → Task 6 (dérivation contexte + `output_dir`).
  **§7 tests (migration, robustesse, fixtures)** → Tasks 4 & 7. Le passage aux **onglets**
  (§5), la **vue master-detail** (§5.5) et le **stub pédagogique** (§5.4) sont **hors
  périmètre de ce plan** (plans 02–03).
- **État `generation = None`** couvert par les gardes UI (Task 6, steps 3-4) ; la
  création « minimale » sans dossier vidéos arrive au plan 03.
