# SP2 · Plan 04 — Onglet pédagogique réel

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (inline, sans subagents).
> **Design** : [`../specs/2026-05-20-sp2-sp3-supports-revision-design.md`](../specs/2026-05-20-sp2-sp3-supports-revision-design.md) (§§8, 10).
> **Avancement** : [`./2026-05-20-sp2-sp3-00-avancement.md`](./2026-05-20-sp2-sp3-00-avancement.md).
> Steps use checkbox (`- [ ]`) syntax.

**Goal:** Remplacer le stub `PedagogyTab` par l'onglet **réel** : réglages
(master-detail Supports / Difficulté / Langues / Modèle & coût), cockpit (boutons
Réglages / Estimer / Générer / Pause / Reprendre / Annuler / Ouvrir le dossier),
vue de **progression** (supports × langues), **bandeau d'état** (génération requise /
prêt / à jour / périmé), **estimation de coût** pédagogie, et câblage `app_main`
(registre des 9 générateurs + `SupportsOrchestrator` + bridge events).

**Architecture:** Calquée sur l'onglet Génération (séparation **logique testable
sans Qt** / **Qt**) : `PedagogyController` (parallèle à `GenerationController`,
worker `QThread`, pause/cancel via `PauseToken`, bridge `PedagogyQtEventBus`),
`PedagogyTab` (parallèle à `GenerationTab`), `PedagogySettingsView` (dialogue
master-detail via `SettingsView`), `PedagogyProgressView` (table + bandeau).
Logique pure : `PedagogyCostEstimator` (app), `PedagogyProgressViewModel` (accumule
les events — la pédagogie n'a **pas** d'état DB), `PedagogyStateViewModel`
(fraîcheur depuis le manifeste). Helpers de **source** (`pedagogy/sources.py`) et
**heuristiques de coût** (`app/_cost_common.py`) extraits et réutilisés (DRY).

**Tech Stack:** PySide6, `pytest`/`pytest-qt`, `ruff`, `mypy --strict`.

**Rappels directives :** pas de magic value (constantes), docstrings Google + module,
**réutiliser** les patterns/briques existants (`SettingsView`, `ProjectHeaderBar`,
`LogsDock`, `FeatureTab`/`FeatureRegistry`, `QtEventBus`, `RunMatrixView`/viewmodels,
`get_pricing`, `build_default_support_registry`, `read_manifest`/`compute_settings_hash`),
DRY/YAGNI/KISS/SRP/SoC, composition > héritage, viewmodels testables **sans Qt**,
widgets en **smoke tests** `pytest-qt`. **Tout en français** (accents corrects).

**Décisions verrouillées pour ce lot :**
- **Réutiliser `ProjectHeaderBar`** pour le cockpit pédagogie (mêmes signaux :
  settings/estimate/start/pause/resume/cancel/open_output). Généraliser ses **3
  infobulles** spécifiques (réglages, estimer, dossier) en paramètres optionnels du
  constructeur (défauts = texte génération actuel) pour un libellé correct côté pédagogie.
- **`PedagogyQtEventBus`** = classe Qt dédiée `(QObject, EventBus[PedagogyEvent])`
  (parallèle à `QtEventBus`) — évite le risque `QObject` + `Generic` paramétré.
- **Progression sans DB** : la pédagogie n'a pas d'état SQLite ; `PedagogyProgressViewModel`
  **accumule les events** en mémoire (reset au lancement, `apply_event` ensuite).
- **Plafond de coût** : enforcement minimal dans `SupportsOrchestrator` (arrêt propre à
  la frontière sûre entre supports si `cost_ceiling_usd` dépassé → `RunStatus.PAUSED`).
- **Langues proposées** = langues pour lesquelles un `consolidated.{lang}.md` existe
  (sinon repli sur toutes les `Language`).

---

## File structure (vue d'ensemble)

**Créés :**

- `src/fahmi2/pedagogy/sources.py` — `consolidated_doc_path`, `source_mtime_ns`, `load_chapters`.
- `src/fahmi2/app/_cost_common.py` — `TOKENS_PER_WORD`, `thinking_output_multiplier` (extraits).
- `src/fahmi2/app/pedagogy_cost_estimator.py` — `PedagogyCostEstimator` + `PedagogyCostEstimation`.
- `src/fahmi2/ui/viewmodels/pedagogy_progress.py` — `PedagogyProgressViewModel` + snapshot/cellule.
- `src/fahmi2/ui/viewmodels/pedagogy_state.py` — `PedagogyState` + `PedagogyStateInfo` + viewmodel.
- `src/fahmi2/ui/widgets/pedagogy_progress_view.py` — `PedagogyProgressView` (bandeau + table).
- `src/fahmi2/ui/dialogs/pedagogy_settings_view.py` — `PedagogySettingsView` (master-detail).
- `src/fahmi2/ui/pedagogy_controller.py` — `PedagogyController` + `PedagogyQtEventBus` (ou dans qt_event_bus.py).
- Tests : `tests/unit/pedagogy/test_sources.py`, `tests/unit/app/test_pedagogy_cost_estimator.py`,
  `tests/unit/ui/viewmodels/test_pedagogy_progress.py`, `tests/unit/ui/viewmodels/test_pedagogy_state.py`,
  `tests/unit/ui/test_pedagogy_settings_view.py`, `tests/unit/ui/test_pedagogy_progress_view.py`,
  `tests/unit/ui/features/test_pedagogy_tab.py`, `tests/unit/ui/test_pedagogy_controller.py`.

**Modifiés :**

- `src/fahmi2/app/cost_estimator.py` — utiliser `_cost_common` (DRY, comportement inchangé).
- `src/fahmi2/app/supports_orchestrator.py` — réutiliser `sources.py` + enforcement plafond.
- `src/fahmi2/ui/qt_event_bus.py` — `PedagogyQtEventBus`.
- `src/fahmi2/ui/widgets/project_header_bar.py` — infobulles paramétrables (3).
- `src/fahmi2/ui/features/pedagogy_tab.py` — onglet réel (remplace le stub).
- `src/fahmi2/ui/app_main.py` — câblage pédagogie + fix `_edit_project` (préserver `pedagogy`).
- Docs : `docs/01-presentation-fonctionnelle.md`, `docs/04-parametrage.md`, `CHANGELOG.md`,
  doc d'avancement.

---

## Task 1 : Helpers de source (`pedagogy/sources.py`) + refactor orchestrateur

> DRY : le chemin du doc consolidé, son mtime et le parsing en chapitres sont
> aujourd'hui privés dans l'orchestrateur. On les extrait pour les réutiliser
> (orchestrateur + estimateur + viewmodel de fraîcheur).

**Files:** Create `src/fahmi2/pedagogy/sources.py` ;
Modify `src/fahmi2/app/supports_orchestrator.py` ; Test `tests/unit/pedagogy/test_sources.py`

- [ ] **Step 1 : Test (échoue)** — `tests/unit/pedagogy/test_sources.py` :

```python
"""Tests des helpers de source du document consolidé."""

from __future__ import annotations

from pathlib import Path

from fahmi2.domain.enums import Language
from fahmi2.infra.storage.fs_artifacts import FsArtifactStore
from fahmi2.pedagogy.sources import (
    consolidated_doc_path,
    load_chapters,
    source_mtime_ns,
)


def test_consolidated_doc_path(tmp_path: Path) -> None:
    assert consolidated_doc_path(tmp_path, Language.FR) == tmp_path / "consolidated.fr.md"


def test_source_mtime_none_when_missing(tmp_path: Path) -> None:
    assert source_mtime_ns(tmp_path, Language.FR) is None


def test_load_chapters_reads_and_parses(tmp_path: Path) -> None:
    FsArtifactStore().write_text_atomic(
        tmp_path / "consolidated.fr.md", "# Cours\n\n# 1. Bases\n\nContenu.\n"
    )
    chapters = load_chapters(tmp_path, Language.FR)
    assert [c.title for c in chapters] == ["Bases"]
    assert source_mtime_ns(tmp_path, Language.FR) is not None


def test_load_chapters_empty_when_missing(tmp_path: Path) -> None:
    assert load_chapters(tmp_path, Language.FR) == ()
```

- [ ] **Step 2 : Lancer** → FAIL.

- [ ] **Step 3 : Créer `pedagogy/sources.py`** :

```python
"""Accès au document consolidé source (chemin, mtime, chapitres).

Le générateur de supports lit le document consolidé produit par la Génération
sous ``<generation_output_dir>/consolidated.{lang}.md``. Ces helpers centralisent
le chemin, l'horodatage de fraîcheur et le parsing en chapitres (réutilisés par
l'orchestrateur, l'estimateur de coût et le calcul de fraîcheur de l'UI).
"""

from __future__ import annotations

from pathlib import Path

from fahmi2.domain.enums import Language
from fahmi2.domain.generation import consolidated_doc_filename
from fahmi2.pedagogy.chapters import Chapter, parse_chapters

_ENCODING_UTF8 = "utf-8"


def consolidated_doc_path(generation_output_dir: Path, language: Language) -> Path:
    """Chemin du document consolidé pour une langue.

    Args:
        generation_output_dir: Dossier des livrables de génération.
        language: Langue.

    Returns:
        Le chemin ``…/consolidated.{lang}.md``.
    """
    return generation_output_dir / consolidated_doc_filename(language)


def source_mtime_ns(generation_output_dir: Path, language: Language) -> int | None:
    """mtime (ns) du doc consolidé, ou ``None`` s'il est absent.

    Args:
        generation_output_dir: Dossier des livrables de génération.
        language: Langue.

    Returns:
        Le ``st_mtime_ns``, ou ``None``.
    """
    doc = consolidated_doc_path(generation_output_dir, language)
    if not doc.exists():
        return None
    return doc.stat().st_mtime_ns


def load_chapters(
    generation_output_dir: Path, language: Language
) -> tuple[Chapter, ...]:
    """Charge et parse les chapitres du doc consolidé (vide si absent).

    Args:
        generation_output_dir: Dossier des livrables de génération.
        language: Langue.

    Returns:
        Les chapitres (vide si le fichier n'existe pas).
    """
    doc = consolidated_doc_path(generation_output_dir, language)
    if not doc.exists():
        return ()
    return parse_chapters(doc.read_text(encoding=_ENCODING_UTF8))
```

- [ ] **Step 4 : Refactor `supports_orchestrator.py`** — remplacer les méthodes privées
  `_load_chapters` et `_source_mtime_ns` par les appels aux helpers
  (`from fahmi2.pedagogy.sources import load_chapters, source_mtime_ns`), retirer l'import
  désormais inutile de `consolidated_doc_filename`/`parse_chapters` si plus référencés.
  Dans `generate` : `source_mtime = source_mtime_ns(ctx.generation_output_dir, language)`
  et `chapters = load_chapters(ctx.generation_output_dir, language)`.

- [ ] **Step 5 : Lancer** → PASS (sources + non-régression orchestrateur).

Run: `.venv\Scripts\python.exe -m pytest tests/unit/pedagogy/test_sources.py tests/unit/app/test_supports_orchestrator.py -q`

---

## Task 2 : Heuristiques de coût partagées (`app/_cost_common.py`)

> DRY : `thinking_output_multiplier` + constantes de tokens sont dans
> `cost_estimator.py` (privé). On les extrait pour les partager avec
> `PedagogyCostEstimator`.

**Files:** Create `src/fahmi2/app/_cost_common.py` ; Modify `src/fahmi2/app/cost_estimator.py`

- [ ] **Step 1 : Créer `app/_cost_common.py`** :

```python
"""Heuristiques de coût partagées (génération + pédagogie).

Constantes de conversion oral → tokens et multiplicateur de tokens de sortie
quand le mode raisonnement (« thinking ») est actif. Les tokens de raisonnement
sont facturés au tarif output standard, d'où le surcoût.
"""

from __future__ import annotations

from fahmi2.domain.enums import ReasoningEffort
from fahmi2.domain.phase import PhaseConfig

#: Mots oraux par minute (hypothèse pour l'estimation depuis une durée audio).
WORDS_PER_MINUTE_ORAL = 150.0
#: Tokens par mot (hypothèse DeepSeek).
TOKENS_PER_WORD = 1.3

_THINKING_OUTPUT_MULTIPLIER_DEFAULT = 2.5
_THINKING_OUTPUT_MULTIPLIER_HIGH = 3.5
_THINKING_OUTPUT_MULTIPLIER_MAX = 6.0


def thinking_output_multiplier(config: PhaseConfig | None) -> float:
    """Multiplicateur des tokens de sortie selon le mode thinking.

    Args:
        config: Configuration LLM, ou ``None`` (estimation sans thinking).

    Returns:
        ``1.0`` si thinking désactivé, sinon 2.5 / 3.5 (HIGH) / 6 (MAX).
    """
    if config is None or not config.thinking_enabled:
        return 1.0
    if config.reasoning_effort is ReasoningEffort.MAX:
        return _THINKING_OUTPUT_MULTIPLIER_MAX
    if config.reasoning_effort is ReasoningEffort.HIGH:
        return _THINKING_OUTPUT_MULTIPLIER_HIGH
    return _THINKING_OUTPUT_MULTIPLIER_DEFAULT
```

- [ ] **Step 2 : Refactor `cost_estimator.py`** — supprimer `_thinking_output_multiplier`
  + ses 3 constantes + `_WORDS_PER_MINUTE_ORAL`/`_TOKENS_PER_WORD`, importer depuis
  `_cost_common` (`from fahmi2.app._cost_common import (TOKENS_PER_WORD, WORDS_PER_MINUTE_ORAL, thinking_output_multiplier)`),
  remplacer les usages (`_thinking_output_multiplier(...)` → `thinking_output_multiplier(...)`,
  `_WORDS_PER_MINUTE_ORAL` → `WORDS_PER_MINUTE_ORAL`, `_TOKENS_PER_WORD` → `TOKENS_PER_WORD`).

- [ ] **Step 3 : Lancer** → PASS (non-régression estimateur génération).

Run: `.venv\Scripts\python.exe -m pytest tests/unit/app/test_cost_estimator.py -q`

---

## Task 3 : `PedagogyCostEstimator`

> §10. Estime, par (support LLM × langue × chapitre), un coût heuristique :
> input ≈ taille du chapitre en tokens, output ≈ table par densité ; flashcards
> glossaire = 0 ; multiplicateur thinking via `_cost_common`. L'examen blanc
> consomme tout le document (somme des chapitres) en un appel.

**Files:** Create `src/fahmi2/app/pedagogy_cost_estimator.py` ;
Test `tests/unit/app/test_pedagogy_cost_estimator.py`

Schéma de coût (constantes centralisées en tête du module) :
- `input_tokens(chapter) = word_count(chapter.body_markdown) * TOKENS_PER_WORD`.
- `output_tokens_per_chapter = _DENSITY_OUTPUT_TOKENS[density]` (LIGHT/STANDARD/DENSE).
- Examen blanc : `input = somme des input_tokens des chapitres` (1 appel/langue),
  `output = _MOCK_EXAM_OUTPUT_TOKENS[density]`.
- Supports **par chapitre** LLM : pour chaque chapitre, `cost_for(input, output*thinking)`.
- `FLASHCARDS_GLOSSARY` ∈ `NO_LLM_SUPPORTS` → 0.
- thinking via `thinking_output_multiplier(pedagogy.llm_config)`.
- pricing via `get_pricing(str(pedagogy.llm_model))`.

- [ ] **Step 1 : Test (échoue)** :

```python
"""Tests de PedagogyCostEstimator."""

from __future__ import annotations

from typing import Any

from fahmi2.app.pedagogy_cost_estimator import PedagogyCostEstimator
from fahmi2.domain.enums import Language, SupportType
from fahmi2.pedagogy.chapters import Chapter


def _chapters(n: int) -> tuple[Chapter, ...]:
    return tuple(
        Chapter(index=i, title=f"C{i}", anchor=f"{i}-c", body_markdown="mot " * 200)
        for i in range(1, n + 1)
    )


def test_glossary_only_is_free(make_pedagogy_settings: Any) -> None:
    ped = make_pedagogy_settings(
        selected_supports=frozenset({SupportType.FLASHCARDS_GLOSSARY})
    )
    est = PedagogyCostEstimator().estimate(
        pedagogy=ped, chapters_by_language={Language.FR: _chapters(3)}
    )
    assert est.total_usd == 0.0


def test_llm_support_has_positive_cost(make_pedagogy_settings: Any) -> None:
    ped = make_pedagogy_settings(
        selected_supports=frozenset({SupportType.QCM}),
        separate_correction=frozenset(),
    )
    est = PedagogyCostEstimator().estimate(
        pedagogy=ped, chapters_by_language={Language.FR: _chapters(3)}
    )
    assert est.total_usd > 0.0
    assert est.per_support_usd[SupportType.QCM] > 0.0


def test_more_chapters_costs_more(make_pedagogy_settings: Any) -> None:
    ped = make_pedagogy_settings(selected_supports=frozenset({SupportType.QCM}))
    small = PedagogyCostEstimator().estimate(
        pedagogy=ped, chapters_by_language={Language.FR: _chapters(1)}
    )
    big = PedagogyCostEstimator().estimate(
        pedagogy=ped, chapters_by_language={Language.FR: _chapters(5)}
    )
    assert big.total_usd > small.total_usd
```

- [ ] **Step 2 : Lancer** → FAIL.

- [ ] **Step 3 : Créer `pedagogy_cost_estimator.py`** (signature + tables) :

```python
"""Estimation pré-génération du coût des supports pédagogiques (heuristique)."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from fahmi2.app._cost_common import TOKENS_PER_WORD, thinking_output_multiplier
from fahmi2.domain.enums import SupportDensity, SupportType
from fahmi2.domain.enums import Language
from fahmi2.domain.pedagogy import NO_LLM_SUPPORTS, PedagogySettings
from fahmi2.infra.llm._pricing import get_pricing
from fahmi2.pedagogy.chapters import Chapter

_DENSITY_OUTPUT_TOKENS: dict[SupportDensity, int] = {
    SupportDensity.LIGHT: 300,
    SupportDensity.STANDARD: 600,
    SupportDensity.DENSE: 1000,
}
_MOCK_EXAM_OUTPUT_TOKENS: dict[SupportDensity, int] = {
    SupportDensity.LIGHT: 800,
    SupportDensity.STANDARD: 1500,
    SupportDensity.DENSE: 2500,
}


@dataclass(frozen=True)
class PedagogyCostEstimation:
    """Estimation de coût des supports.

    Attributes:
        per_support_usd: Coût estimé par type de support.
        total_usd: Coût total estimé.
        chapters_total: Nombre total de chapitres (toutes langues).
    """

    per_support_usd: dict[SupportType, float]
    total_usd: float
    chapters_total: int


class PedagogyCostEstimator:
    """Estime le coût LLM des supports sélectionnés (ordre de grandeur)."""

    def estimate(
        self,
        *,
        pedagogy: PedagogySettings,
        chapters_by_language: Mapping[Language, tuple[Chapter, ...]],
    ) -> PedagogyCostEstimation:
        """Estime le coût total.

        Args:
            pedagogy: Réglages pédagogie.
            chapters_by_language: Chapitres parsés par langue.

        Returns:
            ``PedagogyCostEstimation``.
        """
        pricing = get_pricing(str(pedagogy.llm_model))
        thinking_mult = thinking_output_multiplier(pedagogy.llm_config)
        out_per_chapter = _DENSITY_OUTPUT_TOKENS[pedagogy.density]
        out_mock = _MOCK_EXAM_OUTPUT_TOKENS[pedagogy.density]

        per_support: dict[SupportType, float] = {}
        chapters_total = 0
        for language in pedagogy.languages:
            chapters = chapters_by_language.get(language, ())
            chapters_total += len(chapters)
            chapter_inputs = [
                int(len(c.body_markdown.split()) * TOKENS_PER_WORD) for c in chapters
            ]
            for support in pedagogy.selected_supports:
                cost = self._support_cost(
                    support,
                    chapter_inputs=chapter_inputs,
                    out_per_chapter=out_per_chapter,
                    out_mock=out_mock,
                    thinking_mult=thinking_mult,
                    pricing=pricing,
                )
                per_support[support] = per_support.get(support, 0.0) + cost
        return PedagogyCostEstimation(
            per_support_usd=per_support,
            total_usd=sum(per_support.values()),
            chapters_total=chapters_total,
        )
```

  + méthode privée `_support_cost(...)` :
  - `support in NO_LLM_SUPPORTS` → `0.0`.
  - `support is MOCK_EXAM` → `pricing.cost_for(prompt_tokens=sum(chapter_inputs), completion_tokens=int(out_mock*thinking_mult), cached_prompt_tokens=0)`.
  - sinon (par chapitre) → somme sur chapitres de `pricing.cost_for(input_i, int(out_per_chapter*thinking_mult), 0)`.

  > Importer `SupportType.MOCK_EXAM` ; regrouper les imports `Language`/`SupportDensity`/
  > `SupportType` en un seul `from fahmi2.domain.enums import (...)` (ruff I001).

- [ ] **Step 4 : Lancer** → PASS.

---

## Task 4 : Viewmodel de progression (`ui/viewmodels/pedagogy_progress.py`)

> La pédagogie n'a pas d'état SQLite : la progression est **accumulée depuis les
> events**. Testable sans Qt.

**Files:** Create `src/fahmi2/ui/viewmodels/pedagogy_progress.py` ;
Test `tests/unit/ui/viewmodels/test_pedagogy_progress.py`

Modèle :
```python
@dataclass(frozen=True)
class PedagogyProgressCell:
    support_type: SupportType
    language: Language
    status: PhaseStatus | None   # None = en attente
    cost_usd: float

@dataclass(frozen=True)
class PedagogyProgressSnapshot:
    cells: tuple[PedagogyProgressCell, ...]
    overall_status: RunStatus | None   # None tant que non terminé
    total_cost_usd: float

class PedagogyProgressViewModel:
    def reset(self, *, supports: tuple[SupportType, ...], languages: tuple[Language, ...]) -> None
    def apply_event(self, event: PedagogyEvent) -> None
    def snapshot(self) -> PedagogyProgressSnapshot
```
`reset` pré-remplit une cellule (status=None, cost=0) par (support, langue) dans
l'ordre **langue × support canonique** (utiliser `SupportGeneratorRegistry.canonical_order()`
filtré par `supports`). `apply_event` : `SupportFinished` → met à jour la cellule
(status, cost) ; `SupportGenerationFinished` → `overall_status` + `total_cost_usd` ;
`SupportStarted` → status `RUNNING` ; `SupportRetryAttempt`/`SupportGenerationStarted`
→ no-op sur la grille.

- [ ] **Step 1 : Test (échoue)** : reset(2 supports × 1 langue) → 2 cellules pending ;
  apply `SupportFinished(QCM, FR, SUCCEEDED, cost=0.1)` → cellule QCM/FR à SUCCEEDED,
  cost 0.1 ; apply `SupportGenerationFinished(COMPLETED, total=0.1)` → `overall_status`
  COMPLETED, `total_cost_usd` 0.1.
- [ ] **Step 2 : Lancer** → FAIL.
- [ ] **Step 3 : Créer le viewmodel** (clé de cellule = `(support_type, language)`,
  ordre déterministe via `canonical_order()`).
- [ ] **Step 4 : Lancer** → PASS.

---

## Task 5 : Viewmodel d'état/fraîcheur (`ui/viewmodels/pedagogy_state.py`)

> §4 (R19). Calcule l'état affiché dans le bandeau, depuis le projet + dernier run
> COMPLETED + docs consolidés + manifeste. Testable sans Qt.

**Files:** Create `src/fahmi2/ui/viewmodels/pedagogy_state.py` ;
Test `tests/unit/ui/viewmodels/test_pedagogy_state.py`

```python
class PedagogyState(StrEnum):
    NOT_CONFIGURED = "not_configured"
    GENERATION_REQUIRED = "generation_required"
    READY = "ready"
    UP_TO_DATE = "up_to_date"
    STALE = "stale"

@dataclass(frozen=True)
class PedagogyStateInfo:
    state: PedagogyState
    message: str         # texte FR du bandeau
    can_generate: bool

class PedagogyStateViewModel:
    def __init__(self, *, project_service: ProjectService) -> None
    def compute(self, project: Project) -> PedagogyStateInfo
```

Logique (constantes de messages centralisées) :
- `pedagogy is None` → `NOT_CONFIGURED` (« Configurez d'abord les réglages… »), can_generate=False.
- `project_service.get_last_completed_run(project.id) is None` → `GENERATION_REQUIRED`
  (« Lancez d'abord la Génération… »), can_generate=False.
- `generation_output_dir = workspace/GENERATION_WORKSPACE_SUBDIR/GENERATION_OUTPUT_SUBDIR` ;
  si un `consolidated.{lang}.md` manque pour une langue sélectionnée → `GENERATION_REQUIRED`.
- sinon : `manifest = read_manifest(pedagogy_dir)`, `settings_hash = compute_settings_hash(pedagogy)` ;
  pour chaque (support sélectionné × langue) : `json = artifact_json_path(...)`,
  `fresh = manifest.is_fresh(support, lang, settings_hash=…, source_mtime_ns=source_mtime_ns(...))`.
  - `any_generated = any(json.exists())`.
  - `any_stale = any(json.exists() and not fresh)`.
  - `not any_generated` → `READY` (« Prêt à générer. »), can_generate=True.
  - `any_stale` → `STALE` (« Supports périmés — régénérez. »), can_generate=True.
  - sinon → `UP_TO_DATE` (« Supports à jour. »), can_generate=True.

- [ ] **Step 1 : Tests (échouent)** : couvrir NOT_CONFIGURED, GENERATION_REQUIRED
  (pas de run COMPLETED), READY (run COMPLETED + doc présent, rien généré),
  UP_TO_DATE (artefact + manifeste frais), STALE (artefact + settings changés). Amorcer
  via `SqliteState` + `FsArtifactStore` (doc consolidé) + `write_manifest`.
- [ ] **Step 2 : Lancer** → FAIL.
- [ ] **Step 3 : Créer le viewmodel** (réutilise `read_manifest`, `compute_settings_hash`,
  `artifact_json_path`, `source_mtime_ns`, `consolidated_doc_path`).
- [ ] **Step 4 : Lancer** → PASS.

---

## Task 6 : Plafond de coût dans l'orchestrateur

> §10 : « le plafond interrompt proprement la génération à la prochaine frontière sûre ».

**Files:** Modify `src/fahmi2/app/supports_orchestrator.py` ;
Test `tests/unit/app/test_supports_orchestrator.py`

- [ ] **Step 1 : Test (échoue)** : un générateur factice qui retourne un artefact à
  `cost_usd=10.0` ; `pedagogy.cost_ceiling_usd=1.0` ; 2 supports sélectionnés →
  après le 1er (coût 10 > 1) la génération s'arrête, statut `PAUSED`, et le 2ᵉ support
  n'est pas généré (pas de cellule SUCCEEDED pour lui). (Note : le 1er support est
  généré et compté ; le plafond stoppe **avant** le suivant.)
- [ ] **Step 2 : Lancer** → FAIL.
- [ ] **Step 3 : Implémenter** dans la boucle de `generate`, **avant** de lancer un
  support (frontière sûre) : si `pedagogy.cost_ceiling_usd is not None and total_cost >=
  pedagogy.cost_ceiling_usd` → émettre `SupportGenerationFinished(PAUSED, total_cost)`
  et `return RunStatus.PAUSED`. (Constante de message de log facultative ; pas de magic.)
- [ ] **Step 4 : Lancer** → PASS.

---

## Task 7 : `PedagogySettingsView` (dialogue master-detail)

**Files:** Create `src/fahmi2/ui/dialogs/pedagogy_settings_view.py` ;
Test `tests/unit/ui/test_pedagogy_settings_view.py`

Dialogue calqué sur `GenerationSettingsView`, via `SettingsView`, 4 catégories :
- **Supports** : 9 cases (une par `SupportType`, libellés FR via une table de
  constantes) ; à côté des évaluatifs (`EVALUATIVE_SUPPORTS`), une case « corrigé séparé ».
- **Difficulté** : combo `TargetAudience` + combo `BloomObjective` + combo `SupportDensity`
  + `QTextEdit` directives.
- **Langues** : cases à cocher pour `available_languages` (passées au constructeur).
- **Modèle & coût** : combo `LLMModel` + case `thinking_enabled` + combo `ReasoningEffort`
  (+ « défaut serveur ») + `QDoubleSpinBox` température + `QDoubleSpinBox` plafond
  (`setSpecialValueText("Pas de plafond")`) + cases `ExportFormat`.

API : `PedagogySettingsView(parent=None, *, available_languages: tuple[Language, ...],
initial: PedagogySettings | None = None)` ; `get_pedagogy_settings() -> PedagogySettings | None`.
Le `_on_accept` valide via le `__post_init__` de `PedagogySettings` (capturer
`ValueError` → `QMessageBox.warning`, ne pas accepter). Construit `llm_config` =
`PhaseConfig(thinking_enabled, reasoning_effort, temperature)`.

> Libellés FR : **réutiliser** `pedagogy.labels` (`audience_label`, `bloom_label`,
> `density_label`) pour les combos ; une table locale `_SUPPORT_LABELS` pour les 9
> supports et `_EXPORT_LABELS` pour les formats (centralisées en tête).

- [ ] **Step 1 : Smoke tests** (`pytest-qt`, `qtbot`) : (a) construit sans `initial`
  → `get_pedagogy_settings()` après cocher 1 support + 1 langue renvoie un
  `PedagogySettings` valide ; (b) pré-rempli depuis un `initial` round-trip les
  sélections (supports/langues/audience/density). Suivre le style des smoke tests
  existants (`tests/unit/ui/test_widgets_smoke.py`).
- [ ] **Step 2 : Lancer** → FAIL.
- [ ] **Step 3 : Créer le dialogue.**
- [ ] **Step 4 : Lancer** → PASS.

---

## Task 8 : `PedagogyProgressView` (bandeau + table)

**Files:** Create `src/fahmi2/ui/widgets/pedagogy_progress_view.py` ;
Test `tests/unit/ui/test_pedagogy_progress_view.py`

Widget : un `QLabel` bandeau (objectName `pedagogyStateBanner`) au-dessus d'un
`QTableWidget` (colonnes : Support / Langue / Statut / Coût). API :
- `apply_snapshot(snapshot: PedagogyProgressSnapshot) -> None` (remplit la table ;
  libellés statut FR via table de constantes : None→« En attente », RUNNING→« En cours »,
  SUCCEEDED→« Généré », SKIPPED→« À jour », FAILED→« Échec »).
- `set_state(info: PedagogyStateInfo) -> None` (texte du bandeau + propriété QSS
  `state` pour la couleur).

- [ ] **Step 1 : Smoke test** : `apply_snapshot` avec 2 cellules → 2 lignes ;
  `set_state(PedagogyStateInfo(...))` → bandeau au bon texte.
- [ ] **Step 2 : Lancer** → FAIL.
- [ ] **Step 3 : Créer le widget.**
- [ ] **Step 4 : Lancer** → PASS.

---

## Task 9 : `PedagogyQtEventBus` + infobulles paramétrables de `ProjectHeaderBar`

**Files:** Modify `src/fahmi2/ui/qt_event_bus.py`, `src/fahmi2/ui/widgets/project_header_bar.py` ;
Tests : `tests/unit/ui/test_main_window_smoke.py` (déjà OK) — ajouter au besoin.

- [ ] **Step 1 : `PedagogyQtEventBus`** dans `qt_event_bus.py` :

```python
class PedagogyQtEventBus(QObject, EventBus[PedagogyEvent]):
    """``EventBus[PedagogyEvent]`` Qt-aware (parallèle à ``QtEventBus``)."""

    event_emitted = Signal(object)

    def __init__(self, parent: QObject | None = None) -> None:
        QObject.__init__(self, parent)
        EventBus.__init__(self)

    def publish(self, event: PedagogyEvent) -> None:
        super().publish(event)
        self.event_emitted.emit(event)
```
  (importer `PedagogyEvent`.)

- [ ] **Step 2 : `ProjectHeaderBar`** — rendre 3 infobulles paramétrables. Constructeur :
  `__init__(self, parent=None, *, settings_tooltip=_DEFAULT_SETTINGS_TOOLTIP,
  estimate_tooltip=_DEFAULT_ESTIMATE_TOOLTIP, open_output_tooltip=_DEFAULT_OPEN_OUTPUT_TOOLTIP)`.
  Extraire les textes actuels en constantes `_DEFAULT_*_TOOLTIP`. Appliquer les params
  aux `setToolTip`. Aucun appelant existant à changer (défauts = comportement actuel).

- [ ] **Step 3 : Lancer** (non-régression UI) :

Run: `.venv\Scripts\python.exe -m pytest tests/unit/ui -q`

---

## Task 10 : `PedagogyController`

**Files:** Create `src/fahmi2/ui/pedagogy_controller.py` ;
Test `tests/unit/ui/test_pedagogy_controller.py`

Calqué sur `GenerationController` (mais simplifié : pas de STT/ffmpeg, pas de matrice
DB). Dépendances : `header_bar: ProjectHeaderBar`, `progress_view: PedagogyProgressView`,
`logs_dock: LogsDock`, `window: QWidget`, `project_service: ProjectService`,
`secrets_service: SecretsService`, `state: SqliteState`, `app_paths: AppPaths`,
`registry: SupportGeneratorRegistry`.

Responsabilités :
- `on_project_selected(project_id)` : charge le projet, rafraîchit le bandeau d'état
  (`PedagogyStateViewModel`), active/désactive « Lancer » selon `can_generate`, active
  « Ouvrir le dossier » si `pedagogy/` existe.
- `open_pedagogy_settings()` : ouvre `PedagogySettingsView` (langues disponibles =
  langues ayant un `consolidated.{lang}.md`, sinon toutes), persiste `pedagogy` sur le
  projet (`update_project` en **préservant** `generation`), rafraîchit.
- `estimate_cost()` : charge les chapitres par langue (`load_chapters`), appelle
  `PedagogyCostEstimator`, affiche un `QMessageBox` (réutiliser le style du dialogue
  d'estimation génération ; comparer au plafond).
- `generate()` : valide clé DeepSeek + pédagogie configurée + état `can_generate` ;
  reset `PedagogyProgressViewModel` (supports × langues) ; worker `QThread` exécutant
  `SupportsOrchestrator.generate(project, pause_token, event_bus=PedagogyQtEventBus)` ;
  branche les events → `progress_view` + `logs_dock` (via `_pedagogy_event_to_log`).
- `pause/resume/cancel` via `PauseToken`.
- `open_folder()` : ouvre `pedagogy/` (réutiliser `_open_in_file_explorer` de
  `generation_controller`).

Construire l'orchestrateur :
```python
SupportsOrchestrator(
    state=self._state, project_service=self._project_service, registry=self._registry,
    artifacts=FsArtifactStore(), llm_provider=DeepSeekAdapter(api_key=…),
    prompts=PromptLoader(override_dir=self._app_paths.prompts_override_dir),
    retry_policy=RetryPolicy(),
)
```
Worker `_PedagogyWorker(QObject)` : signaux `finished(object)` / `failed(str)` ;
exécute `orchestrator.generate(project, pause_token=token, event_bus=bus)`.

`_pedagogy_event_to_log(event) -> LogEvent` : convertit chaque `PedagogyEvent` en
`LogEvent` (codes `PEDAGOGY_*`), parallèle à `_to_log_event`.

- [ ] **Step 1 : Tests** (parties testables sans worker réel) : `pytest-qt`.
  - `on_project_selected` sur un projet sans run COMPLETED → bandeau `GENERATION_REQUIRED`,
    « Lancer » désactivé.
  - `open_pedagogy_settings` (monkeypatch du dialogue pour renvoyer un `PedagogySettings`)
    → `project.pedagogy` persisté **et** `generation` préservé.
  - `_pedagogy_event_to_log(SupportFinished(... SUCCEEDED ...))` → `LogEvent` cohérent.
  > Réutiliser les fixtures Qt des smoke tests existants. Pour le worker, un test
  > d'intégration léger : `generate()` avec un registre `[FlashcardsGlossaryGenerator]`
  > (sans LLM) + glossaire amorcé + doc consolidé écrit, en exécutant le worker de
  > façon synchrone (ou en attendant le signal via `qtbot.waitSignal`).
- [ ] **Step 2 : Lancer** → FAIL.
- [ ] **Step 3 : Créer le contrôleur.**
- [ ] **Step 4 : Lancer** → PASS.

---

## Task 11 : `PedagogyTab` réel + câblage `app_main`

**Files:** Modify `src/fahmi2/ui/features/pedagogy_tab.py`, `src/fahmi2/ui/app_main.py` ;
Test `tests/unit/ui/features/test_pedagogy_tab.py`

- [ ] **Step 1 : `PedagogyTab` réel** (remplace le stub) — calqué sur `GenerationTab` :
  construit `ProjectHeaderBar` (avec infobulles pédagogie) + `PedagogyProgressView`,
  possède un `PedagogyController`, expose `feature_id=PEDAGOGY`, `title`, `widget`,
  `controller`, et `on_project_selected` délègue au contrôleur. Constructeur :
  `(*, logs_dock, window, project_service, secrets_service, state, app_paths, registry)`.

- [ ] **Step 2 : `app_main`** :
  - importer `build_default_support_registry`.
  - construire `pedagogy_registry = build_default_support_registry()`.
  - remplacer `pedagogy_tab = PedagogyTab(window)` par la construction réelle (DI).
  - garder une référence anti-GC (`window._pedagogy_tab = pedagogy_tab`).
  - **Fix régression** : dans `_edit_project`, ajouter `pedagogy=project.pedagogy` au
    `Project(...)` reconstruit (sinon l'édition du nom efface la pédagogie).
  - dans `_delete_project`, le test `was_current` ne concerne que la génération ;
    laisser tel quel (le PedagogyController n'a pas besoin de cleanup à la suppression,
    mais on peut appeler `pedagogy_tab.controller.clear_current_project()` si présent —
    optionnel, à n'ajouter que si la méthode existe).

- [ ] **Step 3 : Smoke test `test_pedagogy_tab.py`** : instancie le `PedagogyTab` réel
  avec des fakes/`tmp_path` (à la manière de `test_widgets_smoke.py`), vérifie
  `feature_id is FeatureId.PEDAGOGY`, `title`, `widget` non nul, et
  `on_project_selected(project_id)` ne lève pas.

- [ ] **Step 4 : Lancer** → PASS.

---

## Task 12 : Vérifications systématiques + docs + commit

- [ ] **Step 1** : `.venv\Scripts\python.exe -m pytest -q` → tout vert.
- [ ] **Step 2** : `.venv\Scripts\python.exe -m ruff check .` → clean.
- [ ] **Step 3** : `.venv\Scripts\python.exe -m mypy src tests` → Success.
- [ ] **Step 4 : Docs** : `docs/01-presentation-fonctionnelle.md` (décrire l'onglet
  Supports pédagogiques : réglages, génération, progression, fraîcheur, dossier
  `pedagogy/`), `docs/04-parametrage.md` (réglages pédagogie : supports, difficulté,
  langues, modèle & coût, plafond), `CHANGELOG.md`, doc d'avancement (SP2/04 → Fait ;
  ne reste que SP3/01, SP3/02, docs finales). Mettre à jour `README.md` si l'onglet y
  est listé.
- [ ] **Step 5 : Commit** :

```bash
git add -A
git commit -m "feat(pedagogy): onglet pedagogique reel + estimation + progression (SP2/04)"
```

---

## Self-review (avant de coder, et après)

**Couverture du design :**
- §8 réglages master-detail (Supports/Difficulté/Langues/Modèle & coût) → Task 7.
- §8 cockpit (Générer/Estimer/Ouvrir le dossier/progression/bandeau) → Tasks 8, 10, 11.
- §8 `PedagogyController` (worker QThread, pause/cancel, bridge `QtEventBus`) → Tasks 9, 10.
- §10 `PedagogyCostEstimator` + plafond → Tasks 3, 6.
- R19 fraîcheur (manifeste) → Task 5.
- Câblage `app_main` (registre + orchestrateur) → Task 11.

**Hors périmètre (tracé) :** exports `.apkg`/MD/PDF (SP3) ; docs finales + clôture
matrice chapeau (lot final). La **qualité réelle** des supports reste non testable en CI.

**Cohérence types/signatures :** `SupportsOrchestrator.generate(project, *, pause_token,
event_bus: EventBus[PedagogyEvent])` (inchangé) ; `PedagogyQtEventBus` est un
`EventBus[PedagogyEvent]` ; `PedagogyProgressViewModel.apply_event(PedagogyEvent)` ;
`PedagogyStateViewModel.compute(project) -> PedagogyStateInfo` ;
`PedagogyCostEstimator.estimate(*, pedagogy, chapters_by_language) -> PedagogyCostEstimation` ;
helpers `pedagogy.sources` réutilisés par orchestrateur + estimateur + état ;
`_cost_common.thinking_output_multiplier` réutilisé par les deux estimateurs.
