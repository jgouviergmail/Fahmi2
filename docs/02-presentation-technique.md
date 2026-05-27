# Fahmi2 — Présentation technique

## 1. Stack et plateforme

| Composant | Choix |
|-----------|-------|
| **OS cible** | Windows 11 (10 minimum), mono-utilisateur |
| **Langage** | Python 3.11 ou 3.12 |
| **UI** | PySide6 (Qt 6) — application native fenêtrée |
| **STT local** | faster-whisper 1.x (modèle configurable, défaut `large-v3-turbo`, CUDA) |
| **STT cloud** | OpenAI Transcribe (modèle configurable, défaut `whisper-1`) via SDK officiel |
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
│  MainWindow  ProjectsSidebar  CostMatrixView  LogsDock  Dialogs    │
└─────────────────────────────┬──────────────────────────────────────┘
                              │ signaux Qt, ViewModels (sans Qt)
┌─────────────────────────────▼──────────────────────────────────────┐
│                       Application (use-cases)                      │
│   ProjectService · RunOrchestrator · CostEstimator                 │
│   SupportsOrchestrator · SecretsService · HardwareProbe            │
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
- `core/concurrency` — `map_bounded` (pool de threads borné, *fail-fast*, ordre
  des résultats préservé, honore le `PauseToken`) ; primitif partagé par le moteur
  de génération et l'orchestrateur pédagogie pour paralléliser les appels
  I/O-bound (LLM, STT cloud).
- `core/config` — `AppPaths` (résolution Windows APPDATA / LOCALAPPDATA),
  `AppConfig`, résolveur `ffmpeg` bundlé runtime (PyInstaller `_MEIPASS`).
- `core/migrations` — `MigrationRunner` générique forward-only,
  `v01_baseline`.
- `core/retrieval` — Protocol `GlossaryRetriever`, `PassthroughRetriever`,
  `TfidfGlossaryRetriever`.
- `core/ids` — wrappers ULID (`new_ulid`, `parse_ulid`, `ulid_to_datetime`).

### 2.2 Couche `domain`

Entités pures immuables + machines d'état :

- Énumérations : `Language` (7 langues : fr/en/de/es/it/zh/ar),
  `StylePreset`, `PhaseId` (8 phases),
  `RunStatus`, `PhaseStatus`, `SourceKind` (vidéo/audio/document/YouTube),
  `SttProvider`, `LLMModel`, `ReasoningEffort`, et
  pédagogie : `SupportType` (×8), `TargetAudience`, `BloomObjective`,
  `SupportDensity`, `ExportFormat`.
- IDs typés : `ProjectId`, `RunId`, `SourceId` (via base `_UlidIdBase`).
- Entités : `Term`, `Glossary`, `PhaseConfig`, `PhaseExecution`, `InputSource`
  (source polymorphe : fichier local ou URL), `SourceExecution`,
  `Run`, `Project` (identité minimale : nom + emplacement +
  réglages par fonctionnalité `generation`/`pedagogy`), `GenerationSettings`,
  `ParallelismConfig`, `PedagogySettings`, et entités de support
  (`Flashcard`, `QcmItem`, `TrueFalseItem`, `ClozeItem`, `OpenQuestion`,
  `RevisionSheet`, `KeyPoints`, `MockExam`/`MockExamSection`, `SupportArtifact`).
- Validations exhaustives dans `__post_init__` (output_languages contient
  source_language, phases_config couvre exactement les phases LLM,
  `separate_correction` ⊆ évaluatifs sélectionnés, `correct_index` valide, etc.).
- Le blob `projects.settings_json` est en **v2** (`{version, workspace_folder,
  generation, pedagogy}`) avec migration *lenient* v1→v2 à la lecture.
- `state_machine.py` : `validate_transition_run`,
  `validate_transition_phase` avec tables de transitions immuables.

### 2.3 Couche `pipeline`

Moteur d'exécution pur :

- `PauseToken` thread-safe (request_pause/resume/cancel).
- `EventBus` in-memory + types d'événements (`RunStarted`, `PhaseStarted`,
  `PhaseProgress`, `PhaseFinished`, `RetryAttempt`, `RunFinished`).
- `PhaseHandler` ABC + `PhaseContext` (DI complet) ; `max_parallel_workers(ctx)`
  déclare le pool de la phase (défaut 1 = séquentiel ; surchargé par les phases
  per-video indépendantes).
- `PhaseRegistry` (ordre canonique des 8 phases).
- `PipelineEngine` — boucle d'exécution avec checkpoint SQLite, retry
  policy, événements, pause/cancel. Les phases **per-video** sont parallélisées
  via `core/concurrency/map_bounded` (pool borné par `ParallelismConfig` : STT
  cloud = `stt_cloud_workers`, phases LLM 1/3/4 = `llm_workers` ; STT local = 1,
  GPU unique). Les phases batch 5/6/7 parallélisent leurs boucles internes
  (résumés vidéo, langue × document, langues) ; barrières aux phases batch 2 et 5.
- 8 handlers dans `pipeline/handlers/` (un fichier par phase).
- `pipeline/handlers/_base.py` — helpers communs (invoke LLM, parse JSON,
  build PhaseExecution succeeded, sélection top-K glossaire).
- **Phase 5 = dispatcher de stratégies de consolidation** (`pipeline/handlers/
  _consolidation/`) selon `GenerationSettings.consolidation_mode` :
  `_base.py` (ABC `ConsolidationStrategy` + `ConsolidationResult` + helpers
  déterministes partagés : renumérotation, sommaire, assemblage), `ordered.py`
  (1 source = 1 chapitre, contenu recopié — comportement historique), `thematic.py`
  (refonte thématique transversale en **map-reduce à provenance** : relevé factuel
  par source → plan thématique → rédaction par chapitre → méta ; double contrôle
  déterministe de couverture ; aucun identifiant technique dans le livrable ;
  reprise intra-phase par hash de cohérence ; artefacts `consolidation/`).

### 2.4 Couche `pedagogy`

Moteur de génération des **supports de révision** (calqué sur `pipeline`, mais
orchestrateur dédié léger — sans STT/ffmpeg ni état SQLite) :

- `pedagogy/support_generator.py` — `SupportGenerator` (ABC) + `SupportContext` (DI).
- `pedagogy/support_registry.py` — `SupportGeneratorRegistry` (ordre canonique des 9
  supports) ; `pedagogy/default_registry.py` — `build_default_support_registry()`.
- `pedagogy/chapters.py` — parseur de chapitres du doc consolidé ;
  `pedagogy/sources.py` — chemin / mtime / chapitres de la source.
- `pedagogy/events.py` — événements (`SupportGenerationStarted`, `SupportStarted`,
  `SupportRetryAttempt`, `SupportFinished`, `SupportGenerationFinished`).
- `pedagogy/manifest.py` — manifeste de fraîcheur (`pedagogy/manifest.json` :
  hash des réglages + mtime source par langue) → reprise *coarse* + péremption.
- `pedagogy/artifact_writer.py` / `artifact_reader.py` — (dé)sérialisation des
  artefacts (JSON + Markdown) et chemins.
- `pedagogy/generators/` — `_base.py` (invocation LLM avec retry + helpers de parsing
  JSON typé ; base per-chapitre générique + mixin évaluatif) + 8 générateurs LLM
  (flashcards concepts, QCM + dé-biaisage, vrai/faux, cloze, questions ouvertes,
  fiche, points clés, examen blanc).
- `pedagogy/labels.py` — libellés FR (public, Bloom, densité, langue, glossaire).

### 2.5 Couche `infra`

Adapters externes (ports/adapters) :

- `infra/audio/ffmpeg_extractor.py` — `FFmpegExtractor` (subprocess avec
  ffprobe pré-check piste audio).
- `infra/audio/cloud_audio_preparer.py` — `CloudAudioPreparer` (compression
  Opus + découpage aux silences) : prépare l'audio pour le STT cloud sous la
  limite 25 Mo d'OpenAI Whisper. Injecté dans `OpenAIWhisperAdapter`.
- `infra/stt/` — interface `STTProvider`, `FakeSTTProvider`,
  `FasterWhisperAdapter` (modèle local configurable, téléchargé au 1er usage),
  `OpenAIWhisperAdapter` (modèle cloud configurable ; `verbose_json` pour
  `whisper-1`, sinon `json` → segment unique par tranche), `_pricing` (USD/min
  par modèle cloud, partagé avec le `CostEstimator`).
- `infra/ingestion/` — aiguillage polymorphe des entrants (phase 0) : dispatcher
  `SourceKind → SourceIngestor` (calqué sur `PhaseRegistry`), `classify` (mapping
  extension → type), `MediaIngestor` (vidéo/audio : ffmpeg + STT),
  `DocumentIngestor` (pdf/docx/md/txt → transcription à segment unique via
  `TextExtractor`), `YoutubeIngestor` + `YtDlpDownloader` (binaire yt-dlp).
- `infra/llm/` — interface `LLMProvider`, `FakeLLMProvider`, `DeepSeekAdapter`,
  module `_pricing`, helpers généralisés `invocation.py` (`invoke_llm_chat`,
  `parse_llm_json`).
- `infra/storage/sqlite_state.py` — `SqliteState` mode WAL, 1 connexion par
  thread, busy_timeout, retry SQLITE_BUSY.
- `infra/storage/fs_artifacts.py` — `FsArtifactStore` (writes atomiques
  `.tmp` + rename).
- `infra/secrets/` — Protocol `SecretsStore`, `InMemorySecretsStore`,
  `DPAPISecretsStore` (Windows).
- `infra/prompts/` — `PromptLoader` avec override `%APPDATA%/Fahmi2/prompts/`
  + **templates Jinja2 bundlés** : 8 phases de génération + **3 `phase_5_*` du
  mode thématique** + **`phase_6_glossary_localization`** (localisation des termes
  du glossaire) + 8 `pedagogy_*` + 3 `chat_*`.
- `infra/anki/genanki_exporter.py` — export `.apkg` (genanki : Basic/Cloze/QCM,
  GUID stables, sous-decks par support, tags).
- `infra/export/markdown_pdf.py` — rendu Markdown → HTML (`render_markdown_body`,
  partagé) → PDF via `xhtml2pdf`/ReportLab ; **polices système par langue** (Arial
  latin/arabe, Microsoft YaHei chinois, RTL + reshaping arabe). Deux corrections de
  rendu PDF : retrait des caractères **sans glyphe** (émojis → carrés blancs sinon ;
  `_strip_unrenderable_for_pdf`) et **pré-coupe des retours à la ligne du chinois**
  (`_prewrap_cjk_runs` via `wordSplit`/BeautifulSoup ; règle `-pdf-word-wrap: CJK`
  pour les cellules) — réservées aux langues CJK / au PDF (HTML et Word gèrent
  nativement).
- `infra/export/markdown_docx.py` — rendu Markdown → HTML → **DOCX** via `htmldocx`
  (s'appuie sur `python-docx`) ; tableaux reformatés (style **Table Grid** +
  largeur 100 %, htmldocx ne traduit ni les bordures CSS ni `width:100%`) ;
  orientation **paysage** optionnelle (glossaire) ; **arabe en droite-à-gauche**
  (`w:bidi` paragraphes, `w:rtl` runs, `w:bidiVisual` tableaux), aligné sur le
  PDF/HTML. Word gère nativement la police CJK et la coupe de ligne (rien à déclarer
  côté chinois).

### 2.6 Couche `app`

Services applicatifs :

- `ProjectService` — CRUD projets (+ `get_last_completed_run`). La suppression
  efface l'entrée + ses runs en base **et** le dossier workspace du projet sur
  disque (best-effort) ; le dossier d'entrée (sources) et la base globale
  (`%APPDATA%/Fahmi2/projects.db`) ne sont pas touchés.
- `RunOrchestrator` — lifecycle Run (création + collecte des sources, exécution
  via PipelineEngine, persistance, pause/cancel/resume).
- `SupportsOrchestrator` — orchestrateur dédié des supports pédagogiques
  (inputs par langue, **parallélise les unités supports × langues** via
  `core/concurrency/map_bounded` borné par `PedagogySettings.llm_workers`,
  écriture JSON + Markdown, reprise *coarse* via manifeste sous verrou, events,
  plafond de coût *best-effort* en parallèle).
- `input_sources.build_input_sources` — collecte les sources (fichiers
  vidéo/audio/document du dossier + liens YouTube), applique l'ordre
  (`source_order`) et l'exclusion (`excluded_sources`) via `reconcile_source_order`.
- `CostEstimator` — heuristique pré-run STT + LLM par phase et langue.
  Accepte un `phases_config` optionnel et applique un multiplicateur
  empirique sur les `completion_tokens` selon `thinking_enabled` et
  `reasoning_effort` (×1 / ×2.5 / ×3.5 HIGH / ×6 MAX). Les tokens de
  raisonnement de DeepSeek étant facturés au tarif output standard, ce
  multiplicateur reflète directement le surcoût observé. Heuristiques
  partagées dans `app/_cost_common.py`.
- `PedagogyCostEstimator` — estimation de coût des supports (par support ×
  langue × chapitre, selon densité et thinking).
- `pedagogy_export` / `generation_export` — collecteurs (`collect_*_documents`) +
  façades d'export (`export_pedagogy_to_apkg` pour l'Anki ; `export_*_documents` pour
  Markdown / PDF / HTML / DOCX, déléguées au cœur partagé `document_export.write_documents`).
- Glossaire : pas de service applicatif dédié — il est lu **sur disque**
  (`glossary_master.json`) comme le pipeline ; le parsing (`parse_glossary_master_terms`),
  le rendu Markdown 4 colonnes (`render_glossary_markdown_table` : en-têtes localisés
  par langue parmi les 7, ex. Terme / Acronyme / Signification / Définition ou
  Term / Acronym / Meaning / Definition) et la **localisation terminologique**
  (`localize_glossary_terms` → `cross_lang[L]`, repli sur le terme source) vivent dans
  `domain/glossary.py` (réutilisés par pipeline, pédagogie et Dialogue). La **phase 6**
  localise les termes par un appel LLM structuré (`_localize_glossary`, prompt
  `phase_6_glossary_localization`), rend `glossary.{L}.md` de façon déterministe,
  injecte les équivalents source → cible dans la traduction et persiste `cross_lang`
  dans `glossary_master.json` ; la Pédagogie et le Dialogue **pré-localisent** ensuite
  le glossaire à la langue de contenu qu'ils chargent.
- `PromptsService` — gestion des overrides utilisateur des templates LLM
  (lecture défaut bundlé, lecture / écriture / suppression d'override
  dans `%APPDATA%/Fahmi2/prompts/`, validation Jinja2). Backend du
  `PromptsEditorDialog`. Catalogue : prompts de génération (8 phases + 3 `phase_5_*`
  thématiques + `phase_6_glossary_localization`) + 8 templates `pedagogy_*` + 3 `chat_*`.
- `SecretsService` — wrapper SecretsStore avec redaction logs auto.
- `HardwareProbe` — détection CUDA/GPU au démarrage.

### 2.7 Couche `ui`

Qt PySide6 :

- `ui/theme/` — feuille de style globale **Clair Fluent**
  (`light_fluent.qss`) chargée au démarrage via `apply_theme(app)`.
  Palette accent `#0078d4`, surfaces blanches sur fond `#f5f7fb`,
  `QCheckBox::indicator` stylisé (glyphe ✓ SVG inline en data URL).
  Le QSS est bundlé via le `.spec` PyInstaller pour rester accessible
  en mode packagé.
- `ui/viewmodels/` — logique testable sans Qt :
  - `cost_matrix` — viewmodel **générique** présentationnel (`CostMatrixSnapshot` :
    cellules `statut + coût`, totaux ligne/colonne/général) partagé par les deux
    dashboards (`build_cost_matrix`).
  - `RunMatrixViewModel` — produit un `CostMatrixSnapshot` (vidéos × phases, coût
    par cellule via `list_phase_cells`, coût des phases batch en total de colonne).
  - `StatsStripViewModel` enrichi avec `started_at`, `finished_at`,
    `elapsed_seconds` pour piloter la carte Durée live.
  - `PedagogyProgressViewModel` [accumulation d'events supports × langues ;
    `cost_matrix_snapshot` + `stats_snapshot`] et `PedagogyStateViewModel`
    [fraîcheur : non configuré / génération requise / prêt / à jour / périmé].
- `ui/widgets/` :
  - `StatCard` — carte d'indicateur réutilisable (icône + valeur + sous-info +
    accent), socle des bandes de stats des deux dashboards.
  - `StatsStripWidget` — 5 cartes (Statut, Vidéos, Phases, Durée,
    Coût) bâties sur `StatCard`, avec un `QTimer` interne (1 s) qui rafraîchit la
    carte Durée tant que le Run est `RUNNING` ou `PAUSED`.
  - `CostMatrixView` — matrice de coût **générique** (`QTableView` + délégué) :
    glyphe de statut proéminent + coût secondaire par cellule, totaux mis en avant.
    Partagée par les dashboards Génération (vidéos × phases) et Pédagogie
    (supports × langues). Libellés de statut/accents partagés (`ui/status_labels`).
  - `PedagogyProgressView` — bandeau de fraîcheur + bande de tuiles + `CostMatrixView`.
  - `ProjectsSidebar` — liste des projets préfixés par leurs **icônes de statut**
    `G <icône> / P <icône>` (dernier run génération + pédagogie ; `ProjectListEntry`,
    `update_statuses` pour le rafraîchissement live sans perdre la sélection) ; menu
    contextuel Modifier / Supprimer (`contextMenuEvent` utilise
    `viewport().mapFromGlobal()` pour rester insensible au padding QSS).
  - `LogsDock` — rendu HTML coloré par sévérité ; le filtre « Niveau minimum »
    re-filtre l'affichage existant (tous les events sont conservés).
  - `ProjectHeaderBar` — boutons typés `primary` / `default` / `danger`
    via propriété QSS, **bouton « 💵 Estimer le coût »**, **bouton
    « 📂 Dossier de sortie »**, **bouton « 📦 Exporter » optionnel** et
    **bouton « ↺ Réinitialiser »** (réinitialisation par fonctionnalité, désactivé
    pendant un run ; infobulles paramétrables ; réutilisé par les deux onglets).
  - `PhaseConfigsWidget` — grille de configuration par phase LLM
    (thinking, reasoning_effort HIGH / MAX, température, max retries).
  - `PedagogyProgressView` — bandeau d'état + table de progression (support × langue).
- `ui/dialogs/` — `NewProjectDialog` (minimal : nom + emplacement),
  `GenerationSettingsView` (réglages génération en master-detail),
  `PedagogySettingsView` (réglages pédagogie en master-detail :
  Supports / Difficulté / Langues / Modèle & coût),
  `GlobalSettingsDialog`,
  **`PromptsEditorDialog`** (splitter sidebar + éditeur monospace,
  Enregistrer avec validation Jinja2, Réinitialiser au défaut).
- `ui/pedagogy_labels.py` — libellés UI des supports / statuts / formats d'export.
- `ui/main_window.py` — sidebar projets + `QTabWidget` d'onglets de
  fonctionnalité (peuplé par un `FeatureRegistry`) + menu Édition → *Paramètres
  globaux…* / *Modifier les prompts…*.
- `ui/generation_controller.py` — orchestre le lifecycle Run de l'onglet
  Génération (découplé du `MainWindow` : reçoit header/stats/matrice/logs ;
  worker QThread, pause/resume/cancel via `PauseToken`, slots **`estimate_cost`**
  et **`open_generation_settings`**).
- `ui/pedagogy_controller.py` — orchestre l'onglet Supports pédagogiques
  (worker QThread `SupportsOrchestrator`, pause/cancel, sélecteur d'export
  Anki / Markdown / PDF / HTML / DOCX, bridge `PedagogyQtEventBus`).
- `ui/features/` — abstraction onglet : `FeatureId`, `FeatureTab`,
  `FeatureRegistry`, `GenerationTab` (cockpit + contrôleur), `PedagogyTab`
  (cockpit pédagogique réel + `PedagogyController`).
- `ui/qt_event_bus.py` — adapters EventBus → Signal Qt (`QtEventBus` génération,
  `PedagogyQtEventBus` pédagogie ; bridging worker → UI thread).
- `ui/app_main.py` — point d'entrée + DI complet (apply_theme, onglets de
  fonctionnalité via `FeatureRegistry`, PromptsService, registre des 8 générateurs
  de supports).

### 2.8 Fonctionnalité Dialogue (chat ancré sur le corpus)

Transverse (moteur `chat/` + retrieval + embeddings + UI) : un 3ᵉ onglet
(`FeatureId.CHAT`) où l'utilisateur dialogue avec le corpus produit par la
Génération (consolidé + glossaire).

- `core/retrieval/passages.py` — port `PassageRetriever` + `TfidfPassageRetriever`
  (lexical, réutilise scikit-learn) ; distinct de `GlossaryRetriever`.
- `chat/` (moteur) — `corpus.py` (chargement + chunking par section + glossaire),
  `prompt_builder.py` (système/historique + passages numérotés + garde-fou
  d'historique), `citations.py` (parsing `[§N]`), `query_expander.py` (reformulation
  LLM à la demande si retrieval faible), `retriever_factory.py` (résolution `AUTO` +
  repli), `chat_service.py` (`answer` + `stream_answer`).
- `infra/embeddings/` — port `EmbeddingProvider` + `OpenAIEmbeddingProvider`
  (modèle **configurable** via `EmbeddingModel`, défaut `text-embedding-3-small`) +
  `_pricing` (USD/Mtok par modèle) + fake. Le port expose `consumed_cost_usd()`
  (coût agrégé dans le total du Dialogue). `infra/retrieval/semantic.py` —
  `SemanticPassageRetriever` (index `.npz` persisté + empreinte de validité incluant
  le modèle **+ mtime du consolidé ET du glossaire**, cosine numpy).
- `infra/llm` — extension **additive** `chat_stream` (port + DeepSeek + fake) ;
  `stream_options.include_usage` → coût exact en streaming.
- `app/chat_conversation_store.py` — persistance JSON des conversations
  (`chat/conversations/*.json`) ; `ChatSettings` dans le blob projet v2 (clé `chat`).
- `ui/` — `ChatTab`, `ChatController` (worker `QThread` qui streame via signaux),
  `ChatViewModel` (machine d'état, sans Qt), `ChatView` (fil de bulles + citations
  cliquables + coût), `ChatSettingsView`. **Fraîcheur du corpus** :
  `ChatController.refresh_corpus_if_stale()` re-dérive le corpus quand le consolidé
  ou le glossaire a changé sur disque (clé = langue + mtime consolidé + mtime
  glossaire), appelé avant chaque réponse **et** au signal `run_state_changed` de
  la génération → le Dialogue ne cite jamais un document périmé.

Fidélité **configurable** (prompts `chat_strict`/`chat_augmented`) ; retrieval
**lexical** (offline) ou **sémantique** (embeddings OpenAI), stratégie `AUTO`.

## 3. Flux principal d'un Run

```
[Utilisateur clic ▶ Lancer]
        │
        ▼
RunOrchestrator.create_run(project)
        │  ── collecte des sources (build_input_sources : dossier + URLs,
        │     ordonnées/exclues) — fichiers vidéo/audio/document + liens YouTube
        │  ── persistance Project + Run + SourceExecutions
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
```

> Aucune table de contenu glossaire en base : le glossaire est un artefact
> disque (`glossary_master.json` + `glossary.{lang}.md`), comme les autres
> documents générés.

Index : `idx_runs_project_id`, `idx_videos_run_id`,
`idx_phase_executions_run`, `idx_phase_executions_lookup`.

**Soft migrations** appliquées automatiquement à l'ouverture
(idempotentes, sans perte de données) :

- Suppression de la table `glossary_terms` (`DROP TABLE IF EXISTS`) : intention
  de socle jamais branchée — le glossaire est lu sur disque comme les autres
  documents générés.
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

<emplacement>/pedagogy/                ← Supports pédagogiques (SP2)
├── manifest.json                     ← Fraîcheur (hash réglages + mtime source/langue)
└── {support}/{lang}/
    ├── {support}.json                ← Artefact structuré (items typés)
    ├── {support}.md                  ← Rendu Markdown (sujet)
    └── {support}.corrige.md          ← Corrigé séparé (évaluatifs, si demandé)
```

> Les supports pédagogiques sont produits par le `SupportsOrchestrator`
> (`app/supports_orchestrator.py`) — orchestrateur dédié léger, **pas** le
> `PipelineEngine` — à partir du document consolidé (parsé en chapitres ; une
> **langue de contenu** est résolue parmi les `consolidated.{lang}.md` existants) et
> du glossaire (lu **sur disque** : `glossary_master.json`, comme le pipeline).
> Génération **idempotente** (écrase) + **reprise coarse** : un support frais (hash
> réglages + mtime source inchangés, artefact présent) est *skippé*. Les **8
> supports** sont produits **par LLM** dans la **langue cible** choisie (même si le
> document source est dans une autre langue).

> **Générateurs LLM (SP2/03)** : flashcards concepts, QCM (avec **dé-biaisage
> déterministe** de la position de la bonne réponse), vrai/faux, cloze, questions
> ouvertes, fiche, points clés (par chapitre) et examen blanc (document entier).
> Chacun a un prompt `pedagogy_<support>.j2` **éditable** (Édition → Modifier les
> prompts), un parsing JSON typé vers les entités de `domain/supports.py`, et un
> retry LLM partagé avec le pipeline (`core/retry/classification.default_classify`).
> Les supports **évaluatifs** marqués « corrigé séparé » produisent un fichier
> `<support>.corrige.md` distinct du sujet.

> **Export Anki (SP3/01)** : l'adapter `infra/anki/genanki_exporter.py` (dépendance
> `genanki`) convertit les supports en paquet `.apkg` — `Flashcard`→Basic,
> `ClozeItem`→Cloze, `QcmItem`→note custom. **GUID stables** (`genanki.guid_for`,
> ré-import sans doublon), **sous-decks par support** (`<Projet>::<support>`), **tags**
> (support / langue / niveau / chapitre). La désérialisation des artefacts JSON est dans
> `pedagogy/artifact_reader.py` ; le service `app/pedagogy_export.py` scanne `pedagogy/`.
> Les supports non-cartes (vrai/faux, questions ouvertes, fiche, points clés, examen
> blanc) relèvent de l'export Markdown/PDF/HTML/DOCX. À l'export Anki, les champs
> Markdown sont convertis en HTML (`genanki_exporter._md_to_html`), sauf le texte cloze.

> **Export Markdown/PDF/HTML/DOCX** : le cœur partagé `app/document_export.py`
> (`write_documents`) écrit **un fichier par support et par corrigé** (`<support>.{lang}.<ext>`,
> `<support>.{lang}.corrige.<ext>`) à partir des Markdown **déjà rendus**. Le corps HTML est
> produit une fois par `markdown_pdf.render_markdown_body` (extensions `tables` + `toc`),
> réutilisé par : le HTML (document autonome, CSS intégré) ; le **PDF** via `xhtml2pdf`
> (moteur ReportLab — pagination réelle, **polices système par langue** : Arial pour le
> latin/arabe, Microsoft YaHei pour le chinois, RTL + reshaping arabe ; retrait des
> émojis sans glyphe + pré-coupe des retours à la ligne CJK) ; le **DOCX** via
> `markdown_docx` (htmldocx → python-docx ; Word gère nativement CJK et bidi ; paysage
> optionnel). Les services `app/generation_export.py` et `app/pedagogy_export.py`
> collectent les documents (par langue, le **glossaire** en paysage) ; ils réutilisent
> les `.md` rendus, **pas** de re-rendu (l'`artifact_reader` est réservé à l'Anki).

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

- **1053 tests** passants
- **ruff** + **mypy --strict** propres sur 389 fichiers

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
- **Dépendances exports** : `genanki` (Anki) embarque le schéma en modules Python
  (rien à collecter) ; le **PDF** s'appuie sur `xhtml2pdf`/`reportlab` (purs,
  `collect_all`) ; le **DOCX** sur `htmldocx` + `beautifulsoup4` (purs ; `lxml` déjà
  tiré par `python-docx`). Le rendu PDF utilise des **polices système Windows** (Arial
  latin/arabe, Microsoft YaHei chinois — aucune police à bundler). Détails et procédure
  dans [`packaging/README.md`](../packaging/README.md).
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

- **Ajouter une langue** : ajouter la valeur à `Language` (`domain/enums.py`), son
  libellé dans `domain/languages._LANGUAGE_NAMES` (source unique, prompts + UI), ses
  en-têtes et son titre de glossaire (`domain/glossary`), ses alias de détection STT
  (`openai_whisper_adapter`) ; pour le PDF, ajouter une police si l'écriture l'exige
  (CJK) et, pour une écriture de droite à gauche, l'inscrire dans
  `domain/languages._RTL_LANGUAGES` (source unique RTL pour PDF/HTML/DOCX ;
  + `markdown_pdf._PDF_LANG_RENDERING` pour le reshaping). Tests à compléter.
- **Ajouter un provider STT** : implémenter le Protocol `STTProvider`.
- **Ajouter un provider LLM** : implémenter le Protocol `LLMProvider` +
  ajouter une grille de tarifs dans `_pricing.py`.
- **Ajouter une phase** : créer un `PhaseHandler` + l'enregistrer dans
  `PhaseRegistry`. L'ordre canonique est défini dans `phase_registry.py`.
- **Ajouter un type de support** : créer un `SupportGenerator` (sous-classe de la
  base per-chapitre, + mixin évaluatif si corrigé séparé) + l'enregistrer dans
  `build_default_support_registry`, avec son prompt `pedagogy_<support>.j2` et son
  entité dans `domain/supports.py`.
- **Ajouter une fonctionnalité (onglet)** : enregistrer un `FeatureTab` + son type
  de réglages dans le `FeatureRegistry`, sans modifier `MainWindow` ni `Project`.
- **Ajouter un format d'export** : étendre `ExportFormat`, ajouter son extension
  (`markdown_pdf.EXTENSION_BY_FORMAT`) et son libellé (`ui/pedagogy_labels.EXPORT_LABELS`),
  brancher le rendu dans `app/document_export.write_documents` (+ l'adapter `infra/export/`
  correspondant) ; un format documentaire s'ajoute à `GENERATION_EXPORT_FORMATS` pour
  être proposé en génération.
- **Changer le retriever de glossaire** : implémenter `GlossaryRetriever`
  (Protocol) — actuellement TF-IDF, demain peut-être embeddings.
- **Migrer le schéma SQLite** : créer `core/migrations/vXX_to_vYY.py` et
  enregistrer dans le `MigrationRunner` chaîné.
