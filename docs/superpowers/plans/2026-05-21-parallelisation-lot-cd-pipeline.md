# Parallélisation — Lot C (pipeline per-video) + Lot D (phases batch internes) — Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task (exécution **inline**, pas de subagents — préférence projet). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Paralléliser le pipeline de génération : les phases per-video (0 STT cloud, 1, 3, 4) sur les vidéos, et les phases batch internes (5 résumés, 6 traduction, 7 cohérence) sur leurs unités indépendantes, en câblant enfin `ParallelismConfig`.

**Architecture:** Le `PhaseHandler` déclare son parallélisme via `max_parallel_workers(ctx)` (défaut 1) ; le `PipelineEngine` remplace sa boucle per-video par `core/concurrency/map_bounded`. Les phases batch (6, 7, 5) parallélisent leurs boucles internes avec le même primitif. `ParallelismConfig` est lue par les handlers et exposée dans l'UI génération.

**Tech Stack:** Python 3.12, `concurrent.futures` (via `map_bounded`), PySide6, pytest, ruff, mypy --strict.

**Spec de référence:** [docs/superpowers/specs/2026-05-21-parallelisation-traitements-design.md](../specs/2026-05-21-parallelisation-traitements-design.md) (Lots C et D ; §5, §6, §8).

**Prérequis:** Lot A+B livrés (le primitif `core/concurrency/map_bounded` existe et est testé).

**Interpréteur:** `.venv\Scripts\python.exe`.

---

## Vue d'ensemble des fichiers

| Fichier | Rôle | Action |
|---|---|---|
| `src/fahmi2/pipeline/phase_handler.py` | `max_parallel_workers` (base, défaut 1) | Modifier |
| `src/fahmi2/pipeline/handlers/phase_0_stt.py` | Workers STT (cloud→pool, local→1) | Modifier |
| `src/fahmi2/pipeline/handlers/phase_1_term_extraction.py` | Workers LLM | Modifier |
| `src/fahmi2/pipeline/handlers/phase_3_reformulation.py` | Workers LLM | Modifier |
| `src/fahmi2/pipeline/handlers/phase_4_structuration.py` | Workers LLM | Modifier |
| `src/fahmi2/domain/generation.py` | Défaut `llm_workers=16` + bornes UI | Modifier |
| `src/fahmi2/pipeline/engine.py` | `_execute_phase` via `map_bounded` | Modifier |
| `src/fahmi2/ui/dialogs/generation_settings_view.py` | Saisie `stt_cloud_workers` / `llm_workers` | Modifier |
| `src/fahmi2/pipeline/handlers/phase_7_coherence.py` | `map_bounded` sur les langues | Modifier |
| `src/fahmi2/pipeline/handlers/phase_6_translation.py` | `map_bounded` sur (langue × doc) | Modifier |
| `src/fahmi2/pipeline/handlers/phase_5_consolidation.py` | `map_bounded` sur les résumés vidéo | Modifier |

---

## Task 1 : `max_parallel_workers` sur la base `PhaseHandler`

**Files:**
- Modify: `src/fahmi2/pipeline/phase_handler.py`
- Test: `tests/unit/pipeline/test_engine.py`

- [ ] **Step 1 : Écrire le test qui échoue**

Ajouter à `tests/unit/pipeline/test_engine.py` :

```python
def test_default_max_parallel_workers_is_one(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    ctx = _make_ctx(tmp_path, make_generation_settings, n_videos=1)
    handler = _CountingHandler(PhaseId.STT, is_per_video=True)
    assert handler.max_parallel_workers(ctx) == 1
```

- [ ] **Step 2 : Lancer le test pour vérifier qu'il échoue**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/pipeline/test_engine.py::test_default_max_parallel_workers_is_one -v`
Expected: FAIL — `AttributeError: '_CountingHandler' object has no attribute 'max_parallel_workers'`

- [ ] **Step 3 : Ajouter la méthode concrète à la base**

Dans `src/fahmi2/pipeline/phase_handler.py`, ajouter à la classe `PhaseHandler` (après la propriété `is_per_video`, avant `execute`) :

```python
    def max_parallel_workers(self, ctx: PhaseContext) -> int:
        """Nombre d'unités per-video à traiter en parallèle pour cette phase.

        Défaut : ``1`` (séquentiel). Les phases dont les unités per-video sont
        indépendantes et I/O-bound surchargent cette méthode pour autoriser un
        pool borné (cf. ``GenerationSettings.parallelism``). Ignoré pour les
        phases batch (``is_per_video`` faux).

        Args:
            ctx: Contexte d'exécution (accès aux réglages).

        Returns:
            Le nombre maximal de workers (>= 1).
        """
        del ctx
        return 1
```

- [ ] **Step 4 : Lancer le test (doit passer)**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/pipeline/test_engine.py::test_default_max_parallel_workers_is_one -v`
Expected: PASS

- [ ] **Step 5 : Qualité + commit**

```bash
.venv\Scripts\python.exe -m ruff check src/fahmi2/pipeline/phase_handler.py
.venv\Scripts\python.exe -m mypy src/fahmi2/pipeline/phase_handler.py
git add src/fahmi2/pipeline/phase_handler.py tests/unit/pipeline/test_engine.py
git commit -m "feat(pipeline): max_parallel_workers sur PhaseHandler (defaut 1)"
```

---

## Task 2 : Surcharges des handlers per-video (0, 1, 3, 4)

**Files:**
- Modify: `src/fahmi2/pipeline/handlers/phase_0_stt.py`, `phase_1_term_extraction.py`, `phase_3_reformulation.py`, `phase_4_structuration.py`
- Test: `tests/unit/pipeline/handlers/test_phase_0_stt.py`, `test_phase_1_term_extraction.py`, `test_phase_3_reformulation.py`, `test_phase_4_structuration.py`

- [ ] **Step 1 : Écrire les tests qui échouent**

Ajouter à `tests/unit/pipeline/handlers/test_phase_0_stt.py` (ajouter les imports `from fahmi2.domain.enums import SttProvider` et `from fahmi2.domain.generation import ParallelismConfig` s'ils manquent ; `build_phase_context` est déjà importé) :

```python
def test_phase0_workers_cloud_uses_pool(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    handler = Phase0SttHandler()
    ctx, _ = build_phase_context(
        tmp_path,
        make_generation_settings,
        settings_overrides={
            "stt_provider": SttProvider.OPENAI_CLOUD,
            "parallelism": ParallelismConfig(stt_cloud_workers=5),
        },
    )
    assert handler.max_parallel_workers(ctx) == 5


def test_phase0_workers_local_is_one(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    handler = Phase0SttHandler()
    ctx, _ = build_phase_context(
        tmp_path,
        make_generation_settings,
        settings_overrides={
            "stt_provider": SttProvider.FASTER_WHISPER_LOCAL,
            "parallelism": ParallelismConfig(stt_cloud_workers=5),
        },
    )
    assert handler.max_parallel_workers(ctx) == 1
```

Ajouter à chacun de `test_phase_1_term_extraction.py`, `test_phase_3_reformulation.py`, `test_phase_4_structuration.py` (avec `from fahmi2.domain.generation import ParallelismConfig` et le handler concerné déjà importé ; remplacer `<HandlerClass>` par `Phase1TermExtractionHandler` / `Phase3ReformulationHandler` / `Phase4StructurationHandler`) :

```python
def test_phase_workers_is_llm_pool(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    handler = <HandlerClass>()
    ctx, _ = build_phase_context(
        tmp_path,
        make_generation_settings,
        settings_overrides={"parallelism": ParallelismConfig(llm_workers=7)},
    )
    assert handler.max_parallel_workers(ctx) == 7
```

> Note : `Phase3ReformulationHandler` et `Phase4StructurationHandler` se construisent sans argument (le `top_k_glossary` a une valeur par défaut).

- [ ] **Step 2 : Lancer les tests pour vérifier qu'ils échouent**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/pipeline/handlers/test_phase_0_stt.py tests/unit/pipeline/handlers/test_phase_1_term_extraction.py tests/unit/pipeline/handlers/test_phase_3_reformulation.py tests/unit/pipeline/handlers/test_phase_4_structuration.py -k workers -v`
Expected: FAIL (les handlers héritent du défaut 1, donc 1 ≠ 5/7)

- [ ] **Step 3 : Surcharger phase 0 (STT)**

Dans `src/fahmi2/pipeline/handlers/phase_0_stt.py`, étendre l'import enums et ajouter la méthode dans `Phase0SttHandler` (après `is_per_video`) :

```python
from fahmi2.domain.enums import PhaseId, PhaseStatus, SttProvider
```

```python
    def max_parallel_workers(self, ctx: PhaseContext) -> int:
        """STT cloud : pool ``stt_cloud_workers`` ; STT local : 1 (GPU unique)."""
        if ctx.settings.stt_provider is SttProvider.OPENAI_CLOUD:
            return ctx.settings.parallelism.stt_cloud_workers
        return 1
```

- [ ] **Step 4 : Surcharger phases 1, 3, 4 (LLM)**

Dans chacun de `phase_1_term_extraction.py`, `phase_3_reformulation.py`, `phase_4_structuration.py`, ajouter dans la classe handler (après `is_per_video`) :

```python
    def max_parallel_workers(self, ctx: PhaseContext) -> int:
        """Parallélise les vidéos via le pool LLM configuré."""
        return ctx.settings.parallelism.llm_workers
```

- [ ] **Step 5 : Lancer les tests (doivent passer)**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/pipeline/handlers/ -k workers -v`
Expected: PASS (5 tests)

- [ ] **Step 6 : Qualité + commit**

```bash
.venv\Scripts\python.exe -m ruff check src/fahmi2/pipeline/handlers/ tests/unit/pipeline/handlers/
.venv\Scripts\python.exe -m mypy src/fahmi2/pipeline/handlers/
git add src/fahmi2/pipeline/handlers/ tests/unit/pipeline/handlers/
git commit -m "feat(pipeline): handlers 0/1/3/4 declarent leur pool de parallelisme"
```

---

## Task 3 : Défaut `llm_workers=16` + bornes UI

**Files:**
- Modify: `src/fahmi2/domain/generation.py`
- Test: `tests/unit/domain/test_generation.py`

- [ ] **Step 1 : Mettre à jour le test existant + ajouter les bornes**

Dans `tests/unit/domain/test_generation.py`, modifier l'assertion ligne ~83 (`assert parallelism.llm_workers == 4` → `16`) et ajouter un test des bornes :

```python
    assert parallelism.stt_cloud_workers == 3
    assert parallelism.llm_workers == 16
```

```python
def test_parallelism_ui_bounds_exposed() -> None:
    from fahmi2.domain.generation import (
        MAX_LLM_WORKERS,
        MAX_STT_CLOUD_WORKERS,
    )

    assert MAX_STT_CLOUD_WORKERS == 8
    assert MAX_LLM_WORKERS == 64
```

- [ ] **Step 2 : Lancer pour vérifier l'échec**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/domain/test_generation.py -k "parallelism" -v`
Expected: FAIL (llm_workers vaut encore 4 ; `MAX_*` non définis)

- [ ] **Step 3 : Porter le défaut et ajouter les bornes**

Dans `src/fahmi2/domain/generation.py`, modifier la constante et ajouter les bornes :

```python
_DEFAULT_STT_CLOUD_WORKERS = 3
_DEFAULT_LLM_WORKERS = 16

#: Bornes hautes proposées dans l'UI (la limite DeepSeek est par concurrence,
#: largement au-dessus ; OpenAI Whisper a de vraies limites RPM → STT plus bas).
MAX_STT_CLOUD_WORKERS = 8
MAX_LLM_WORKERS = 64
```

- [ ] **Step 4 : Lancer les tests (doivent passer)**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/domain/test_generation.py -v`
Expected: PASS

- [ ] **Step 5 : Qualité + commit**

```bash
.venv\Scripts\python.exe -m ruff check src/fahmi2/domain/generation.py tests/unit/domain/test_generation.py
.venv\Scripts\python.exe -m mypy src/fahmi2/domain/generation.py
git add src/fahmi2/domain/generation.py tests/unit/domain/test_generation.py
git commit -m "feat(domain): defaut llm_workers=16 + bornes UI de parallelisme"
```

---

## Task 4 : Câbler le moteur (`_execute_phase` via `map_bounded`)

**Files:**
- Modify: `src/fahmi2/pipeline/engine.py`
- Test: `tests/unit/pipeline/test_engine.py`

- [ ] **Step 1 : Étendre `_CountingHandler` + écrire le test parallèle**

Dans `tests/unit/pipeline/test_engine.py`, ajouter le paramètre `parallel_workers` au `__init__` de `_CountingHandler` (après `cost_per_call`) et l'override :

```python
        cost_per_call: float = 0.0,
        parallel_workers: int = 1,
    ) -> None:
```

```python
        self._cost_per_call = cost_per_call
        self._parallel_workers = parallel_workers
```

Et ajouter la méthode à `_CountingHandler` (après la propriété `is_per_video`) :

```python
    def max_parallel_workers(self, ctx: PhaseContext) -> int:
        del ctx
        return self._parallel_workers
```

Puis ajouter le test :

```python
def test_engine_parallel_per_video_processes_all_videos(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    ctx = _make_ctx(tmp_path, make_generation_settings, n_videos=6)
    handler = _CountingHandler(PhaseId.STT, is_per_video=True, parallel_workers=4)
    engine = _make_engine(handler)
    final = engine.execute(ctx)
    assert final is RunStatus.COMPLETED
    assert len(handler.calls) == 6
    assert set(handler.calls) == {v.video_id for v in ctx.run.videos}
    for video in ctx.run.videos:
        assert (
            ctx.state.get_phase_status(ctx.run.id, PhaseId.STT, video_id=video.video_id)
            is PhaseStatus.SUCCEEDED
        )
```

- [ ] **Step 2 : Lancer le test (passe déjà en séquentiel, mais valide la cible)**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/pipeline/test_engine.py::test_engine_parallel_per_video_processes_all_videos -v`
Expected: PASS (le moteur séquentiel traite déjà les 6 vidéos ; ce test garantit la non-régression du parallélisme)

- [ ] **Step 3 : Câbler `map_bounded` dans le moteur**

Dans `src/fahmi2/pipeline/engine.py`, ajouter l'import :

```python
from fahmi2.core.concurrency import map_bounded
```

Remplacer la méthode `_execute_phase` :

```python
    def _execute_phase(self, handler: PhaseHandler, ctx: PhaseContext) -> None:
        """Exécute une phase complète (toutes ses vidéos si per-video).

        Les phases per-video sont parallélisées via ``map_bounded`` borné par
        ``handler.max_parallel_workers(ctx)`` (le ``PauseToken`` est honoré entre
        soumissions ; une exception sur une vidéo interrompt la phase — fail-fast).

        Args:
            handler: Handler de la phase.
            ctx: Contexte.
        """
        if handler.is_per_video:
            workers = handler.max_parallel_workers(ctx)
            map_bounded(
                lambda video: self._execute_one(handler, ctx, video=video),
                ctx.run.videos,
                max_workers=workers,
                pause_token=ctx.pause_token,
            )
        else:
            self._execute_one(handler, ctx, video=None)
```

> Le `_raise_if_paused_or_cancelled(ctx)` qui précédait chaque vidéo est désormais assuré par `map_bounded` (consulte le `PauseToken` avant chaque soumission). Le check entre phases reste dans `execute`.

- [ ] **Step 4 : Lancer toute la suite du moteur (régression)**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/pipeline/test_engine.py -v`
Expected: PASS (tous les tests existants + le nouveau ; `test_engine_respects_cancel` valide qu'un token annulé avant exécution ne traite aucune vidéo)

- [ ] **Step 5 : Qualité + commit**

```bash
.venv\Scripts\python.exe -m ruff check src/fahmi2/pipeline/engine.py tests/unit/pipeline/test_engine.py
.venv\Scripts\python.exe -m mypy src/fahmi2/pipeline/engine.py
git add src/fahmi2/pipeline/engine.py tests/unit/pipeline/test_engine.py
git commit -m "feat(pipeline): execution per-video parallele via map_bounded"
```

---

## Task 5 : Exposer `ParallelismConfig` dans l'UI génération

**Files:**
- Modify: `src/fahmi2/ui/dialogs/generation_settings_view.py`
- Test: `tests/unit/ui/test_generation_settings_view.py`

- [ ] **Step 1 : Écrire le test qui échoue**

Ajouter à `tests/unit/ui/test_generation_settings_view.py` (ajouter en tête `from fahmi2.domain.generation import ParallelismConfig`) :

```python
def test_parallelism_round_trips(
    qtbot: QtBot, make_generation_settings: Any
) -> None:
    gen = make_generation_settings(
        parallelism=ParallelismConfig(stt_cloud_workers=5, llm_workers=20)
    )
    view = GenerationSettingsView(_HW, initial=gen)
    qtbot.addWidget(view)
    view._on_accept()  # noqa: SLF001
    result = view.get_generation_settings()
    assert result is not None
    assert result.parallelism.stt_cloud_workers == 5
    assert result.parallelism.llm_workers == 20
```

- [ ] **Step 2 : Lancer le test pour vérifier qu'il échoue**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/ui/test_generation_settings_view.py::test_parallelism_round_trips -v`
Expected: FAIL (la vue fige `ParallelismConfig()` → 3/16, ≠ 5/20)

- [ ] **Step 3 : Ajouter les widgets et le câblage**

Dans `src/fahmi2/ui/dialogs/generation_settings_view.py` :

Imports — ajouter `QSpinBox` à l'import PySide6 et les bornes du domaine :

```python
from fahmi2.domain.generation import (
    MAX_LLM_WORKERS,
    MAX_STT_CLOUD_WORKERS,
    GenerationSettings,
    ParallelismConfig,
)
```

Dans `_build_fields`, après `self._phase_configs_widget = PhaseConfigsWidget(self)` :

```python
        defaults = ParallelismConfig()
        self._stt_workers_input = QSpinBox(self)
        self._stt_workers_input.setRange(1, MAX_STT_CLOUD_WORKERS)
        self._stt_workers_input.setValue(defaults.stt_cloud_workers)
        self._stt_workers_input.setToolTip(
            "Transcriptions cloud simultanées (sans effet en STT local : 1 GPU)."
        )
        self._llm_workers_input = QSpinBox(self)
        self._llm_workers_input.setRange(1, MAX_LLM_WORKERS)
        self._llm_workers_input.setValue(defaults.llm_workers)
        self._llm_workers_input.setToolTip(
            "Appels LLM simultanés (limite DeepSeek par concurrence, très haute)."
        )
```

Dans `_build_stt_page`, ajouter une ligne au `QFormLayout` (après le checkbox keep-audio) :

```python
        form.addRow("Transcriptions en parallèle :", self._stt_workers_input)
```

Dans `_build_model_page`, ajouter une ligne (après « Plafond budget ») :

```python
        form.addRow("Appels LLM en parallèle :", self._llm_workers_input)
```

Dans `_on_accept`, remplacer `parallelism=ParallelismConfig(),` :

```python
            parallelism=ParallelismConfig(
                stt_cloud_workers=self._stt_workers_input.value(),
                llm_workers=self._llm_workers_input.value(),
            ),
```

Dans `_populate`, après `self._cost_ceiling_input.setValue(...)` :

```python
        self._stt_workers_input.setValue(generation.parallelism.stt_cloud_workers)
        self._llm_workers_input.setValue(generation.parallelism.llm_workers)
```

- [ ] **Step 4 : Lancer les tests UI (régression incluse)**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/ui/test_generation_settings_view.py -v`
Expected: PASS

- [ ] **Step 5 : Qualité + commit**

```bash
.venv\Scripts\python.exe -m ruff check src/fahmi2/ui/dialogs/generation_settings_view.py tests/unit/ui/test_generation_settings_view.py
.venv\Scripts\python.exe -m mypy src/fahmi2/ui/dialogs/generation_settings_view.py
git add src/fahmi2/ui/dialogs/generation_settings_view.py tests/unit/ui/test_generation_settings_view.py
git commit -m "feat(ui): expose le parallelisme (STT cloud / LLM) en generation"
```

---

## Task 6 : Phase 7 (cohérence) parallèle sur les langues

**Files:**
- Modify: `src/fahmi2/pipeline/handlers/phase_7_coherence.py`
- Test: `tests/unit/pipeline/handlers/test_phase_7_coherence.py`

- [ ] **Step 1 : Écrire le test qui échoue**

Ajouter à `tests/unit/pipeline/handlers/test_phase_7_coherence.py` (réutiliser les imports/helpers du fichier ; `_llm`/`_seed*` selon les patterns existants). Le test vérifie que les deux langues sont réécrites :

```python
def test_coherence_parallel_two_languages(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    from fahmi2.domain.generation import (
        ParallelismConfig,
        consolidated_doc_filename,
    )

    ctx, _ = build_phase_context(
        tmp_path,
        make_generation_settings,
        llm_response=LLMResponse(
            content="Cohérent.",
            thinking_content=None,
            prompt_tokens=10,
            completion_tokens=10,
            cached_prompt_tokens=0,
            cost_usd=0.002,
        ),
        settings_overrides={
            "output_languages": (Language.FR, Language.EN),
            "parallelism": ParallelismConfig(llm_workers=4),
        },
    )
    for lang in (Language.FR, Language.EN):
        (ctx.output_dir).mkdir(parents=True, exist_ok=True)
        (ctx.output_dir / consolidated_doc_filename(lang)).write_text(
            "# Doc\n\n## Intro\n\nTexte.", encoding="utf-8"
        )
    (ctx.workspace).mkdir(parents=True, exist_ok=True)
    (ctx.workspace / "glossary_master.json").write_text(
        '{"terms": []}', encoding="utf-8"
    )

    result = Phase7CoherenceHandler().execute(ctx, video=None)
    assert result.status is PhaseStatus.SUCCEEDED
    for lang in (Language.FR, Language.EN):
        assert (ctx.output_dir / consolidated_doc_filename(lang)).read_text(
            encoding="utf-8"
        ) == "Cohérent."
```

- [ ] **Step 2 : Lancer le test (avant refactor)**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/pipeline/handlers/test_phase_7_coherence.py::test_coherence_parallel_two_languages -v`
Expected: PASS (le code séquentiel produit déjà les 2 fichiers ; ce test garantit la non-régression après parallélisation)

- [ ] **Step 3 : Paralléliser la boucle des langues**

Dans `src/fahmi2/pipeline/handlers/phase_7_coherence.py`, ajouter l'import :

```python
from fahmi2.core.concurrency import map_bounded
```

Remplacer la boucle `for target in ctx.settings.output_languages:` du `execute` :

```python
        glossary_terms = _load_glossary_terms(ctx.workspace)
        costs = map_bounded(
            lambda target: self._run_for_language(ctx, target, glossary_terms),
            ctx.settings.output_languages,
            max_workers=ctx.settings.parallelism.llm_workers,
            pause_token=ctx.pause_token,
        )
        total_cost = sum(costs)
```

(Supprimer l'ancienne initialisation `total_cost = 0.0` + boucle ; `_run_for_language` est inchangé et retourne déjà le coût.)

- [ ] **Step 4 : Lancer les tests du handler (régression)**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/pipeline/handlers/test_phase_7_coherence.py -v`
Expected: PASS

- [ ] **Step 5 : Qualité + commit**

```bash
.venv\Scripts\python.exe -m ruff check src/fahmi2/pipeline/handlers/phase_7_coherence.py tests/unit/pipeline/handlers/test_phase_7_coherence.py
.venv\Scripts\python.exe -m mypy src/fahmi2/pipeline/handlers/phase_7_coherence.py
git add src/fahmi2/pipeline/handlers/phase_7_coherence.py tests/unit/pipeline/handlers/test_phase_7_coherence.py
git commit -m "feat(pipeline): phase 7 coherence parallele sur les langues"
```

---

## Task 7 : Phase 6 (traduction) parallèle sur (langue × document)

**Files:**
- Modify: `src/fahmi2/pipeline/handlers/phase_6_translation.py`
- Test: `tests/unit/pipeline/handlers/test_phase_6_translation.py`

**Conception** : on **collecte** les traductions LLM à effectuer (uniquement langues ≠ source), on exécute les **copies** (langue source) directement, puis on lance les traductions via `map_bounded`. Chaque tâche traduit un document et l'écrit.

- [ ] **Step 1 : Écrire le test qui échoue**

Ajouter à `tests/unit/pipeline/handlers/test_phase_6_translation.py` (réutiliser `_seed_workspace`, `_llm`, `build_phase_context` du fichier) :

```python
def test_translation_parallel_non_source_language(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    from fahmi2.domain.generation import (
        ParallelismConfig,
        consolidated_doc_filename,
    )

    video = VideoExecution(video_id=VideoId.new(), source_path=tmp_path / "v.mp4")
    ctx, _ = build_phase_context(
        tmp_path,
        make_generation_settings,
        llm_response=_llm("Translated."),
        videos=(video,),
        settings_overrides={
            "source_language": Language.FR,
            "output_languages": (Language.FR, Language.EN),
            "parallelism": ParallelismConfig(llm_workers=4),
        },
    )
    _seed_workspace(ctx.workspace, videos=(video,))

    result = Phase6TranslationHandler().execute(ctx, video=None)
    assert result.status is PhaseStatus.SUCCEEDED
    # FR (source) : copie ; EN : traduction LLM.
    assert (ctx.output_dir / consolidated_doc_filename(Language.EN)).read_text(
        encoding="utf-8"
    ) == "Translated."
    assert (
        ctx.output_dir / "per-video" / "en" / f"{video.video_id.value}.md"
    ).read_text(encoding="utf-8") == "Translated."
    assert result.cost_usd > 0
```

- [ ] **Step 2 : Lancer le test (avant refactor)**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/pipeline/handlers/test_phase_6_translation.py::test_translation_parallel_non_source_language -v`
Expected: PASS (le code séquentiel produit déjà ces fichiers ; garantit la non-régression)

- [ ] **Step 3 : Refactorer en collecte de tâches + exécution parallèle**

Dans `src/fahmi2/pipeline/handlers/phase_6_translation.py`, ajouter les imports :

```python
from dataclasses import dataclass

from fahmi2.core.concurrency import map_bounded
```

Ajouter un type de tâche (après les constantes de module) :

```python
@dataclass(frozen=True)
class _TranslationTask:
    """Une traduction LLM à effectuer : source → fichier cible."""

    source_markdown: str
    target: Language
    target_path: Path
```

Remplacer la boucle `for target in ctx.settings.output_languages:` du `execute` (la partie qui appelle `_produce_for_language` et somme les coûts) par une collecte + exécution parallèle :

```python
        tasks: list[_TranslationTask] = []
        for target in ctx.settings.output_languages:
            self._collect_for_language(
                ctx,
                target=target,
                consolidated_master_md=consolidated_master,
                glossary_master_payload=glossary_master,
                per_video_structured=per_video_structured,
                tasks=tasks,
            )
        costs = map_bounded(
            lambda task: self._run_translation(ctx, task, glossary_master),
            tasks,
            max_workers=ctx.settings.parallelism.llm_workers,
            pause_token=ctx.pause_token,
        )
        total_cost = sum(costs)
```

Remplacer la méthode `_produce_for_language` par `_collect_for_language` (mêmes écritures pour la langue source — copies directes ; collecte des traductions sinon) :

```python
    def _collect_for_language(
        self,
        ctx: PhaseContext,
        *,
        target: Language,
        consolidated_master_md: str,
        glossary_master_payload: dict[str, Any],
        per_video_structured: dict[str, str],
        tasks: list[_TranslationTask],
    ) -> None:
        """Écrit les copies (langue source) et empile les traductions (sinon).

        Args:
            ctx: Contexte.
            target: Langue cible.
            consolidated_master_md: Document consolidé source.
            glossary_master_payload: Glossaire JSON master.
            per_video_structured: Mapping ``video_id -> markdown structuré``.
            tasks: Liste de tâches de traduction à compléter (effet de bord).
        """
        is_source = target is ctx.settings.source_language

        for video_id, structured_md in per_video_structured.items():
            target_path = (
                ctx.output_dir
                / _PER_VIDEO_OUTPUT_SUBDIR
                / target.value
                / f"{video_id}.md"
            )
            if is_source:
                ctx.artifacts.write_text_atomic(target_path, structured_md)
            else:
                tasks.append(
                    _TranslationTask(structured_md, target, target_path)
                )

        consolidated_target = ctx.output_dir / consolidated_doc_filename(target)
        if is_source:
            ctx.artifacts.write_text_atomic(
                consolidated_target, consolidated_master_md
            )
        else:
            tasks.append(
                _TranslationTask(consolidated_master_md, target, consolidated_target)
            )

        glossary_target = ctx.output_dir / f"glossary.{target.value}.md"
        glossary_md = _render_glossary_md(glossary_master_payload, target)
        if is_source:
            ctx.artifacts.write_text_atomic(glossary_target, glossary_md)
        else:
            tasks.append(_TranslationTask(glossary_md, target, glossary_target))

    def _run_translation(
        self,
        ctx: PhaseContext,
        task: _TranslationTask,
        glossary_master_payload: dict[str, Any],
    ) -> float:
        """Traduit une tâche via le LLM et écrit le fichier cible.

        Args:
            ctx: Contexte.
            task: Tâche de traduction.
            glossary_master_payload: Glossaire master JSON.

        Returns:
            Le coût LLM (USD).
        """
        translated, cost = self._translate(
            ctx, task.source_markdown, task.target, glossary_master_payload
        )
        ctx.artifacts.write_text_atomic(task.target_path, translated)
        return cost
```

(Conserver la méthode `_translate` inchangée. Supprimer l'ancienne `_produce_for_language`.)

- [ ] **Step 4 : Lancer les tests du handler (régression)**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/pipeline/handlers/test_phase_6_translation.py -v`
Expected: PASS

- [ ] **Step 5 : Qualité + commit**

```bash
.venv\Scripts\python.exe -m ruff check src/fahmi2/pipeline/handlers/phase_6_translation.py tests/unit/pipeline/handlers/test_phase_6_translation.py
.venv\Scripts\python.exe -m mypy src/fahmi2/pipeline/handlers/phase_6_translation.py
git add src/fahmi2/pipeline/handlers/phase_6_translation.py tests/unit/pipeline/handlers/test_phase_6_translation.py
git commit -m "feat(pipeline): phase 6 traduction parallele sur (langue x document)"
```

---

## Task 8 : Phase 5 (consolidation) — résumés vidéo parallèles

**Files:**
- Modify: `src/fahmi2/pipeline/handlers/phase_5_consolidation.py`
- Test: `tests/unit/pipeline/handlers/test_phase_5_consolidation.py`

**Conception** : la pré-consolidation produit un résumé LLM **indépendant par vidéo** ; on les parallélise via `map_bounded` (ordre préservé → assemblage déterministe). L'appel meta final reste séquentiel (barrière interne).

- [ ] **Step 1 : Écrire le test qui échoue**

Ajouter à `tests/unit/pipeline/handlers/test_phase_5_consolidation.py` un test qui vérifie que la consolidation produit le document pour plusieurs vidéos avec un pool (réutiliser les helpers `_seed`/`_llm` du fichier ; adapter les noms à ceux présents). Squelette :

```python
def test_consolidation_parallel_summaries(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    from fahmi2.domain.generation import ParallelismConfig

    videos = tuple(
        VideoExecution(video_id=VideoId.new(), source_path=tmp_path / f"v{i}.mp4")
        for i in range(3)
    )
    ctx, _ = build_phase_context(
        tmp_path,
        make_generation_settings,
        llm_response=LLMResponse(
            content='{"title": "T", "global_title": "G", "summary_markdown": "S", '
            '"introduction_markdown": "I", "conclusion_markdown": "C"}',
            thinking_content=None,
            prompt_tokens=10,
            completion_tokens=10,
            cached_prompt_tokens=0,
            cost_usd=0.003,
        ),
        videos=videos,
        settings_overrides={"parallelism": ParallelismConfig(llm_workers=4)},
    )
    structured_dir = ctx.workspace / "structured"
    structured_dir.mkdir(parents=True, exist_ok=True)
    for v in videos:
        (structured_dir / f"{v.video_id.value}.md").write_text(
            f"# Chapitre {v.video_id.value}\n\nContenu.", encoding="utf-8"
        )

    result = Phase5ConsolidationHandler().execute(ctx, video=None)
    assert result.status is PhaseStatus.SUCCEEDED
    assert (ctx.workspace / "consolidated_master.md").exists()
    assert result.cost_usd > 0
```

> Adapter `VideoExecution`/`VideoId`/`LLMResponse`/`Phase5ConsolidationHandler` aux imports du fichier (les ajouter si manquants).

- [ ] **Step 2 : Lancer le test (avant refactor)**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/pipeline/handlers/test_phase_5_consolidation.py::test_consolidation_parallel_summaries -v`
Expected: PASS (le code séquentiel produit déjà le document ; garantit la non-régression)

- [ ] **Step 3 : Paralléliser les résumés**

Dans `src/fahmi2/pipeline/handlers/phase_5_consolidation.py`, ajouter l'import :

```python
from fahmi2.core.concurrency import map_bounded
```

Remplacer la boucle de pré-consolidation dans `execute` :

```python
        structured_by_video = _load_all_structured(ctx.workspace, ctx.run.videos)

        summary_results = map_bounded(
            lambda kv: self._summarize_one(ctx, kv),
            list(structured_by_video.items()),
            max_workers=ctx.settings.parallelism.llm_workers,
            pause_token=ctx.pause_token,
        )
        summaries = [summary for summary, _ in summary_results]
        total_cost = sum(cost for _, cost in summary_results)

        meta, meta_cost = self._produce_meta(ctx, summaries)
        total_cost += meta_cost
```

Ajouter la méthode `_summarize_one` (juste après `_summarize_video`) :

```python
    def _summarize_one(
        self, ctx: PhaseContext, item: tuple[str, str]
    ) -> tuple[dict[str, Any], float]:
        """Résume une vidéo (clé = ``video_id``), pour exécution parallèle.

        Args:
            ctx: Contexte.
            item: Couple ``(video_id, structured_markdown)``.

        Returns:
            ``(summary_avec_video_id, cost_usd)``.
        """
        video_id, structured_md = item
        summary, cost = self._summarize_video(ctx, structured_md)
        summary["video_id"] = video_id
        return summary, cost
```

(Supprimer l'ancienne boucle `for video_id, structured_md in structured_by_video.items(): ...` ; `_summarize_video` et `_produce_meta` restent inchangés.)

- [ ] **Step 4 : Lancer les tests du handler (régression)**

Run: `.venv\Scripts\python.exe -m pytest tests/unit/pipeline/handlers/test_phase_5_consolidation.py -v`
Expected: PASS

- [ ] **Step 5 : Qualité + commit**

```bash
.venv\Scripts\python.exe -m ruff check src/fahmi2/pipeline/handlers/phase_5_consolidation.py tests/unit/pipeline/handlers/test_phase_5_consolidation.py
.venv\Scripts\python.exe -m mypy src/fahmi2/pipeline/handlers/phase_5_consolidation.py
git add src/fahmi2/pipeline/handlers/phase_5_consolidation.py tests/unit/pipeline/handlers/test_phase_5_consolidation.py
git commit -m "feat(pipeline): phase 5 resumes video parallelises (ordre preserve)"
```

---

## Task 9 : Vérification finale + documentation

**Files:** `CLAUDE.md`, `docs/04-parametrage.md`.

- [ ] **Step 1 : Suite complète**

Run: `.venv\Scripts\python.exe -m pytest`
Expected: PASS

- [ ] **Step 2 : Lint + typage globaux**

Run: `.venv\Scripts\python.exe -m ruff check .`
Run: `.venv\Scripts\python.exe -m mypy src tests`
Expected: `All checks passed!` / `Success: no issues found`

- [ ] **Step 3 : Documentation**

- `CLAUDE.md` : dans « Le pipeline en 8 phases » ou « Mécanismes transverses », noter que le moteur parallélise les phases per-video via `PhaseHandler.max_parallel_workers` (`ParallelismConfig` câblée : STT cloud = `stt_cloud_workers`, STT local = 1 ; phases 1/3/4 = `llm_workers`) et que les phases 5/6/7 parallélisent leurs boucles internes. Mentionner le défaut `llm_workers=16`.
- `docs/04-parametrage.md` : dans la section génération, mettre à jour les lignes `stt_cloud_workers` (défaut 3) et `llm_workers` (défaut **16**) pour indiquer qu'elles sont **désormais effectives** et réglables (Transcription / Modèle & coût).

- [ ] **Step 4 : Commit final**

```bash
git add CLAUDE.md docs
git commit -m "docs: parallelisation du pipeline (per-video + phases batch)"
```

---

## Self-review (couverture spec Lots C+D)

- **§5 `max_parallel_workers` + câblage moteur** → Tasks 1, 2, 4. ✓
- **§5 phase 0 (cloud→pool / local→1), phases 1/3/4 (llm_workers)** → Task 2. ✓
- **§6 phase 6 (langue × doc), phase 7 (langues), phase 5 (résumés)** → Tasks 7, 6, 8. ✓
- **§8 `ParallelismConfig` câblée + UI + défaut llm_workers=16** → Tasks 3, 5. ✓
- **§10.5 fail-fast / pause** → hérités de `map_bounded` (Lot A), exercés par `test_engine_respects_cancel`. ✓

**Barrières préservées** : le moteur reste « phase par phase » (Task 4) ; les phases batch 2 et 5 demeurent des points de synchronisation. Aucune modification du checkpoint SQLite.
