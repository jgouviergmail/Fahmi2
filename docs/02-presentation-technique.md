# Fahmi2 — Présentation technique

## 1. Stack et plateforme

| Composant | Choix |
|-----------|-------|
| **OS cible** | Windows 11 (10 minimum), mono-utilisateur |
| **Langage** | Python 3.11 ou 3.12 |
| **UI** | PySide6 (Qt 6) — application native fenêtrée |
| **STT local** | faster-whisper 1.x (modèle `large-v3-turbo`, CUDA) |
| **STT cloud** | OpenAI Whisper (`whisper-1`) via SDK officiel |
| **LLM** | DeepSeek v4 Flash / Pro via SDK OpenAI-compatible |
| **Audio** | ffmpeg-python (wrapper) + binaire ffmpeg bundlé |
| **Retrieval** | scikit-learn (TF-IDF + cosine similarity) |
| **Templates** | Jinja2 (prompts paramétrables) |
| **Stockage** | SQLite (mode WAL) + fichiers Markdown / JSON |
| **Secrets** | Windows DPAPI (`win32crypt.CryptProtectData`) |
| **Tests** | pytest, pytest-qt, pytest-cov |
| **Lint/types** | ruff (formatter + linter), mypy `--strict` |
| **Packaging** | PyInstaller `--onedir`, .zip portable |

## 2. Architecture en couches

```
┌────────────────────────────────────────────────────────────────────┐
│                          UI (PySide6 — MVVM)                       │
│  MainWindow  ProjectsSidebar  RunMatrixView  LogsDock  Dialogs     │
└─────────────────────────────┬──────────────────────────────────────┘
                              │ signaux Qt, ViewModels (sans Qt)
┌─────────────────────────────▼──────────────────────────────────────┐
│                       Application (use-cases)                      │
│   ProjectService · RunOrchestrator · CostEstimator                 │
│   GlossaryReconciler · SecretsService · HardwareProbe              │
└────┬──────────┬───────────┬──────────────┬───────────┬─────────────┘
     │          │           │              │           │
     ▼          ▼           ▼              ▼           ▼
┌────────┐ ┌─────────┐ ┌─────────┐  ┌────────────┐ ┌─────────┐
│ Domain │ │Pipeline │ │  Infra  │  │   Core     │ │  Tests  │
│ pure   │ │ Engine  │ │ stt/llm │  │ log/retry/ │ │ fakes & │
│ models │ │+8 hand- │ │ ffmpeg/ │  │ errors/cfg │ │ fixtures│
│        │ │ lers    │ │ sqlite/ │  │            │ │         │
│        │ │         │ │ dpapi/  │  │            │ │         │
│        │ │         │ │ prompts │  │            │ │         │
└────────┘ └─────────┘ └─────────┘  └────────────┘ └─────────┘
```

### 2.1 Couche `core`

Modules transverses, sans dépendance externe (ni Qt, ni HTTP, ni SQL) :

- `core/logging` — `LogEvent` structuré, `LogSink` abstrait, `JsonlFileSink`,
  redaction globale des secrets enregistrés.
- `core/errors` — hiérarchie `Fahmi2Error` (TransientError, PermanentError,
  STTError, LLMError, FFmpegError, StorageError, ConfigError, …),
  `ErrorInfo` sérialisable, registre de messages localisés FR.
- `core/retry` — `RetryPolicy` (exponentiel + jitter borné), `with_retry`
  runner avec classifier injectable.
- `core/config` — `AppPaths` (résolution Windows APPDATA / LOCALAPPDATA),
  `AppConfig`, résolveur `ffmpeg` bundlé runtime (PyInstaller `_MEIPASS`).
- `core/migrations` — `MigrationRunner` générique forward-only,
  `v01_baseline`.
- `core/retrieval` — Protocol `GlossaryRetriever`, `PassthroughRetriever`,
  `TfidfGlossaryRetriever`.
- `core/ids` — wrappers ULID (`new_ulid`, `parse_ulid`, `ulid_to_datetime`).

### 2.2 Couche `domain`

Entités pures immuables + machines d'état :

- Énumérations : `Language`, `StylePreset`, `PhaseId` (8 phases),
  `RunStatus`, `PhaseStatus`, `SttProvider`, `LLMModel`.
- IDs typés : `ProjectId`, `RunId`, `VideoId` (via base `_UlidIdBase`).
- Entités : `Term`, `Glossary`, `PhaseConfig`, `PhaseExecution`,
  `VideoExecution`, `Run`, `Project`, `ProjectSettings`,
  `ParallelismConfig`.
- Validations exhaustives dans `__post_init__` (output_languages contient
  source_language, phases_config couvre exactement les phases LLM, etc.).
- `state_machine.py` : `validate_transition_run`,
  `validate_transition_phase` avec tables de transitions immuables.

### 2.3 Couche `pipeline`

Moteur d'exécution pur :

- `PauseToken` thread-safe (request_pause/resume/cancel).
- `EventBus` in-memory + types d'événements (`RunStarted`, `PhaseStarted`,
  `PhaseProgress`, `PhaseFinished`, `RetryAttempt`, `RunFinished`).
- `PhaseHandler` ABC + `PhaseContext` (DI complet).
- `PhaseRegistry` (ordre canonique des 8 phases).
- `PipelineEngine` — boucle d'exécution avec checkpoint SQLite, retry
  policy, événements, pause/cancel.
- 8 handlers dans `pipeline/handlers/` (un fichier par phase).
- `pipeline/handlers/_base.py` — helpers communs (invoke LLM, parse JSON,
  build PhaseExecution succeeded, sélection top-K glossaire).

### 2.4 Couche `infra`

Adapters externes (ports/adapters) :

- `infra/audio/ffmpeg_extractor.py` — `FFmpegExtractor` (subprocess avec
  ffprobe pré-check piste audio).
- `infra/stt/` — interface `STTProvider`, `FakeSTTProvider`,
  `FasterWhisperAdapter`, `OpenAIWhisperAdapter`.
- `infra/llm/` — interface `LLMProvider`, `FakeLLMProvider`, `DeepSeekAdapter`,
  module `_pricing` avec grilles tarifaires.
- `infra/storage/sqlite_state.py` — `SqliteState` mode WAL, 1 connexion par
  thread, busy_timeout, retry SQLITE_BUSY.
- `infra/storage/fs_artifacts.py` — `FsArtifactStore` (writes atomiques
  `.tmp` + rename).
- `infra/secrets/` — Protocol `SecretsStore`, `InMemorySecretsStore`,
  `DPAPISecretsStore` (Windows).
- `infra/prompts/` — `PromptLoader` avec override `%APPDATA%/Fahmi2/prompts/`
  + 8 templates Jinja2 bundlés.

### 2.5 Couche `app`

Services applicatifs :

- `ProjectService` — CRUD projets.
- `RunOrchestrator` — lifecycle Run (création + scan vidéos, exécution via
  PipelineEngine, persistance, pause/cancel/resume).
- `VideoScanner` — détection des extensions vidéo supportées dans un dossier.
- `CostEstimator` — heuristique pré-run STT + LLM par phase et langue.
  Accepte un `phases_config` optionnel et applique un multiplicateur
  empirique sur les `completion_tokens` selon `thinking_enabled` et
  `reasoning_effort` (×1 / ×2.5 / ×3.5 HIGH / ×6 MAX). Les tokens de
  raisonnement de DeepSeek étant facturés au tarif output standard, ce
  multiplicateur reflète directement le surcoût observé.
- `GlossaryReconciler` — import payload JSON, load Glossary, render
  Markdown 4 colonnes (Terme / Acronyme / Signification / Définition,
  ou Term / Acronym / Meaning / Definition).
- `PromptsService` — gestion des overrides utilisateur des templates LLM
  (lecture défaut bundlé, lecture / écriture / suppression d'override
  dans `%APPDATA%/Fahmi2/prompts/`, validation Jinja2). Backend du
  `PromptsEditorDialog`.
- `SecretsService` — wrapper SecretsStore avec redaction logs auto.
- `HardwareProbe` — détection CUDA/GPU au démarrage.

### 2.6 Couche `ui`

Qt PySide6 :

- `ui/theme/` — feuille de style globale **Clair Fluent**
  (`light_fluent.qss`) chargée au démarrage via `apply_theme(app)`.
  Palette accent `#0078d4`, surfaces blanches sur fond `#f5f7fb`,
  `QCheckBox::indicator` stylisé (glyphe ✓ SVG inline en data URL).
  Le QSS est bundlé via le `.spec` PyInstaller pour rester accessible
  en mode packagé.
- `ui/viewmodels/` — logique testable sans Qt (`RunMatrixViewModel`,
  `StatsStripViewModel` enrichi avec `started_at`, `finished_at`,
  `elapsed_seconds` pour piloter la carte Durée live).
- `ui/widgets/` :
  - `StatsStripWidget` — 5 cartes (Statut, Vidéos, Phases, Durée,
    Coût) avec icône + titre + valeur + sous-info, et un `QTimer`
    interne (1 s) qui rafraîchit la carte Durée tant que le Run est
    `RUNNING` ou `PAUSED`.
  - `RunMatrixView` — colorisation par `PhaseStatus`, en-têtes courts
    (STT, Termes, Glossaire…), alignement centré.
  - `ProjectsSidebar` — menu contextuel Modifier / Supprimer
    (`contextMenuEvent` utilise `viewport().mapFromGlobal()` pour rester
    insensible au padding QSS).
  - `LogsDock` — rendu HTML coloré par sévérité.
  - `ProjectHeaderBar` — boutons typés `primary` / `default` / `danger`
    via propriété QSS, **bouton « 💵 Estimer le coût »** et **bouton
    « 📂 Dossier de sortie »**.
  - `PhaseConfigsWidget` — grille de configuration par phase LLM
    (thinking, reasoning_effort HIGH / MAX, température, max retries).
- `ui/dialogs/` — `NewProjectDialog`, `GlobalSettingsDialog`,
  **`PromptsEditorDialog`** (splitter sidebar + éditeur monospace,
  Enregistrer avec validation Jinja2, Réinitialiser au défaut).
- `ui/main_window.py` — cockpit dense + menu Édition → *Paramètres
  globaux…* / *Modifier les prompts…*.
- `ui/run_controller.py` — orchestre le lifecycle Run depuis l'UI
  (worker QThread, pause/resume/cancel via `PauseToken`, slot
  **`estimate_cost`** qui scanne le dossier, probe ffprobe et appelle
  `CostEstimator` avec `settings.phases_config`).
- `ui/qt_event_bus.py` — adapter EventBus → Signal Qt (bridging worker → UI
  thread).
- `ui/app_main.py` — point d'entrée + DI complet (apply_theme,
  RunController, PromptsService).

## 3. Flux principal d'un Run

```
[Utilisateur clic ▶ Lancer]
        │
        ▼
RunOrchestrator.create_run(project)
        │  ── scan dossier d'entrée (VideoScanner)
        │  ── persistance Project + Run + VideoExecutions
        ▼
RunOrchestrator.execute(run, ctx)
        │  ── delegate à PipelineEngine.execute(ctx)
        ▼
PipelineEngine boucle sur les phases :
   pour chaque PhaseHandler dans l'ordre canonique :
     pour chaque vidéo (si per-video) ou une seule fois (si batch) :
        1. check PauseToken (raise si cancel, wait si pause)
        2. lookup checkpoint SQLite (skip si SUCCEEDED)
        3. emit PhaseStarted
        4. exécuter handler avec retry policy
        5. persister PhaseExecution en SQLite (transaction)
        6. emit PhaseFinished
        │
        ▼
[Sortie : Markdown par vidéo × langues, glossaire × langues, consolidé × langues]
```

## 4. Modèle de données

### 4.1 Schéma SQLite (v1)

```sql
CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);

CREATE TABLE projects (
  id TEXT PRIMARY KEY, name TEXT NOT NULL,
  created_at TEXT NOT NULL, settings_json TEXT NOT NULL,
  last_run_at TEXT
);

CREATE TABLE runs (
  id TEXT PRIMARY KEY, project_id TEXT NOT NULL,
  status TEXT NOT NULL, started_at TEXT NOT NULL,
  finished_at TEXT, cost_usd REAL NOT NULL DEFAULT 0,
  settings_snapshot_json TEXT NOT NULL,
  FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE videos (
  id TEXT PRIMARY KEY, run_id TEXT NOT NULL,
  source_path TEXT NOT NULL, detected_language TEXT,
  FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
);

CREATE TABLE phase_executions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL, phase_id TEXT NOT NULL, video_id TEXT,
  status TEXT NOT NULL,
  started_at TEXT, finished_at TEXT,
  artifact_path TEXT, retry_count INTEGER NOT NULL DEFAULT 0,
  cost_usd REAL NOT NULL DEFAULT 0, error_json TEXT,
  UNIQUE (run_id, phase_id, video_id),
  FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
);

CREATE TABLE glossary_terms (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL, language TEXT NOT NULL,
  term TEXT NOT NULL, definition TEXT NOT NULL,
  acronym TEXT, acronym_expansion TEXT,
  sources_json TEXT NOT NULL, aliases_json TEXT NOT NULL,
  cross_lang_json TEXT NOT NULL,
  UNIQUE (run_id, language, term),
  FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
);
```

Index : `idx_runs_project_id`, `idx_videos_run_id`,
`idx_phase_executions_run`, `idx_phase_executions_lookup`,
`idx_glossary_run_lang`.

**Soft migrations** appliquées automatiquement à l'ouverture
(idempotentes, sans perte de données) :

- Ajout des colonnes `glossary_terms.acronym` et
  `glossary_terms.acronym_expansion` (`ALTER TABLE ADD COLUMN`) si
  absentes sur une DB préexistante.
- Nettoyage rétroactif des doublons batch dans `phase_executions` (lignes
  multiples avec `video_id IS NULL` pour la même `(run_id, phase_id)` —
  SQLite traite `NULL` comme distinct dans une contrainte `UNIQUE`,
  ce qui faisait s'accumuler les lignes avant que le upsert ne gère
  explicitement le cas `NULL`). On ne conserve que la ligne `id` la
  plus récente par groupe.

**`upsert_phase_execution`** distingue maintenant les deux cas :

- `video_id` défini → `INSERT ... ON CONFLICT(run_id, phase_id,
  video_id) DO UPDATE`.
- `video_id IS NULL` (phases batch) → `DELETE FROM phase_executions
  WHERE run_id = ? AND phase_id = ? AND video_id IS NULL` puis
  `INSERT`. C'est la seule manière fiable d'unifier les phases batch
  dans SQLite.

### 4.2 Arborescence des artefacts (par projet)

```
<workspace_folder>/
├── transcripts/{video_id}.json       ← Phase 0 STT
├── audio/{video_id}.wav              ← Audio extrait (supprimable)
├── candidates/{video_id}.json        ← Phase 1
├── glossary_master.json              ← Phase 2
├── reformulated/{video_id}.md        ← Phase 3
├── structured/{video_id}.md          ← Phase 4
└── consolidated_master.md            ← Phase 5

<output_dir>/
├── consolidated.{lang}.md            ← Phases 6 + 7
├── glossary.{lang}.md
└── per-video/{lang}/{video_id}.md
```

## 5. Conventions de code

- **Style** : Google Python Style Guide, docstrings avec sections
  `Args`, `Returns`, `Raises`.
- **Linting** : ruff strict (E, F, W, B, C90, N, UP, ANN, S, PL, I).
- **Type checker** : mypy `--strict`, zéro erreur tolérée.
- **Constantes magiques** : centralisées au top des modules.
- **Helpers privés** : préfixe `_method_name`.
- **Modules internes** : préfixe `_` (ex: `_base.py`, `_pricing.py`,
  `_schema.sql`, `_fakes.py`).
- **Immutabilité** : entités domaine `@dataclass(frozen=True)`, with-
  méthodes pour copies modifiées (`with_status`, `with_added_cost`).

## 6. Tests

### 6.1 Stratégie par couche

| Couche | Type de tests | Couverture |
|--------|---------------|------------|
| `domain/` | unitaires purs | ~100 % |
| `core/` | unitaires | ~95 % |
| `pipeline/` | unitaires avec fakes | ~95 % |
| `infra/` adapters | mock SDK + fixtures | ~90 % (real adapters testés manuel) |
| `app/` | unitaires + intégration | ~95 % |
| `ui/` viewmodels | unitaires (sans Qt) | ~95 % |
| `ui/` widgets | smoke pytest-qt | golden path |
| End-to-end | run complet sur fakes + ffmpeg réel | 1 happy path + erreurs clés |

### 6.2 Métriques actuelles

- **445+ tests** passants
- **ruff** + **mypy --strict** propres sur 186+ fichiers

## 7. Packaging et distribution

- **PyInstaller `--onedir`** : démarrage rapide, antivirus plus permissif
  qu'avec `--onefile`.
- **ffmpeg bundlé automatiquement** : `packaging/fetch-ffmpeg.ps1` télécharge
  le binaire et vérifie le SHA256 ; `packaging/build.ps1` l'appelle
  automatiquement avant le build.
- **Modèle Whisper non bundlé** : téléchargé à la demande au premier run en
  mode STT local (sinon jamais).
- **.zip portable** : `packaging/make-portable-zip.ps1` produit
  `Fahmi2-<version>-win64.zip`.
- **Pas de signature de code en v1** : un avertissement SmartScreen apparaît
  au 1er lancement (clic « Plus d'infos » → « Exécuter quand même »).

## 8. Sécurité

- **Clés API chiffrées** via DPAPI Windows (`CryptProtectData`), liées à
  l'utilisateur Windows courant.
- **Aucune télémétrie** sortante.
- **Mode hors-ligne possible** (STT local + LLM cloud, ou inversement).
- **Redaction automatique** des valeurs secrètes dans tous les logs
  (mécanisme global `register_secret`).
- **Mark-of-the-Web** SmartScreen : pas de bypass, l'utilisateur garde le
  contrôle.

## 9. Évolutivité

L'architecture est ouverte à des extensions sans casser l'existant :

- **Ajouter une langue** : ajouter à `Language` + ses libellés FR/EN + tests.
- **Ajouter un provider STT** : implémenter le Protocol `STTProvider`.
- **Ajouter un provider LLM** : implémenter le Protocol `LLMProvider` +
  ajouter une grille de tarifs dans `_pricing.py`.
- **Ajouter une phase** : créer un `PhaseHandler` + l'enregistrer dans
  `PhaseRegistry`. L'ordre canonique est défini dans `phase_registry.py`.
- **Changer le retriever de glossaire** : implémenter `GlossaryRetriever`
  (Protocol) — actuellement TF-IDF, demain peut-être embeddings.
- **Migrer le schéma SQLite** : créer `core/migrations/vXX_to_vYY.py` et
  enregistrer dans le `MigrationRunner` chaîné.
