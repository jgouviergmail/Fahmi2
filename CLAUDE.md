# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Projet

Fahmi2 transforme un dossier de vidéos MP4 de cours oraux en documents Markdown
consolidés (reformulés, structurés, glossaire) via un pipeline STT + 7 phases
LLM DeepSeek. Application desktop Windows mono-utilisateur, PySide6, packagée en
`.zip` portable (installation double-clic, ffmpeg bundlé).

L'app est organisée en **onglets de fonctionnalité** (Génération ; Supports
pédagogiques — 8 types de supports de révision avec exports Anki/Markdown/PDF/HTML) :
un `Project` ne porte que son nom + son emplacement, les réglages métier vivant
par fonctionnalité (`GenerationSettings`, `PedagogySettings`).

## Langue et conventions de travail

- **Tout en français** : code comments, docstrings, messages utilisateur, logs,
  commits. Orthographe parfaite avec accents et diacritiques (jamais d'ASCII de
  substitution). Les identifiants de code restent dans leur forme d'origine.
- **Google Python Style Guide** : docstrings avec sections `Args`, `Returns`,
  `Raises` ; docstring de module sur chaque fichier.
- **Vérification systématique en fin de tâche** : `pytest`, `ruff check .`,
  `mypy src tests` doivent tous être verts avant de considérer un travail
  terminé. Repasser autant de fois que nécessaire jusqu'à zéro défaut.
- Entités domaine immuables (`@dataclass(frozen=True)`) + méthodes `with_*` pour
  les copies modifiées. Helpers privés `_method`, modules internes `_module.py`
  (`_base.py`, `_pricing.py`, `_schema.sql`, `_fakes.py`).

## Commandes

L'interpréteur du venv est `.venv\Scripts\python.exe` (Python 3.12 — **pas 3.13**,
contrainte `>=3.11,<3.13` dans `pyproject.toml`). En PowerShell on peut activer
via `.\.venv\Scripts\Activate.ps1`, mais préférer l'appel direct de l'exe.

```powershell
# Tests
.venv\Scripts\python.exe -m pytest                              # toute la suite
.venv\Scripts\python.exe -m pytest tests/unit/app               # une couche
.venv\Scripts\python.exe -m pytest tests/unit/app/test_x.py::test_name -v   # un seul test
.venv\Scripts\python.exe -m pytest --cov=src/fahmi2 --cov-report=term-missing

# Qualité (les deux doivent être propres)
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy src tests

# Lancer l'app en dev
.venv\Scripts\python.exe -m fahmi2.ui.app_main

# Build du .zip portable Windows (télécharge ffmpeg, valide, build PyInstaller)
.\packaging\build.ps1
.\packaging\make-portable-zip.ps1
```

Note Windows : git réécrit LF→CRLF (warnings attendus, sans conséquence). Le
fichier `packaging/fahmi2.spec` est `.gitignore` (`*.spec`) — modifier le `.spec`
pour bundler de nouvelles ressources ne sera pas versionné.

Dépendances supports pédagogiques à bundler dans le `.spec` au prochain build :
`genanki` embarque des fichiers de données (`apkg_schema.sql`, `apkg_col.anki2`)
→ `--collect-data genanki` (ou `collect_data_files('genanki')`) ; `markdown` et
`fpdf2` (+ `Pillow`, `fontTools`, `defusedxml`) sont des modules purs (ajouter en
`hiddenimports` si l'analyse PyInstaller les manque) ; le PDF utilise la police
**Arial système Windows** (rien à bundler). Détails dans `packaging/README.md`.

## Architecture en couches

Dépendances dirigées vers le bas (UI → app → pipeline/infra → domain/core).
`core` et `domain` n'importent ni Qt, ni HTTP, ni SQL.

- `core/` — transverse : `errors` (hiérarchie `Fahmi2Error` + `ErrorInfo`
  sérialisable + messages FR), `retry` (`RetryPolicy` + `with_retry`), `logging`
  (JSONL + redaction secrets), `config/paths` (`AppPaths` Windows + résolution
  ffmpeg bundlé runtime), `migrations`, `retrieval` (TF-IDF glossaire),
  `concurrency` (`map_bounded` : pool borné, fail-fast, ordre préservé, honore le
  `PauseToken` ; partagé pour paralléliser les appels LLM/STT I/O-bound), `ids`,
  `slugify` (`slugify_anchor` : ancre GFM **source unique** — sommaire du consolidé
  en génération, parseur de chapitres pédagogiques, ids de titres de l'export HTML).
- `domain/` — entités pures immuables (`Project` [identité minimale : nom +
  emplacement + réglages par fonctionnalité], `GenerationSettings`,
  `PedagogySettings`, `Run`, `VideoExecution`, `PhaseExecution`, `Term`,
  `Glossary`, entités de support dans `supports.py` : `Flashcard`, `QcmItem`,
  `TrueFalseItem`, `ClozeItem`, `OpenQuestion`, `RevisionSheet`, `KeyPoints`,
  `MockExam`, `SupportArtifact`), enums (génération + pédagogie : `SupportType`×8,
  `TargetAudience`, `BloomObjective`, `SupportDensity`, `ExportFormat`,
  `ReasoningEffort`), IDs ULID typés, et **machines d'état** (`state_machine.py`)
  qui valident les transitions Run et Phase.
- `pipeline/` — moteur d'exécution pur de la **génération** : `PipelineEngine`
  (checkpoint SQLite par phase + retry + events + pause/cancel), `PhaseRegistry`
  (ordre canonique des 8 phases), `PhaseHandler`/`PhaseContext` (DI),
  `EventBus` (générique), `PauseToken`, `handlers/phase_N_*.py` (un par phase).
- `pedagogy/` — moteur des **supports de révision** (calqué sur `pipeline/`, mais
  sans STT/SQLite) : `SupportGenerator` (ABC) + `SupportContext` (DI),
  `SupportGeneratorRegistry` + `build_default_support_registry`, `chapters`
  (parseur), `sources`, `events`, `manifest` (fraîcheur), `artifact_writer`/
  `artifact_reader`, `generators/` (`_base` per-chapitre + mixin évaluatif + 8
  générateurs LLM : flashcards concepts, QCM, vrai/faux, cloze, questions
  ouvertes, fiche, points clés, examen blanc), `labels`.
- `infra/` — adapters (ports/adapters) : `stt/` (FasterWhisper local + OpenAI
  cloud + fakes), `llm/` (DeepSeek + `_pricing` + `invocation` + fakes),
  `audio/ffmpeg_extractor` + `cloud_audio_preparer` (compression Opus +
  découpage aux silences : franchit la limite 25 Mo d'OpenAI Whisper, injecté
  dans l'adapter STT cloud), `anki/genanki_exporter` (`.apkg`),
  `export/markdown_pdf` (Markdown + PDF), `storage/sqlite_state` (WAL) +
  `fs_artifacts` (writes atomiques), `secrets/` (DPAPI Windows),
  `prompts/loader` + `defaults/*.j2` (8 phases + 8 `pedagogy_*`).
- `app/` — use-cases : `ProjectService` (+ `get_last_completed_run`),
  `RunOrchestrator`, `SupportsOrchestrator`, `CostEstimator`,
  `PedagogyCostEstimator`, `pedagogy_export` (Anki/MD/PDF/HTML) + `generation_export`
  (consolidé + glossaire MD/PDF/HTML) sur le cœur partagé `document_export`, `_cost_common`,
  `PromptsService`, `SecretsService`, `VideoScanner`,
  `HardwareProbe`. (Le glossaire est lu sur disque — `glossary_master.json` —
  comme le pipeline ; parsing/rendu dans `domain/glossary`, pas de service dédié.)
- `ui/` — PySide6 : `features/` (abstraction onglet : `FeatureId`, `FeatureTab`,
  `FeatureRegistry`, `GenerationTab`, `PedagogyTab` réel), `viewmodels/` (logique
  testable **sans Qt**, dont `PedagogyProgressViewModel`/`PedagogyStateViewModel`),
  `widgets/` (dont `SettingsView` master-detail réutilisable, `PedagogyProgressView`),
  `dialogs/` (dont `GenerationSettingsView`, `PedagogySettingsView`),
  `theme/` (QSS Clair Fluent), `pedagogy_labels`, `main_window` (sidebar +
  `QTabWidget`), `generation_controller`, `pedagogy_controller`, `qt_event_bus`
  (`QtEventBus` + `PedagogyQtEventBus`), `app_main` (point d'entrée + DI complet).

## Le pipeline en 8 phases

Ordre canonique dans `phase_registry.py`. Chaque handler déclare `is_per_video` :

| Phase | Handler | Mode |
|-------|---------|------|
| 0 STT | `phase_0_stt` | **par vidéo** |
| 1 Extraction termes | `phase_1_term_extraction` | **par vidéo** |
| 2 Réconciliation glossaire | `phase_2_glossary_reconciliation` | batch |
| 3 Reformulation | `phase_3_reformulation` | **par vidéo** |
| 4 Structuration | `phase_4_structuration` | **par vidéo** |
| 5 Consolidation | `phase_5_consolidation` | batch |
| 6 Traduction | `phase_6_translation` | batch (boucle vidéos × langues) |
| 7 Cohérence | `phase_7_coherence` | batch (boucle langues) |

Le `PipelineEngine._execute_one` persiste chaque `PhaseExecution` en SQLite. Une
phase déjà `SUCCEEDED` est **skippée** (passée en `SKIPPED`). C'est le socle du
checkpoint/reprise. Les phases batch sont persistées avec `video_id IS NULL`.

**Parallélisme** : le moteur exécute les phases per-video via
`core/concurrency/map_bounded` borné par `PhaseHandler.max_parallel_workers(ctx)`
(défaut 1 ; phase 0 = `parallelism.stt_cloud_workers` si STT cloud sinon 1 — 1 GPU
local ; phases 1/3/4 = `parallelism.llm_workers`). Les phases batch parallélisent
leurs boucles internes : 6 sur `(langue × document)`, 7 sur les langues, 5 sur les
résumés vidéo (ordre des résultats préservé → assemblage déterministe). Les
barrières restent les phases batch 2 et 5 (le moteur reste « phase par phase »).
`ParallelismConfig` est câblée et réglable dans l'UI (défaut `llm_workers=16`,
`stt_cloud_workers=3`). Détails : `docs/superpowers/specs/2026-05-21-parallelisation-traitements-design.md`.

## Mécanismes transverses (à connaître avant de modifier)

- **Coquille multi-fonctionnalités** : la zone projet est une `QTabWidget` peuplée
  par un `FeatureRegistry` (calqué sur `PhaseRegistry`). Un `Project` ne porte que
  nom + emplacement (immuable après création) ; les réglages métier sont par
  fonctionnalité (`GenerationSettings`, `None` = « à configurer »). Le workspace a un
  dossier par fonctionnalité (`<emplacement>/generation/…`). Le blob
  `projects.settings_json` est en **v2** (`{version, workspace_folder, generation,
  pedagogy}`) avec migration *lenient* v1→v2 à la lecture. Ajouter une fonctionnalité
  = enregistrer un `FeatureTab`, sans toucher `MainWindow` ni `Project`.
- **Checkpoint / reprise après erreur** : un Run garde le même `RunId` du début à
  la fin. `RunOrchestrator.resume_or_create_run(project)` reprend le dernier Run
  s'il est `FAILED`/`PAUSED`/`RUNNING`-orphelin (les phases `SUCCEEDED` seront
  skippées), sinon crée un nouveau Run. La state machine autorise donc
  `FAILED → RUNNING`. Ne jamais re-`create_run` pour « reprendre » : ça forge un
  nouveau `RunId` et perd tout le checkpoint.
- **Piège SQLite `UNIQUE` + `NULL`** : SQLite traite `NULL` comme distinct dans
  une contrainte `UNIQUE`, donc `ON CONFLICT(run_id, phase_id, video_id)` ne se
  déclenche **jamais** pour les phases batch (`video_id IS NULL`).
  `SqliteState.upsert_phase_execution` fait un `DELETE + INSERT` explicite dans ce
  cas. Toute évolution du schéma passe par `_apply_soft_migrations` (idempotent,
  `ALTER TABLE ADD COLUMN` ou nettoyage de données).
- **DeepSeek thinking** : `DeepSeekAdapter` envoie le mode raisonnement via
  `extra_body={"thinking": {"type": "enabled"|"disabled"}, "reasoning_effort":
  "high"|"max"}`, configurable **par phase** (`PhaseConfig.thinking_enabled` +
  `reasoning_effort`). `CostEstimator` applique un multiplicateur sur les tokens
  de sortie selon ce niveau (×2.5 / ×3.5 HIGH / ×6 MAX) — les tokens de
  raisonnement sont facturés au tarif output.
- **Override des prompts** : `PromptLoader` charge prioritairement
  `%APPDATA%/Fahmi2/prompts/<nom>.j2` s'il existe et est un Jinja2 valide, sinon
  le défaut bundlé dans `infra/prompts/defaults/`. `PromptsService` +
  `PromptsEditorDialog` exposent ça dans l'UI. Modifier un `.j2` de `defaults/`
  change la base pour tous, mais un override `%APPDATA%` le masque. Le catalogue
  couvre les 8 phases **et** les 8 templates `pedagogy_*` (tous éditables pareil).
- **Supports pédagogiques** : 8 types, tous LLM, générés par un **orchestrateur
  dédié léger** (`SupportsOrchestrator`, **pas** le `PipelineEngine`) qui
  **parallélise les unités (langue × support)** via `core/concurrency/map_bounded`
  (borné par `PedagogySettings.llm_workers`, défaut 16, plage 1–64 exposée en
  réglage ; verrou sur le manifeste, compteur de coût partagé). Le **plafond de
  coût est best-effort** en parallèle (léger dépassement toléré par les requêtes
  en vol). Détails : `docs/superpowers/specs/2026-05-21-parallelisation-traitements-design.md`.
  Les entrants sont lus **sur disque** comme le pipeline :
  document consolidé (parsé en chapitres ; une **langue de contenu** est résolue
  parmi les `consolidated.{lang}.md` existants — la langue cible peut donc différer)
  et glossaire (`glossary_master.json` ; pas de table SQLite). Les supports sont
  rédigés par le LLM dans la **langue cible** choisie, indépendamment de la langue
  du document source. Pas de checkpoint SQLite : la fraîcheur est suivie par le
  `pedagogy/manifest.json` (hash des réglages + mtime source par langue), une source
  régénérée **périme** les supports (bandeau d'état UI). **Alignement sur la
  génération** (`_is_complete`) : relancer un ensemble **complet** (tout présent +
  frais) **régénère** tout (écrase, comme un nouveau run) ; un ensemble **incomplet**
  (interruption / plafond) est **repris** *coarse* (supports frais skippés, manquants
  générés). Le statut de la dernière exécution est persisté sur disque
  (`pedagogy/run_state.json` : `RunStatus` + horodatages + coût) pour un statut
  homogène avec la génération (sidebar, tuiles), lisible hors session active. Le
  `SupportsOrchestrator` applique
  un **plafond de coût** (`PedagogyCostEstimator`). Les générateurs LLM partagent
  le retry du pipeline (`core/retry/classification.default_classify`) via
  `pedagogy/generators/_base.py` (parsing JSON typé). Les supports **évaluatifs**
  « corrigé séparé » produisent un `<support>.corrige.md` distinct du sujet.
  Exports : `.apkg` (genanki) via `app/pedagogy_export.py`, **Markdown/PDF/HTML
  un fichier par support et par corrigé** (`<support>.<lang>(.corrige).<ext>`) via
  le cœur partagé `app/document_export.py` (`write_documents` : collecteur →
  écriture par format ; `infra/export/markdown_pdf` reste un pur *renderer*). La
  **génération** a son propre export documentaire `app/generation_export.py`
  (consolidé + glossaire, un fichier par langue, MD/PDF/HTML ; réglage
  `GenerationSettings.export_formats`, opt-in). Côté UI, le helper partagé
  `ui/_export_ui.py` (`choose_export_format` + `run_document_export`) factorise
  choix de format → dossier → erreurs → log pour les deux contrôleurs. Les
  prompts autorisent un Markdown léger dans le contenu ; l'export Anki **convertit
  les champs Markdown en HTML** (`genanki_exporter._md_to_html`) — sauf le texte
  cloze (mécanique `{{cN::}}` préservée). MD/PDF/HTML consomment le Markdown rendu tel quel.
  **Gotchas du renderer `infra/export/markdown_pdf` (fpdf2 + python-markdown)** :
  (1) les tableaux pipe GFM exigent l'extension `tables` (`_MARKDOWN_EXTENSIONS`),
  sinon ils restent du texte littéral (HTML comme PDF) ; (2) `fpdf2.write_html`
  **lève** `FPDFException` sur un lien d'ancre interne `<a href="#...">` (sommaire
  du consolidé) faute de `set_link` → on neutralise ces ancres au PDF
  (`_INTERNAL_ANCHOR_RE`, texte conservé) ; (3) `fpdf2` rend les puces/numéros de
  liste à une taille erronée sans `font_size_pt` explicite sur `li`/`ol`/`ul`
  (`_pdf_tag_styles`).
- **Erreurs → UI** : une exception levée par un handler **doit** être une
  `Fahmi2Error` (code + user_message + technical_details). Le moteur la convertit
  en `ErrorInfo`, la propage dans `PhaseFinished.error`, et `generation_controller._to_log_event`
  l'expose dans le panneau Logs (code + message + détails) et `events.jsonl`.
- **UI threading & projet affiché** : un Run tourne dans un `QThread` worker. Le
  `GenerationController` (découplé du `MainWindow` : il reçoit header/stats/matrice/logs)
  distingue `_current_project` (affiché dans le dashboard) de
  `_active_worker_project_id` (projet du worker actif) — les events du pipeline
  ne rafraîchissent matrice/stats que si les deux coïncident, pour ne pas écraser
  le dashboard quand l'utilisateur navigue entre projets pendant un Run. Le
  bridge worker→UI passe par `QtEventBus` (EventBus → Signal Qt).
- **Secrets** : clés API chiffrées via DPAPI Windows (`DPAPISecretsStore`),
  jamais en clair sur disque ni dans les logs. Hors Windows (dev), fallback
  `InMemorySecretsStore`.

## Tests

Fixtures clés (dans `tests/conftest.py`) : `make_generation_settings` fabrique des
`GenerationSettings` valides, `make_project` un `Project` minimal ; passer des kwargs
pour surcharger. Les providers
réels ont des doubles `_fakes.py` (`FakeLLMProvider`, `FakeSTTProvider`). Les
viewmodels UI se testent sans Qt ; les widgets ont des smoke tests `pytest-qt`.
`mypy --strict` est actif : attention au narrowing après un `assert` suivi d'un
appel mutant (contourner via `getattr` plutôt que d'accepter un faux
`unreachable`).

## Directives systématiques

0. **Toujours valider la complétude du plan**
1. **Constants centralization** — pas de magic string, magic number, valeur par défaut directement dans le code mais dans des constantes
2.  Conformity with existing codebase patterns (reuse existing classes, methods, helpers, constants, mixins, base classes)
3.  Follow the Google Python Style Guide — Google-style docstrings with Args, Returns, Raises sections; module-level docstrings on every file
4.  Verify naming consistency (imports, classes, methods, variables, constants) and that all arguments are properly defined and passed
5. Respect framework patterns
6. Respect DRY, YAGNI, KISS, SRP, SoC, Boy Scout Rule, Composition over Inheritance
7. Write generic, extensible code — no duplication, reuse validator mixins and base classes
8. Update all documentation in `docs/` as well as all cross-cutting docs, `README.md`