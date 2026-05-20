# SP2 · Plan 01 — Domaine & persistance pédagogie

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline).
> **Design** : [`../specs/2026-05-20-sp2-sp3-supports-revision-design.md`](../specs/2026-05-20-sp2-sp3-supports-revision-design.md).
> Steps use checkbox (`- [ ]`) syntax.

**Goal:** Introduire les enums pédagogie + `PedagogySettings` + le champ
`Project.pedagogy`, et le persister dans le blob v2 (clé `pedagogy`), avec migration et
tests. **Aucun comportement existant changé.**

**Architecture:** `domain/pedagogy.py` (calqué sur `domain/generation.py`) ; réutilise
`PhaseConfig` pour la config LLM. Persistance : (dé)sérialisation de la clé `pedagogy`
dans `sqlite_state` (déjà réservée à `null` depuis SP1). Les **entités de support**
(`Flashcard`, `QcmItem`…) sont introduites avec leurs générateurs (SP2/02–03), YAGNI.

**Rappels directives :** pas de magic value (constantes), docstrings Google, réutiliser
les patterns (`GenerationSettings`), DRY/KISS/SRP, `mypy --strict`.

---

## Task 1 : Enums pédagogie

**Files:** Modify `src/fahmi2/domain/enums.py` ; Test `tests/unit/domain/test_enums_pedagogy.py`

- [ ] **Step 1 : Test (échoue)**

```python
# tests/unit/domain/test_enums_pedagogy.py
"""Tests des enums de la fonctionnalité pédagogique."""

from __future__ import annotations

from fahmi2.domain.enums import (
    BloomObjective,
    ExportFormat,
    SupportDensity,
    SupportType,
    TargetAudience,
)


def test_support_type_has_nine_members() -> None:
    assert len(SupportType) == 9
    assert SupportType.FLASHCARDS_GLOSSARY in SupportType


def test_other_pedagogy_enums() -> None:
    assert BloomObjective.AUTO in BloomObjective
    assert TargetAudience.LICENCE in TargetAudience
    assert SupportDensity.STANDARD in SupportDensity
    assert ExportFormat.APKG in ExportFormat
```

- [ ] **Step 2 : Lancer** → FAIL (`ImportError`).

- [ ] **Step 3 : Ajouter les enums à la fin de `enums.py`**

```python
class SupportType(StrEnum):
    """Types de supports de révision générables."""

    FLASHCARDS_GLOSSARY = "flashcards_glossary"
    FLASHCARDS_CONCEPTS = "flashcards_concepts"
    QCM = "qcm"
    TRUE_FALSE = "true_false"
    CLOZE = "cloze"
    OPEN_QUESTIONS = "open_questions"
    REVISION_SHEET = "revision_sheet"
    KEY_POINTS = "key_points"
    MOCK_EXAM = "mock_exam"


class TargetAudience(StrEnum):
    """Public cible des supports (règle l'exigence et le registre)."""

    DISCOVERY = "discovery"
    HIGH_SCHOOL = "high_school"
    LICENCE = "licence"
    MASTER_EXPERT = "master_expert"


class BloomObjective(StrEnum):
    """Objectif cognitif (taxonomie de Bloom, regroupements simples)."""

    AUTO = "auto"
    RESTITUTE = "restitute"
    UNDERSTAND_APPLY = "understand_apply"
    ANALYZE_BEYOND = "analyze_beyond"


class SupportDensity(StrEnum):
    """Densité (volume) des supports générés."""

    LIGHT = "light"
    STANDARD = "standard"
    DENSE = "dense"


class ExportFormat(StrEnum):
    """Formats d'export des supports."""

    APKG = "apkg"
    MARKDOWN = "markdown"
    PDF = "pdf"
```

- [ ] **Step 4 : Lancer** → PASS.

---

## Task 2 : `domain/pedagogy.py` (`PedagogySettings`)

**Files:** Create `src/fahmi2/domain/pedagogy.py` ; Test `tests/unit/domain/test_pedagogy.py`

- [ ] **Step 1 : Test (échoue)**

```python
# tests/unit/domain/test_pedagogy.py
"""Tests des invariants de ``PedagogySettings``."""

from __future__ import annotations

import pytest

from fahmi2.domain.enums import (
    BloomObjective,
    ExportFormat,
    Language,
    LLMModel,
    SupportDensity,
    SupportType,
    TargetAudience,
)
from fahmi2.domain.pedagogy import (
    EVALUATIVE_SUPPORTS,
    NO_LLM_SUPPORTS,
    PEDAGOGY_WORKSPACE_SUBDIR,
    PedagogySettings,
)
from fahmi2.domain.phase import PhaseConfig


def _make(**overrides: object) -> PedagogySettings:
    base: dict[str, object] = {
        "selected_supports": frozenset({SupportType.FLASHCARDS_GLOSSARY}),
        "separate_correction": frozenset(),
        "target_audience": TargetAudience.LICENCE,
        "bloom_objective": BloomObjective.AUTO,
        "pedagogy_directives": "",
        "languages": (Language.FR,),
        "density": SupportDensity.STANDARD,
        "llm_model": LLMModel.DEEPSEEK_V4_FLASH,
        "llm_config": PhaseConfig(),
        "cost_ceiling_usd": None,
        "export_formats": frozenset({ExportFormat.APKG}),
    }
    base.update(overrides)
    return PedagogySettings(**base)  # type: ignore[arg-type]


def test_constants() -> None:
    assert PEDAGOGY_WORKSPACE_SUBDIR == "pedagogy"
    assert SupportType.QCM in EVALUATIVE_SUPPORTS
    assert SupportType.FLASHCARDS_GLOSSARY in NO_LLM_SUPPORTS


def test_valid_construct() -> None:
    assert _make().target_audience is TargetAudience.LICENCE


def test_selected_supports_must_be_non_empty() -> None:
    with pytest.raises(ValueError, match="selected_supports"):
        _make(selected_supports=frozenset())


def test_languages_must_be_non_empty() -> None:
    with pytest.raises(ValueError, match="languages"):
        _make(languages=())


def test_separate_correction_subset_of_evaluative_selected() -> None:
    # QCM est évaluatif mais non sélectionné -> invalide.
    with pytest.raises(ValueError, match="separate_correction"):
        _make(
            selected_supports=frozenset({SupportType.FLASHCARDS_GLOSSARY}),
            separate_correction=frozenset({SupportType.QCM}),
        )


def test_negative_ceiling_rejected() -> None:
    with pytest.raises(ValueError, match="cost_ceiling_usd"):
        _make(cost_ceiling_usd=-1.0)
```

- [ ] **Step 2 : Lancer** → FAIL.

- [ ] **Step 3 : Créer `pedagogy.py`**

```python
# src/fahmi2/domain/pedagogy.py
"""Entité ``PedagogySettings`` (fonctionnalité Supports pédagogiques).

Regroupe les réglages de génération des supports de révision : types choisis,
corrigés séparés, public cible + objectif Bloom + directives, langues, densité,
modèle LLM + config, plafond de coût et formats d'export. Le nom et l'emplacement
restent portés par ``Project``.
"""

from __future__ import annotations

from dataclasses import dataclass

from fahmi2.domain.enums import (
    BloomObjective,
    ExportFormat,
    Language,
    LLMModel,
    SupportDensity,
    SupportType,
    TargetAudience,
)
from fahmi2.domain.phase import PhaseConfig

#: Sous-dossier du workspace dédié aux supports pédagogiques.
PEDAGOGY_WORKSPACE_SUBDIR = "pedagogy"

#: Supports évaluatifs (un corrigé séparé a du sens).
EVALUATIVE_SUPPORTS: frozenset[SupportType] = frozenset(
    {
        SupportType.QCM,
        SupportType.TRUE_FALSE,
        SupportType.CLOZE,
        SupportType.OPEN_QUESTIONS,
        SupportType.MOCK_EXAM,
    }
)

#: Supports produits sans appel LLM (depuis le glossaire).
NO_LLM_SUPPORTS: frozenset[SupportType] = frozenset(
    {SupportType.FLASHCARDS_GLOSSARY}
)


@dataclass(frozen=True)
class PedagogySettings:
    """Réglages de la fonctionnalité Supports pédagogiques.

    Attributes:
        selected_supports: Types de supports à générer (non vide).
        separate_correction: Supports évaluatifs pour lesquels produire un
            corrigé séparé (⊆ ``EVALUATIVE_SUPPORTS`` ∩ ``selected_supports``).
        target_audience: Public cible (exigence + registre).
        bloom_objective: Objectif cognitif Bloom (``AUTO`` = selon le public).
        pedagogy_directives: Directives pédagogiques libres.
        languages: Langues de génération (non vide).
        density: Densité (volume) des supports.
        llm_model: Modèle DeepSeek utilisé.
        llm_config: Config des appels LLM (thinking/effort/température/retries).
        cost_ceiling_usd: Plafond de coût (``None`` = pas de plafond).
        export_formats: Formats d'export demandés.
    """

    selected_supports: frozenset[SupportType]
    separate_correction: frozenset[SupportType]
    target_audience: TargetAudience
    bloom_objective: BloomObjective
    pedagogy_directives: str
    languages: tuple[Language, ...]
    density: SupportDensity
    llm_model: LLMModel
    llm_config: PhaseConfig
    cost_ceiling_usd: float | None
    export_formats: frozenset[ExportFormat]

    def __post_init__(self) -> None:
        if not self.selected_supports:
            raise ValueError("selected_supports must contain at least one support")
        if not self.languages:
            raise ValueError("languages must contain at least one language")
        allowed_correction = EVALUATIVE_SUPPORTS & self.selected_supports
        invalid = self.separate_correction - allowed_correction
        if invalid:
            raise ValueError(
                "separate_correction must be a subset of evaluative selected "
                f"supports. Invalid: {sorted(s.value for s in invalid)}"
            )
        if self.cost_ceiling_usd is not None and self.cost_ceiling_usd < 0:
            raise ValueError(
                f"cost_ceiling_usd must be >= 0 or None, got {self.cost_ceiling_usd}"
            )
```

- [ ] **Step 4 : Lancer** → PASS.

---

## Task 3 : `Project.pedagogy` + persistance

**Files:** Modify `src/fahmi2/domain/project.py`, `src/fahmi2/infra/storage/sqlite_state.py` ;
Test `tests/unit/infra/storage/test_sqlite_state.py`

- [ ] **Step 1 : Ajouter le champ à `Project`**

Dans `project.py` : importer `from fahmi2.domain.pedagogy import PedagogySettings` et
ajouter le champ après `generation` :

```python
    generation: GenerationSettings | None = None
    pedagogy: PedagogySettings | None = None
```

Compléter la docstring (`pedagogy: Réglages Supports pédagogiques, ou None`).

- [ ] **Step 2 : Sérialisation pédagogie dans `sqlite_state.py`**

Ajouter les imports (`PedagogySettings` + enums pédagogie) et deux helpers calqués sur
`_serialize_generation_settings` :

```python
def _serialize_pedagogy_settings(ped: PedagogySettings) -> dict[str, Any]:
    """Sérialise un ``PedagogySettings`` en dict JSON-compatible."""
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
    }


def _deserialize_pedagogy_settings(payload: dict[str, Any]) -> PedagogySettings:
    """Désérialise un ``PedagogySettings`` depuis un dict.

    Raises:
        KeyError, ValueError: Capturées par l'appelant (-> StorageError).
    """
    cfg = payload["llm_config"]
    return PedagogySettings(
        selected_supports=frozenset(
            SupportType(s) for s in payload["selected_supports"]
        ),
        separate_correction=frozenset(
            SupportType(s) for s in payload["separate_correction"]
        ),
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
        export_formats=frozenset(
            ExportFormat(f) for f in payload["export_formats"]
        ),
    )
```

- [ ] **Step 3 : Brancher dans le blob projet**

`_serialize_project_blob` : remplacer `_BLOB_KEY_PEDAGOGY: None,` par

```python
        _BLOB_KEY_PEDAGOGY: (
            _serialize_pedagogy_settings(project.pedagogy)
            if project.pedagogy is not None
            else None
        ),
```

`_deserialize_project_blob` : retour en **triplet** ``(workspace, generation, pedagogy)``.
Après le bloc `generation`, dans le même `try`, ajouter :

```python
        ped_payload = payload.get(_BLOB_KEY_PEDAGOGY)
        pedagogy = (
            _deserialize_pedagogy_settings(ped_payload)
            if ped_payload is not None
            else None
        )
```

et `return workspace_folder, generation, pedagogy`. (Mettre à jour la signature de
retour et la docstring.)

`_row_to_project` : déstructurer le triplet et passer `pedagogy=pedagogy` au `Project`.

```python
        workspace_folder, generation, pedagogy = _deserialize_project_blob(settings_json)
        return Project(
            id=ProjectId(value=project_id),
            name=name,
            workspace_folder=workspace_folder,
            created_at=_datetime_from_iso(created_at_str),
            last_run_at=_datetime_from_iso_or_none(last_run_at_str),
            generation=generation,
            pedagogy=pedagogy,
        )
```

> v1 (blob à plat) : `payload.get(_BLOB_KEY_PEDAGOGY)` renvoie `None` → `pedagogy=None`.
> Compatibilité préservée.

- [ ] **Step 4 : Tests persistance** (ajouter à `test_sqlite_state.py`)

```python
def test_pedagogy_settings_round_trip(
    tmp_path: Path, make_generation_settings: Any, make_pedagogy_settings: Any
) -> None:
    with SqliteState(tmp_path / "t.db") as state:
        project = Project(
            id=ProjectId.new(),
            name="P",
            workspace_folder=Path("./ws"),
            created_at=_ts(),
            generation=make_generation_settings(),
            pedagogy=make_pedagogy_settings(),
        )
        state.upsert_project(project)
        loaded = state.get_project(project.id)
        assert loaded is not None
        assert loaded.pedagogy is not None
        assert loaded.pedagogy.selected_supports == project.pedagogy.selected_supports


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
```

---

## Task 4 : Fixture `make_pedagogy_settings`

**Files:** Modify `tests/conftest.py`

- [ ] **Step 1 : Ajouter la fixture** (après `make_project`)

```python
@pytest.fixture
def make_pedagogy_settings() -> Any:
    """Fabrique des ``PedagogySettings`` valides (kwargs de surcharge)."""

    def _factory(**overrides: Any) -> PedagogySettings:
        base: dict[str, Any] = {
            "selected_supports": frozenset({SupportType.FLASHCARDS_GLOSSARY}),
            "separate_correction": frozenset(),
            "target_audience": TargetAudience.LICENCE,
            "bloom_objective": BloomObjective.AUTO,
            "pedagogy_directives": "",
            "languages": (Language.FR,),
            "density": SupportDensity.STANDARD,
            "llm_model": LLMModel.DEEPSEEK_V4_FLASH,
            "llm_config": PhaseConfig(),
            "cost_ceiling_usd": None,
            "export_formats": frozenset({ExportFormat.APKG}),
        }
        base.update(overrides)
        return PedagogySettings(**base)

    return _factory
```

Ajouter les imports nécessaires en tête de `conftest.py` (`BloomObjective`,
`ExportFormat`, `SupportDensity`, `SupportType`, `TargetAudience`, `PedagogySettings`).

---

## Task 5 : Vérifs + commit

- [ ] **Step 1** : `.venv\Scripts\python.exe -m pytest -q` → PASS.
- [ ] **Step 2** : `.venv\Scripts\python.exe -m ruff check .` → clean.
- [ ] **Step 3** : `.venv\Scripts\python.exe -m mypy src tests` → Success.
- [ ] **Step 4** : commit `feat(domain): PedagogySettings + enums pedagogie + persistance (SP2/01)`.

## Self-review

Couvre §3.1 (enums), §3.2 (PedagogySettings + plafond), §3.3 (Project.pedagogy +
persistance v2). Entités de support (§3.4) déférées à leurs tranches (SP2/02–03).
