# Fahmi2 — Technical overview

## 1. Stack and platform

| Component | Choice |
|-----------|--------|
| **Target OS** | Windows 11 (10 minimum), single user |
| **Language** | Python 3.11 or 3.12 |
| **UI** | PySide6 (Qt 6) — native windowed application |
| **Local STT** | faster-whisper 1.x (configurable model, default `large-v3-turbo`, CUDA) |
| **Cloud STT** | OpenAI Transcribe (configurable model, default `whisper-1`) via the official SDK |
| **LLM** | DeepSeek v4 Flash / Pro via the OpenAI-compatible SDK |
| **Audio** | ffmpeg-python (wrapper) + bundled ffmpeg binary |
| **Retrieval** | scikit-learn (TF-IDF + cosine similarity) |
| **Templates** | Jinja2 (configurable prompts) |
| **Storage** | SQLite (WAL mode) + Markdown / JSON files |
| **Secrets** | Windows DPAPI (`win32crypt.CryptProtectData`) |
| **i18n** | Native Qt translation stack (`QTranslator` + `.ts`/`.qm` via `pyside6-lupdate` / `pyside6-lrelease`) |
| **Tests** | pytest, pytest-qt, pytest-cov |
| **Lint/types** | ruff (formatter + linter), mypy `--strict` |
| **Packaging** | PyInstaller `--onedir`, portable `.zip` |

## 2. Layered architecture

```
┌────────────────────────────────────────────────────────────────────┐
│                          UI (PySide6 — MVVM)                       │
│  MainWindow  ProjectsSidebar  CostMatrixView  LogsDock  Dialogs    │
└─────────────────────────────┬──────────────────────────────────────┘
                              │ Qt signals, ViewModels (Qt-free)
┌─────────────────────────────▼──────────────────────────────────────┐
│                       Application (use cases)                      │
│   ProjectService · RunOrchestrator · CostEstimator                 │
│   SupportsOrchestrator · SecretsService · HardwareProbe            │
│   ThemeController · LanguageController                             │
└────┬──────────┬───────────┬──────────────┬───────────┬─────────────┘
     │          │           │              │           │
     ▼          ▼           ▼              ▼           ▼
┌────────┐ ┌─────────┐ ┌─────────┐  ┌────────────┐ ┌─────────┐
│ Domain │ │Pipeline │ │  Infra  │  │   Core     │ │  i18n   │
│ pure   │ │ Engine  │ │ stt/llm │  │ log/retry/ │ │ AppLang │
│ models │ │+8 hand- │ │ ffmpeg/ │  │ errors/cfg │ │ install │
│        │ │ lers    │ │ sqlite/ │  │            │ │ .ts/.qm │
│        │ │         │ │ dpapi/  │  │            │ │         │
│        │ │         │ │ prompts │  │            │ │         │
└────────┘ └─────────┘ └─────────┘  └────────────┘ └─────────┘
```

### 2.1 `core` layer

Cross-cutting modules, with no external dependency (no Qt, HTTP, or SQL):

- `core/logging` — structured `LogEvent`, abstract `LogSink`,
  `JsonlFileSink`, global redaction of registered secrets.
- `core/errors` — `Fahmi2Error` hierarchy (TransientError, PermanentError,
  STTError, LLMError, FFmpegError, StorageError, ConfigError, …),
  serialisable `ErrorInfo`, registry of localised messages (FR + EN).
- `core/retry` — `RetryPolicy` (bounded exponential + jitter), `with_retry`
  runner with an injectable classifier.
- `core/concurrency` — `map_bounded` (bounded thread pool, *fail-fast*,
  result order preserved, honours the `PauseToken`); shared primitive used
  by the generation engine and the pedagogy orchestrator to parallelise
  I/O-bound calls (LLM, cloud STT).
- `core/config` — `AppPaths` (resolves Windows APPDATA / LOCALAPPDATA),
  `AppConfig`, runtime resolver for bundled `ffmpeg` (PyInstaller
  `_MEIPASS`).
- `core/migrations` — generic forward-only `MigrationRunner`,
  `v01_baseline`.
- `core/retrieval` — `GlossaryRetriever` Protocol, `PassthroughRetriever`,
  `TfidfGlossaryRetriever`.
- `core/ids` — ULID wrappers (`new_ulid`, `parse_ulid`, `ulid_to_datetime`).

### 2.2 `domain` layer

Pure immutable entities + state machines:

- Enums: `Language` (7 languages: fr/en/de/es/it/zh/ar), `StylePreset`,
  `PhaseId` (8 phases), `RunStatus`, `PhaseStatus`, `SourceKind`
  (video/audio/document/YouTube), `SttProvider`, `LLMModel`,
  `ReasoningEffort`, and pedagogy: `SupportType` (×8), `TargetAudience`,
  `BloomObjective`, `SupportDensity`, `ExportFormat`.
- Typed IDs: `ProjectId`, `RunId`, `SourceId` (via `_UlidIdBase`).
- Entities: `Term`, `Glossary`, `PhaseConfig`, `PhaseExecution`,
  `InputSource` (polymorphic source: local file or URL), `SourceExecution`,
  `Run`, `Project` (minimal identity: name + location + per-feature
  settings `generation`/`pedagogy`), `GenerationSettings`,
  `ParallelismConfig`, `PedagogySettings`, and support entities
  (`Flashcard`, `QcmItem`, `TrueFalseItem`, `ClozeItem`, `OpenQuestion`,
  `RevisionSheet`, `KeyPoints`, `MockExam`/`MockExamSection`,
  `SupportArtifact`).
- Exhaustive validations in `__post_init__` (`output_languages` contains
  `source_language`, `phases_config` covers exactly the LLM phases,
  `separate_correction` ⊆ selected evaluative materials, `correct_index`
  valid, etc.).
- The `projects.settings_json` blob is in **v2** (`{version,
  workspace_folder, generation, pedagogy}`) with *lenient* v1→v2 migration
  on read.
- `state_machine.py`: `validate_transition_run`, `validate_transition_phase`
  with immutable transition tables.

### 2.3 `pipeline` layer

Pure execution engine:

- Thread-safe `PauseToken` (request_pause/resume/cancel).
- In-memory `EventBus` + event types (`RunStarted`, `PhaseStarted`,
  `PhaseProgress`, `PhaseFinished`, `RetryAttempt`, `RunFinished`).
- `PhaseHandler` ABC + `PhaseContext` (full DI); `max_parallel_workers(ctx)`
  declares the phase's pool (default 1 = sequential; overridden by
  independent per-source phases).
- `PhaseRegistry` (canonical order of the 8 phases).
- `PipelineEngine` — execution loop with SQLite checkpoint, retry policy,
  events, pause/cancel. **Per-source** phases are parallelised via
  `core/concurrency/map_bounded` (pool bounded by `ParallelismConfig`:
  cloud STT = `stt_cloud_workers`, LLM phases 1/3/4 = `llm_workers`; local
  STT = 1, single GPU). Batch phases 5/6/7 parallelise their internal loops
  (per-source summaries, language × document, languages); barriers at batch
  phases 2 and 5.
- 8 handlers in `pipeline/handlers/` (one file per phase).
- `pipeline/handlers/_base.py` — common helpers (invoke LLM, parse JSON,
  build `PhaseExecution` succeeded, top-K glossary selection).
- **Phase 5 = consolidation strategy dispatcher**
  (`pipeline/handlers/_consolidation/`) based on
  `GenerationSettings.consolidation_mode`: `_base.py` (ABC
  `ConsolidationStrategy` + `ConsolidationResult` + deterministic shared
  helpers: renumbering, table of contents, assembly), `ordered.py` (1
  source = 1 chapter, content copied — historical behaviour), `thematic.py`
  (cross-cutting thematic rewrite as **map-reduce with provenance**:
  per-source factual ledger → thematic plan → per-chapter writing → meta;
  deterministic dual coverage check; no technical identifier in the
  deliverable; intra-phase resume via coherence hash; `consolidation/`
  artefacts).

### 2.4 `pedagogy` layer

Engine for generating the **revision materials** (modelled after
`pipeline`, but with a dedicated lightweight orchestrator — no STT/ffmpeg
or SQLite state):

- `pedagogy/support_generator.py` — `SupportGenerator` (ABC) +
  `SupportContext` (DI).
- `pedagogy/support_registry.py` — `SupportGeneratorRegistry` (canonical
  order of the 8 materials); `pedagogy/default_registry.py` —
  `build_default_support_registry()`.
- `pedagogy/sources.py` — source path / mtime / chapters (the chapter parser
  itself now lives in the shared `core/corpus/structure.py`, see the
  Visualizations section below).
- `pedagogy/events.py` — events (`SupportGenerationStarted`,
  `SupportStarted`, `SupportRetryAttempt`, `SupportFinished`,
  `SupportGenerationFinished`).
- `pedagogy/manifest.py` — freshness manifest (`pedagogy/manifest.json`:
  settings hash + per-language source mtime) → *coarse* resume + staleness.
- `pedagogy/artifact_writer.py` / `artifact_reader.py` —
  (de)serialisation of artefacts (JSON + Markdown) and paths.
- `pedagogy/generators/` — `_base.py` (LLM invocation with retry + typed
  JSON parsing helpers; generic per-chapter base + evaluative mixin) + 8
  LLM generators (concept flashcards, MCQs + bias mitigation, true/false,
  cloze, open questions, summary sheet, key points, mock exam).
- `pedagogy/labels.py` — **French source** labels (audience, Bloom,
  density, language, glossary) used in the LLM prompts. Their UI-localised
  counterparts live in `ui/pedagogy_labels.audience_display_label()` /
  `bloom_display_label()` / `density_display_label()` (rule of thumb: the
  domain prompts stay in French because the LLM prompt design is tuned for
  it; the UI translates the same labels independently).

### 2.5 `infra` layer

External adapters (ports/adapters):

- `infra/audio/ffmpeg_extractor.py` — `FFmpegExtractor` (subprocess with
  ffprobe audio-track pre-check).
- `infra/audio/cloud_audio_preparer.py` — `CloudAudioPreparer` (Opus
  compression + silence chunking): prepares audio for cloud STT under
  OpenAI Whisper's 25 MB limit. Injected into `OpenAIWhisperAdapter`.
- `infra/stt/` — `STTProvider` interface, `FakeSTTProvider`,
  `FasterWhisperAdapter` (configurable local model, downloaded at first
  use), `OpenAIWhisperAdapter` (configurable cloud model; `verbose_json`
  for `whisper-1`, otherwise `json` → single segment per chunk),
  `_pricing` module (USD/min per cloud model, shared with the
  `CostEstimator`).
- `infra/ingestion/` — polymorphic source routing (phase 0): `SourceKind →
  SourceIngestor` dispatcher (modelled after `PhaseRegistry`), `classify`
  (extension → type mapping), `MediaIngestor` (video/audio: ffmpeg + STT;
  with the per-source slide-analysis option on, runs the `SlideAnalyzer`
  after STT and merges the result via `slide_merge`), `DocumentIngestor`
  (pdf/docx/md/txt → single-segment transcription via `TextExtractor`),
  `YoutubeIngestor` + `YtDlpDownloader` (yt-dlp binary; downloads the
  **≤ 720p progressive video** instead of audio-only when slide analysis
  is on), `slide_merge` (pure function interleaving timestamped
  `[Slide affichée de mm:ss à mm:ss] …` segments into the transcription).
- `infra/video/` — **slide detection** (no vision calls): `frame_extractor`
  (`SlideFrameExtractor`: one ffmpeg pass, 1 frame / 2 s, longest side
  ≤ 1280 px) + `tiles`/`grouping` (pure tile-dHash two-pass grouping —
  per-video temporal-noise mask + dynamic region, scale-free change
  fraction with a recall-biased threshold, transition-fade coalescing,
  re-displayed-slide dedup by content, per-video caps) + `_constants`
  (every detection knob) + `_fakes` (`FakeSlideFrameExtractor`).
- `infra/vision/` — slide reading (ports/adapters): `SlideVisionProvider`
  port + `OpenAIVisionAdapter` (JSON mode `{texte, visuels}`, per-call
  cost, typed retryable errors) + `_pricing` (USD/token per `VisionModel`
  + per-slide estimate) + `SlideAnalyzer` façade (vision calls
  parallelised via `map_bounded`, **globally** bounded by `llm_workers`
  across parallel sources, per-source cost/warning accounting, frames
  cleanup or `slide_NNN.jpg` retention) + `_fakes`.
- `infra/llm/` — `LLMProvider` interface, `FakeLLMProvider`,
  `DeepSeekAdapter`, `_pricing` module, generalised `invocation.py`
  helpers (`invoke_llm_chat`, `parse_llm_json`).
- `infra/storage/sqlite_state.py` — `SqliteState` in WAL mode, 1 connection
  per thread, `busy_timeout`, SQLITE_BUSY retry.
- `infra/storage/fs_artifacts.py` — `FsArtifactStore` (atomic `.tmp` write
  + rename).
- `infra/secrets/` — `SecretsStore` Protocol, `InMemorySecretsStore`,
  `DPAPISecretsStore` (Windows).
- `infra/prompts/` — `PromptLoader` with `%APPDATA%/Fahmi2/prompts/`
  override + **bundled Jinja2 templates**: 8 generation phases +
  **`phase_0_slide_analysis`** (content-focused slide reading) + **3
  `phase_5_*` thematic-mode** + **`phase_6_glossary_localization`**
  (glossary term localisation) + 8 `pedagogy_*` + 3 `chat_*` + **5 `visuals_*`**
  (`visuals_graph_extraction`, `visuals_community_report`, `visuals_idea_chains`,
  `visuals_diagram_authoring`, `visuals_label_translation`).
- `infra/anki/genanki_exporter.py` — `.apkg` export (genanki: Basic/Cloze/
  MCQ, stable GUIDs, sub-decks per material, tags).
- `infra/export/markdown_pdf.py` — Markdown → HTML
  (`render_markdown_body`, shared) → PDF rendering via
  `xhtml2pdf`/ReportLab; **system fonts per language** (Arial for
  Latin/Arabic, Microsoft YaHei for Chinese, RTL + Arabic reshaping). Two
  PDF-rendering fixes: removal of characters **with no glyph** (emojis →
  white squares otherwise; `_strip_unrenderable_for_pdf`) and **pre-broken
  Chinese line wrapping** (`_prewrap_cjk_runs` via
  `wordSplit`/BeautifulSoup; `-pdf-word-wrap: CJK` CSS rule for cells) —
  reserved to CJK languages / PDF (HTML and Word handle them natively).
- `infra/export/markdown_docx.py` — Markdown → HTML → **DOCX** via
  `htmldocx` (relies on `python-docx`); tables reformatted (**Table
  Grid** style + 100 % width, since htmldocx translates neither the CSS
  borders nor `width:100%`); optional **landscape** orientation
  (glossary); **right-to-left Arabic** (`w:bidi` on paragraphs, `w:rtl`
  on runs, `w:bidiVisual` on tables), aligned with PDF/HTML. Word
  natively handles the CJK font and line breaks (nothing to declare for
  Chinese).

### 2.6 `app` layer

Application services:

- `ProjectService` — project CRUD (+ `get_last_completed_run`). Deletion
  removes the entry + its runs from the database **and** the project
  workspace folder on disk (best effort); the input folder (sources) and
  the global database (`%APPDATA%/Fahmi2/projects.db`) are not touched.
- `RunOrchestrator` — Run lifecycle (creation + source collection,
  execution via `PipelineEngine`, persistence, pause/cancel/resume).
- `SupportsOrchestrator` — dedicated orchestrator for revision materials
  (inputs per language, **parallelises support × language units** via
  `core/concurrency/map_bounded` bounded by `PedagogySettings.llm_workers`,
  JSON + Markdown writes, *coarse* resume via manifest under a lock,
  events, *best-effort* cost cap in parallel mode).
- `input_sources.build_input_sources` — collects sources (video/audio/
  document files from the folder + YouTube links), applies the order
  (`source_order`) and exclusion (`excluded_sources`) via
  `reconcile_source_order`.
- `CostEstimator` — pre-run heuristic for STT + LLM per phase and
  language. Accepts an optional `phases_config` and applies an empirical
  multiplier on `completion_tokens` according to `thinking_enabled` and
  `reasoning_effort` (×1 / ×2.5 / ×3.5 HIGH / ×6 MAX). Because DeepSeek's
  reasoning tokens are billed at the standard output rate, this multiplier
  directly reflects the observed surcharge. Heuristics shared in
  `app/_cost_common.py`.
- `PedagogyCostEstimator` — cost estimate for materials (per material ×
  language × chapter, depending on density and thinking).
- `pedagogy_export` / `generation_export` — collectors
  (`collect_*_documents`) + export façades (`export_pedagogy_to_apkg` for
  Anki; `export_*_documents` for Markdown / PDF / HTML / DOCX, delegated
  to the shared core `document_export.write_documents`).
- Glossary: no dedicated application service — it is read **from disk**
  (`glossary_master.json`) like the pipeline; parsing
  (`parse_glossary_master_terms`), 4-column Markdown rendering
  (`render_glossary_markdown_table`: per-language localised headers among
  the 7 — e.g. Terme / Acronyme / Signification / Définition or Term /
  Acronym / Meaning / Definition) and **term localisation**
  (`localize_glossary_terms` → `cross_lang[L]` carrying **term +
  definition** via `LocalizedTerm`, fallback on the source) live in
  `domain/glossary.py` (reused by pipeline, pedagogy, and Dialogue).
  **Phase 6** localises the terms through a structured LLM call
  (`_localize_glossary`, `phase_6_glossary_localization` prompt), renders
  `glossary.{L}.md` deterministically, injects the source → target
  equivalents into translation and persists `cross_lang` into
  `glossary_master.json`; Pedagogy and Dialogue then **pre-localise** the
  glossary to the content language they load.
- `PromptsService` — manages user overrides of LLM templates (read bundled
  default, read / write / delete override under `%APPDATA%/Fahmi2/
  prompts/`, Jinja2 validation). Backend for the `PromptsEditorDialog`.
  Catalogue: generation prompts (8 phases + 3 thematic `phase_5_*` +
  `phase_6_glossary_localization`) + 8 `pedagogy_*` templates + 3
  `chat_*` + 5 `visuals_*` templates.
- `SecretsService` — `SecretsStore` wrapper with automatic log
  redaction.
- `HardwareProbe` — CUDA/GPU detection at startup.
- `ThemeController` — reads the appearance preference (`UiPreferences` in
  `%APPDATA%/Fahmi2/ui_prefs.json`), applies the theme at startup, listens
  for system-theme changes (`SYSTEM` mode only) and exposes `set_mode` for
  the settings screens (immediate application + best-effort persistence).
- `LanguageController` — strict mirror of `ThemeController` for the UI
  language. Reads the `language: AppLanguage` preference from
  `ui_prefs.json`, installs the corresponding `QTranslator` at startup,
  exposes `set_language` (which persists the choice). Language changes
  take effect at the **next launch** (Qt does not propagate
  `LanguageChange` to strings already rendered through `tr()` at widget
  construction time, and rebuilding the whole tree would be fragile).

### 2.7 `ui` layer

Qt PySide6:

- `ui/theme/` — global design system with **Light Fluent**
  (`light_fluent.qss`) **and a mirror Dark mode** (`dark_fluent.qss`). The
  tokens (palettes + shadow spec + the `ThemeMode { SYSTEM, LIGHT, DARK }`
  enum) are centralised in `theme/_tokens.py`. Theme selection goes
  through `apply_theme(app, mode)`; `SYSTEM` is resolved via
  `QStyleHints.colorScheme()` (follows the OS theme). Light keeps the
  accent `#0078d4`, white surfaces on `#f5f7fb` background; dark shifts
  the accent to `#4aa3ee` (brightness bump), `#1a1f27` surfaces on
  `#11151c` background. Both sheets expose **exactly** the same set of
  selectors (guarded by `tests/unit/ui/test_theme_sync.py`) so that no
  widget ends up unstyled after switching. `QCheckBox::indicator` is
  styled (✓ inline SVG glyph as data URL). The QSS files are bundled
  through the PyInstaller `.spec` to stay accessible in packaged mode.
- `ui/_components.py` — shared assembly bricks (`card`, `page_header`,
  `field_hint`, `section_label`, `horizontal_separator`, `install_shadow`,
  `reapply_card_shadows`, **`localize_button_box`** — the i18n-aware
  successor of `frenchify_button_box`, which translates standard Qt
  buttons (`Cancel` → "Annuler"/"Cancel"…) by going through
  `QCoreApplication.translate("StandardButtons", …)`). Card shadows are
  carried by a Python `QGraphicsDropShadowEffect` (QSS does not support
  `box-shadow`) — `reapply_card_shadows` re-installs the shadows with the
  active-theme colour after each switch.
- `ui/viewmodels/` — logic testable without Qt:
  - `cost_matrix` — **generic** presentation viewmodel
    (`CostMatrixSnapshot`: `status + cost` cells, row/column/grand totals)
    shared by both dashboards (`build_cost_matrix`).
  - `RunMatrixViewModel` — produces a `CostMatrixSnapshot` (sources ×
    phases, per-cell cost via `list_phase_cells`, batch phase cost as
    column total). Phase labels and statuses are translated to the active
    UI language through `QCoreApplication.translate("RunMatrix", …)`.
  - `StatsStripViewModel` enriched with `started_at`, `finished_at`,
    `elapsed_seconds` to drive the live Duration card.
  - `PedagogyProgressViewModel` (event accumulation per support × language;
    `cost_matrix_snapshot` + `stats_snapshot`) and `PedagogyStateViewModel`
    (freshness: not configured / generation required / ready / up to date
    / stale; status messages translated through
    `QCoreApplication.translate("PedagogyState", …)`).
- `ui/widgets/` :
  - `StatCard` — reusable indicator card (icon + value + sub-info +
    accent), the building block of both dashboards' stats strips.
  - `StatsStripWidget` — 6 cards (Status, Sources, Phases, Languages,
    Duration, Cost) built on top of `StatCard`, with an internal `QTimer`
    (1 s) that refreshes the Duration card while the Run is `RUNNING` or
    `PAUSED`.
  - `CostMatrixView` — **generic** cost matrix (`QTableView` + delegate):
    prominent status glyph + secondary cost per cell, highlighted totals.
    Shared by the Generation (sources × phases) and Pedagogy (materials ×
    languages) dashboards. Status labels and accents are shared in
    `ui/status_labels`.
  - `PedagogyProgressView` — freshness banner + stats strip + `CostMatrixView`.
  - `ProjectsSidebar` — project list with **aggregated status dot** (worst
    of generation/pedagogy statuses) + bold name + status sub-label
    (`ProjectListEntry`, `update_statuses` for live refresh without losing
    the selection); right-click context menu Edit / Delete
    (`contextMenuEvent` uses `viewport().mapFromGlobal()` to stay
    insensitive to QSS padding).
  - `LogsDock` — HTML rendering coloured by severity; the "Minimum level"
    filter re-filters the existing display (all events are kept).
  - `ProjectHeaderBar` — buttons typed `primary` / `default` / `danger`
    via a QSS property, **"💵 Estimate cost"** button, **"📂 Output
    folder"** button, **optional "📦 Export"** button, and **"↺ Reset"**
    button (per-feature reset, disabled during a run; configurable
    tooltips; reused by both tabs).
  - `PhaseConfigsWidget` — per-phase LLM configuration grid (thinking,
    reasoning_effort HIGH / MAX, temperature, max retries).
  - `_chat_bubble` — chat bubbles with rounded corners (custom `QPainter`
    painting since `QTextBrowser` does not support `border-radius`);
    user/assistant alignment, clickable inline citations.
  - `chat_view` — Dialogue tab view (passive): conversation list, language
    selector, message thread (`ChatThread`), input + Send button,
    cumulative cost.
- `ui/dialogs/` — `NewProjectDialog` (minimal: name + location),
  `GenerationSettingsView` (master-detail generation settings),
  `PedagogySettingsView` (master-detail pedagogy settings: Materials /
  Difficulty / Languages / Model & cost), **`GlobalSettingsDialog`** (3
  cards: API keys, Appearance, **Language** — combo Français / English
  with restart-required hint),
  **`PromptsEditorDialog`** (sidebar splitter + monospace editor, Save
  with Jinja2 validation, Reset to default).
- `ui/main_window.py` — projects sidebar + `QTabWidget` of feature tabs
  (populated by a `FeatureRegistry`) + Edit menu → *Global settings…* /
  *Edit prompts…*.
- `ui/generation_controller.py` — orchestrates the Generation tab Run
  lifecycle (decoupled from `MainWindow`: receives the header/stats/matrix/
  logs; QThread worker, pause/resume/cancel via `PauseToken`,
  **`estimate_cost`** and **`open_generation_settings`** slots, every
  user-facing `QMessageBox` translated via
  `QCoreApplication.translate("GenerationController", …)`).
- `ui/pedagogy_controller.py` — orchestrates the Revision materials tab
  (`SupportsOrchestrator` QThread worker, pause/cancel, Anki / Markdown /
  PDF / HTML / DOCX export picker, `PedagogyQtEventBus` bridge,
  user-facing `QMessageBox`es translated via
  `QCoreApplication.translate("PedagogyController", …)`).
- `ui/chat_controller.py` — orchestrates the Dialogue tab (corpus
  loading, retriever building, streaming worker, conversation
  persistence). User-facing `QMessageBox`es translated via
  `QCoreApplication.translate("ChatController", …)`.
- `ui/features/` — tab abstraction: `FeatureId`, `FeatureTab`,
  `FeatureRegistry`, `GenerationTab` (cockpit + controller),
  `PedagogyTab` (pedagogy cockpit + `PedagogyController`), `ChatTab`
  (Dialogue + `ChatController`).
- `ui/qt_event_bus.py` — EventBus → Qt Signal adapters (`QtEventBus` for
  generation, `PedagogyQtEventBus` for pedagogy; worker → UI thread
  bridging).
- `ui/app_main.py` — entry point + full DI (`LanguageController` is
  installed **before** widget construction so that `self.tr()` resolves
  to the active language; `ThemeController` then reads the appearance
  preference and applies the theme; feature tabs are registered via
  `FeatureRegistry`).

### 2.8 `i18n` layer

Native Qt translation stack:

- `fahmi2/i18n/languages.py` — **pure Python** module (no Qt
  dependency): `AppLanguage` enum (`FR`, `EN`), `LANGUAGE_LABELS`
  (native labels, "Français" / "English"), `DEFAULT_LANGUAGE`.
  Importable by `ui_preferences` without pulling `QTranslator`.
- `fahmi2/i18n/__init__.py` — Qt-aware functions:
  - `bundled_translations_dir() → Path` — resolves the `.qm` folder in
    dev (next to the package) or packaged mode (via `sys._MEIPASS`).
  - `install_translator(app, language, dir)` — installs the matching
    `QTranslator`, cleans up the previous one via
    `setParent(None) + deleteLater()` (avoids a memory-corruption pattern
    seen in long test sessions), aligns `QLocale.setDefault(...)` for
    standard widgets.
  - Module-level `_ACTIVE_TRANSLATORS: dict[int, QTranslator]` cache
    indexed by `id(app)`.
- `fahmi2/i18n/translations/fahmi2_<code>.ts` — editable XML translation
  sources, versioned.
- `fahmi2/i18n/compiled/fahmi2_<code>.qm` — binary compiled files
  (`.gitignore`), regenerated by `scripts/i18n_compile.py`, bundled at
  build through `packaging/fahmi2.spec` (`datas`).

UI strings go through `self.tr(...)` (in `QObject` instances) or
`QCoreApplication.translate("Context", "literal source")` (in free
functions / module-level constants, with `QT_TRANSLATE_NOOP` for
extraction marking when resolution is deferred).

**Migration state (covered by ~60 parametric tests)**: 485 strings,
≥ 28 Linguist contexts (MainWindow, GlobalSettingsDialog,
NewProjectDialog, GenerationSettingsView, PedagogySettingsView,
ChatSettingsView, PromptsEditorDialog, CostEstimateDialog,
PhaseConfigsWidget, SourceOrderView, ProjectsSidebar, ProjectHeaderBar,
StatsStripWidget, StatusLabels, LogsDock, ChatTab, GenerationTab,
PedagogyTab, ChatView, ChatBubble, CostMatrix, PedagogyProgressView,
ChatController, GenerationController, PedagogyController, ExportUI,
RunMatrix, PedagogyState, ModelLabels, PedagogyLabels, StandardButtons,
FsHelpers, …).

### 2.9 Dialogue feature (chat anchored on the corpus)

Cross-cutting (engine `chat/` + retrieval + embeddings + UI): a 3rd tab
(`FeatureId.CHAT`) where the user dialogues with the corpus produced by
Generation (consolidated document + glossary).

- `core/retrieval/passages.py` — `PassageRetriever` port +
  `TfidfPassageRetriever` (lexical, reuses scikit-learn); distinct from
  `GlossaryRetriever`.
- `chat/` (engine) — `corpus.py` (loading + per-section chunking +
  glossary), `prompt_builder.py` (system/history + numbered passages +
  history guard), `citations.py` (`resolve_citations`: rewrites the LLM
  `[§N]` markers into numbered clickable links `[[N]](anchor)` +
  `Citation`), `query_expander.py` (LLM rephrasing on demand when
  retrieval is weak), `retriever_factory.py` (`AUTO` resolution +
  fallback), `chat_service.py` (`answer` + `stream_answer`).
- `infra/embeddings/` — `EmbeddingProvider` port +
  `OpenAIEmbeddingProvider` (**configurable** model via `EmbeddingModel`,
  default `text-embedding-3-small`) + `_pricing` (USD/Mtok per model) +
  fake. The port exposes `consumed_cost_usd()` (cost aggregated into the
  Dialogue total). `infra/retrieval/semantic.py` —
  `SemanticPassageRetriever` (persisted `.npz` index + validity
  fingerprint including the model **+ consolidated AND glossary mtimes**,
  numpy cosine).
- `infra/llm` — **additive** `chat_stream` extension (port + DeepSeek +
  fake); `stream_options.include_usage` → exact streaming cost.
- `app/chat_conversation_store.py` — JSON persistence of conversations
  (`chat/conversations/*.json`); `ChatSettings` in the v2 project blob
  (`chat` key).
- `ui/` — `ChatTab`, `ChatController` (`QThread` worker that streams via
  signals), `ChatViewModel` (state machine, Qt-free), `ChatView` (bubble
  thread + clickable citations + cost), `ChatSettingsView`. **Corpus
  freshness**: `ChatController.refresh_corpus_if_stale()` re-derives the
  corpus when the consolidated document or the glossary has changed on
  disk (key = language + consolidated mtime + glossary mtime), called
  before each answer **and** on the generation `run_state_changed` signal
  → the Dialogue never cites a stale document.
  **Corpus language per conversation**: `Conversation.language` drives the
  language **read/cited and the answer language**; a selector (populated
  by `available_content_languages`) chooses it at conversation creation
  time (hidden if only one language was produced).
  `_resolve_content_language(project, target)` prefers the conversation
  language; the corpus, the injected glossary (pre-localised), and the
  `.npz` index (per language, lazy) follow.

Configurable **fidelity** (`chat_strict`/`chat_augmented` prompts);
**lexical** (offline) or **semantic** (OpenAI embeddings) retrieval,
`AUTO` strategy.

### 2.10 Visualizations feature (standalone interactive HTML)

Cross-cutting (engine `visuals/` + HTML renderers + UI): a 4th tab
(`FeatureId.VISUALS`) that turns a generated course into two fully
self-contained interactive HTML pages. **GraphRAG-lite**, modelled after the
Pedagogy feature (lightweight orchestrator, no `PipelineEngine`).

- `core/corpus/structure.py` — **shared** consolidated-structure parser
  (`parse_chapters` / `parse_sections`); `parse_sections` exposes a
  **language-invariant** `section_path` from the numeric heading prefix
  (reused by Pedagogy, Dialogue and Visualizations).
- `visuals/` (engine) — `sources.py` (consolidated doc → per-section
  `TextUnit`, fragmented past `MAX_UNIT_CHARS`; `available_visuals_languages`
  restricts to **Latin** `VISUALS_LANGUAGES`), `_constants.py` (all magic
  numbers: gleaning rounds, per-density node/diagram caps, **map-pruning
  ratios / cap / floor**, entity-merge cosine threshold, Louvain seed, excerpt
  length), `_excerpts.py` (`SectionIndex` for
  embedded source excerpts), `extractors/` (`graph_extractor` [glossary
  backbone + LLM semantic layer + **gleaning**], `entity_resolver` [embedding
  cosine merge + glossary spine + **AUTO** label-normalisation fallback],
  `community_reporter`, `idea_chains` [map-reduce over reports],
  `diagram_author` [typed diagrams], `label_translator`), `community.py`
  (`detect_communities`: networkx Louvain with fixed seed → deterministic),
  `_pruning.py` (`prune_knowledge_graph`: **density-driven map pruning** by
  edge-first selection — drops isolated nodes, keeps the most connected up to a
  per-density node budget, connectivity guaranteed by construction),
  `events.py`, `manifest.py` (per-language freshness **+ persisted per-livrable costs**:
  per-language localization + global structure costs, reconstructed for the persisted
  cost matrix).
- `infra/export/` — `knowledge_map_html.py` / `diagram_board_html.py`
  (deterministic typed-JSON → self-contained HTML); `_visuals_assets.py` reads
  and **inlines** the vendored **Cytoscape.js** core + extensions from
  `_assets/visuals/` (**no CDN**); `_assets/visuals/*` (vendored MIT libs +
  CSS + JS + HTML templates). The renderers embed a **per-deliverable storage key**
  (`fahmi2:visuals:<deliverable>:<lang>:<hash8>:v1`, content-hashed) and inline the shared
  **`_layout_store.js`** (localStorage wrapper with availability probe + `try/catch`); the
  map's fcose layout is **legibility-tuned** (`nodeDimensionsIncludeLabels`, spacing) and
  manual node positions **persist** (restored on reload, « Réinitialiser » reverts) on both
  deliverables. `storage/feature_run_state.py` — shared `run_state.json` model
  (pedagogy + visuals).
- `app/` — `VisualsOrchestrator` (extract structure **once** in a structure
  language → per-Latin-language localise + render, freshness manifest +
  `run_state`, best-effort cost cap). **Both phases are parallelised**: the
  structure extraction parallelises its per-unit / per-community LLM calls via
  `extractors/_base.map_units_with_progress` (bounded by `llm_workers`, honours the
  `PauseToken`, **order preserved → deterministic**) emitting
  `VisualsStructureProgress`; the per-language localise+render uses per-language
  `map_bounded`. `VisualsCostEstimator` (pre-run estimate, reuses `_cost_common`).
- `ui/` — `VisualsTab`, `VisualsController` (`QThread` worker +
  `VisualsQtEventBus`), `VisualsSettingsView` (deliverables / content / AI
  generation), `VisualsProgressView` (status grid + tiles), with a **Structure**
  column **before** the per-language columns (per-deliverable extraction status +
  `Graph N/total` tooltip + per-step logs),
  `VisualsProgressViewModel` / `VisualsStateViewModel` (Qt-free),
  `visuals_labels.py`. The sidebar gains a **third** status (Visualizations).
- Prompts: 5 `visuals_*` templates (graph extraction, community report,
  idea-chains, diagram authoring, label translation) editable from the
  PromptsEditor.

**Multilingual = structure extracted once + labels localised** (Latin-script
languages only: fr/en/de/es/it; Chinese & Arabic deliberately excluded).
**Zero rendering DSL** (no Mermaid): the LLM emits typed JSON only.

## 3. Main Run flow

```
[User clicks ▶ Run]
        │
        ▼
RunOrchestrator.create_run(project)
        │  ── source collection (build_input_sources: folder + URLs,
        │     ordered/excluded) — video/audio/document files + YouTube links
        │  ── Project + Run + SourceExecutions persistence
        ▼
RunOrchestrator.execute(run, ctx)
        │  ── delegates to PipelineEngine.execute(ctx)
        ▼
PipelineEngine loops over phases:
   for each PhaseHandler in canonical order:
     for each source (if per-source) or once (if batch):
        1. check PauseToken (raise if cancel, wait if pause)
        2. lookup SQLite checkpoint (skip if SUCCEEDED)
        3. emit PhaseStarted
        4. execute the handler with the retry policy
        5. persist PhaseExecution into SQLite (transaction)
        6. emit PhaseFinished
        │
        ▼
[Output: Markdown per source × languages, glossary × languages, consolidated × languages]
```

## 4. Data model

### 4.1 SQLite schema (v1)

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

CREATE TABLE sources (
  id TEXT PRIMARY KEY, run_id TEXT NOT NULL,
  source_kind TEXT NOT NULL DEFAULT 'video',
  source_location TEXT NOT NULL, detected_language TEXT,
  FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
);

CREATE TABLE phase_executions (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  run_id TEXT NOT NULL, phase_id TEXT NOT NULL, source_id TEXT,
  status TEXT NOT NULL,
  started_at TEXT, finished_at TEXT,
  artifact_path TEXT, retry_count INTEGER NOT NULL DEFAULT 0,
  cost_usd REAL NOT NULL DEFAULT 0,
  per_source_costs_json TEXT,  -- v1.5.1 (soft migration): {source_id: cost} for batch phases 5/6; NULL = no attribution
  error_json TEXT,
  UNIQUE (run_id, phase_id, source_id),
  FOREIGN KEY (run_id) REFERENCES runs(id) ON DELETE CASCADE
);
```

> No glossary-content table in the database: the glossary is a disk
> artefact (`glossary_master.json` + `glossary.{lang}.md`), like the other
> generated documents.

Indexes: `idx_runs_project_id`, `idx_sources_run_id`,
`idx_phase_executions_run`, `idx_phase_executions_lookup`.

**Soft migrations** applied automatically on open (idempotent, no data
loss):

- Removal of the `glossary_terms` table (`DROP TABLE IF EXISTS`): a
  baseline intent that never landed — the glossary is read from disk like
  the other generated documents.
- Retroactive cleanup of duplicate batch rows in `phase_executions` (rows
  with `source_id IS NULL` for the same `(run_id, phase_id)` — SQLite
  treats `NULL` as distinct in a `UNIQUE` constraint, which used to
  accumulate rows before the upsert handled the `NULL` case explicitly).
  Only the latest `id` per group is kept.

**`upsert_phase_execution`** now handles the two cases distinctly:

- `source_id` defined → `INSERT ... ON CONFLICT(run_id, phase_id,
  source_id) DO UPDATE`.
- `source_id IS NULL` (batch phases) → `DELETE FROM phase_executions
  WHERE run_id = ? AND phase_id = ? AND source_id IS NULL` then `INSERT`.
  That is the only reliable way to unify batch phases in SQLite.

### 4.2 Artefact tree (per project)

```
<workspace_folder>/
├── transcripts/{source_id}.json       ← Phase 0 STT (+ interleaved [Slide …] segments when slide analysis is on)
├── audio/{source_id}.wav              ← Extracted audio (deletable)
├── frames/{source_id}/slide_NNN.jpg   ← Kept slide images (only with « keep slide images » on; transient otherwise)
├── candidates/{source_id}.json        ← Phase 1
├── glossary_master.json              ← Phase 2
├── reformulated/{source_id}.md        ← Phase 3
├── structured/{source_id}.md          ← Phase 4
└── consolidated_master.md            ← Phase 5

<output_dir>/
├── consolidated.{lang}.md            ← Phases 6 + 7
├── glossary.{lang}.md
└── per-video/{lang}/{source_id}.md

<location>/pedagogy/                   ← Revision materials (SP2)
├── manifest.json                     ← Freshness (settings hash + source/language mtime)
└── {support}/{lang}/
    ├── {support}.json                ← Structured artefact (typed items)
    ├── {support}.md                  ← Markdown rendering (question)
    └── {support}.corrige.md          ← Separate answer key (evaluative, if requested)

<location>/visuals/                    ← Visualizations
├── manifest.json                     ← Per-language freshness (settings hash + structure/glossary/content mtime)
├── run_state.json                    ← Last execution status + cost (shared feature_run_state)
└── output/
    ├── knowledge_map.{lang}.html      ← Standalone interactive knowledge map (Latin langs only)
    └── diagrams.{lang}.html           ← Standalone generated-diagram gallery
```

> Revision materials are produced by `SupportsOrchestrator`
> (`app/supports_orchestrator.py`) — dedicated lightweight orchestrator,
> **not** the `PipelineEngine` — from the consolidated document (parsed into
> chapters; a **content language** is resolved among the existing
> `consolidated.{lang}.md`) and the glossary (read **from disk**:
> `glossary_master.json`, like the pipeline).
> **Idempotent** generation (overwrites) + **coarse** resume: a fresh
> material (unchanged settings hash + source mtime, artefact present) is
> *skipped*. The **8 materials** are produced **by the LLM** in the chosen
> **target language** (even when the source document is in another
> language).

> **LLM generators (SP2/03)**: concept flashcards, MCQs (with **deterministic
> bias mitigation** of the correct-answer position), true/false, cloze, open
> questions, summary sheet, key points (per chapter), and mock exam (whole
> document). Each has a `pedagogy_<support>.j2` **editable** prompt (Edit →
> Edit prompts), typed JSON parsing toward the entities in
> `domain/supports.py`, and a shared LLM retry with the pipeline
> (`core/retry/classification.default_classify`). Evaluative materials
> flagged "separate answer key" produce a `<support>.corrige.md` file
> distinct from the question file.

> **Anki export (SP3/01)**: the `infra/anki/genanki_exporter.py` adapter
> (`genanki` dependency) turns the materials into a `.apkg` package —
> `Flashcard` → Basic, `ClozeItem` → Cloze, `QcmItem` → custom note.
> **Stable GUIDs** (`genanki.guid_for`, re-import without duplicates),
> **sub-decks per material** (`<Project>::<material>`), **tags** (material
> / language / level / chapter). Artefact JSON deserialisation lives in
> `pedagogy/artifact_reader.py`; the `app/pedagogy_export.py` service scans
> `pedagogy/`. Non-card materials (true/false, open questions, summary
> sheet, key points, mock exam) fall under the Markdown/PDF/HTML/DOCX
> export. On Anki export, Markdown fields are converted to HTML
> (`genanki_exporter._md_to_html`), except cloze text.

> **Markdown/PDF/HTML/DOCX export**: the shared `app/document_export.py`
> core (`write_documents`) writes **one file per material and per answer
> key** (`<material>.{lang}.<ext>`, `<material>.{lang}.corrige.<ext>`)
> from the **already-rendered** Markdown. The HTML body is produced once
> by `markdown_pdf.render_markdown_body` (extensions `tables` + `toc`),
> reused by: HTML (self-contained document, embedded CSS); **PDF** via
> `xhtml2pdf` (ReportLab engine — real pagination, **system fonts per
> language**: Arial for Latin/Arabic, Microsoft YaHei for Chinese, RTL +
> Arabic reshaping; emoji-without-glyph stripping + CJK line-break
> pre-cut); **DOCX** via `markdown_docx` (htmldocx → python-docx; Word
> natively handles CJK and bidi; optional landscape). The
> `app/generation_export.py` and `app/pedagogy_export.py` services collect
> the documents (per language, the **glossary** in landscape); they reuse
> the rendered `.md`, **no** re-rendering (`artifact_reader` is reserved
> for Anki).

## 5. Code conventions

- **Style**: Google Python Style Guide, docstrings with `Args`,
  `Returns`, `Raises` sections.
- **Linting**: strict ruff (E, F, W, B, C90, N, UP, ANN, S, PL, I).
- **Type checker**: mypy `--strict`, zero error tolerated.
- **Magic constants**: centralised at the top of modules.
- **Private helpers**: `_method_name` prefix.
- **Internal modules**: `_` prefix (e.g. `_base.py`, `_pricing.py`,
  `_schema.sql`, `_fakes.py`).
- **Immutability**: domain entities `@dataclass(frozen=True)`, with-
  methods for modified copies (`with_status`, `with_added_cost`).
- **i18n source strings**: always in French (the project's source
  language). Marked through `self.tr()` (in `QObject` methods) or
  `QCoreApplication.translate("Context", "literal source")` (in free
  functions / module constants); never through a function wrapper
  (`pyside6-lupdate` does not follow wrappers).

## 6. Tests

### 6.1 Strategy per layer

| Layer | Test type | Coverage |
|-------|-----------|----------|
| `domain/` | pure unit | ~100 % |
| `core/` | unit | ~95 % |
| `pipeline/` | unit with fakes | ~95 % |
| `infra/` adapters | SDK mock + fixtures | ~90 % (real adapters tested manually) |
| `app/` | unit + integration | ~95 % |
| `ui/` viewmodels | unit (Qt-free) | ~95 % |
| `ui/` widgets | pytest-qt smoke | golden path |
| `i18n/` | parametric end-to-end (≥ 1 string per migrated context) | ~12 % of strings, 100 % of contexts |
| End-to-end | full run on fakes + real ffmpeg | 1 happy path + key errors |

### 6.2 Current metrics

- **1384 passing tests** × 3 consecutive runs
- **ruff** + **mypy --strict** clean over the whole `src` + `tests` tree

## 7. Packaging and distribution

- **PyInstaller `--onedir`**: fast startup, more antivirus-tolerant than
  `--onefile`.
- **ffmpeg automatically bundled**: `packaging/fetch-ffmpeg.ps1` downloads
  the binary and verifies the SHA-256; `packaging/build.ps1` calls it
  automatically before the build.
- **Whisper model not bundled**: downloaded on demand at the first run in
  local STT mode (otherwise never).
- **i18n `.qm` bundled**: `scripts/i18n_compile.py` must be run before
  `pyinstaller`; the `.spec` ships them via
  `("src/fahmi2/i18n/compiled/*.qm", "fahmi2/i18n/compiled")` in `datas`.
  Without that line the packaged app stays in French regardless of the
  user preference (silent fallback).
- **Portable `.zip`**: `packaging/make-portable-zip.ps1` produces
  `Fahmi2-<version>-win64.zip`.
- **Export dependencies**: `genanki` (Anki) inlines the schema as Python
  modules (nothing to collect); **PDF** relies on `xhtml2pdf`/`reportlab`
  (pure, `collect_all`); **DOCX** on `htmldocx` + `beautifulsoup4` (pure;
  `lxml` already pulled in by `python-docx`). PDF rendering uses **Windows
  system fonts** (Arial Latin/Arabic, Microsoft YaHei Chinese — no font to
  bundle). Details and procedure in
  [`packaging/README.md`](../packaging/README.md).
- **No code signing in v1**: a SmartScreen warning appears on the first
  launch (click "More info" → "Run anyway").

## 8. Security

- **Encrypted API keys** via Windows DPAPI (`CryptProtectData`), tied to
  the current Windows user.
- **No outbound telemetry**.
- **Offline mode possible** (local STT + cloud LLM, or the other way
  around).
- **Automatic redaction** of secret values in every log (global
  `register_secret` mechanism).
- **SmartScreen Mark-of-the-Web**: no bypass, the user keeps control.

## 9. Extensibility

The architecture is open to extensions without breaking the existing code:

- **Add a language**: add the value to `Language` (`domain/enums.py`), its
  label in `domain/languages._LANGUAGE_NAMES` (single source, prompts +
  UI), its glossary headers and title (`domain/glossary`), its STT
  detection aliases (`openai_whisper_adapter`); for PDF, add a font if the
  writing system requires it (CJK) and, for a right-to-left script,
  register it in `domain/languages._RTL_LANGUAGES` (single RTL source for
  PDF/HTML/DOCX; + `markdown_pdf._PDF_LANG_RENDERING` for reshaping).
  Tests to complete.
- **Add a UI language**: add the value to `AppLanguage`
  (`src/fahmi2/i18n/languages.py`) + its native label in
  `LANGUAGE_LABELS`; run `scripts/i18n_extract.py` to generate the `.ts`,
  translate it (Qt Linguist or any text editor), then run
  `scripts/i18n_compile.py`. No code change required beyond the enum.
- **Add an STT provider**: implement the `STTProvider` Protocol.
- **Add an LLM provider**: implement the `LLMProvider` Protocol + add a
  pricing grid in `_pricing.py`.
- **Add a phase**: create a `PhaseHandler` + register it in
  `PhaseRegistry`. The canonical order is defined in
  `phase_registry.py`.
- **Add a material type**: create a `SupportGenerator` (subclass of the
  per-chapter base, + evaluative mixin if a separate answer key is
  needed) + register it in `build_default_support_registry`, with its
  `pedagogy_<support>.j2` prompt and its entity in `domain/supports.py`.
- **Add a feature (tab)**: register a `FeatureTab` + its settings type in
  the `FeatureRegistry`, without modifying `MainWindow` or `Project`.
- **Add an export format**: extend `ExportFormat`, add its extension
  (`markdown_pdf.EXTENSION_BY_FORMAT`) and its label
  (`ui/pedagogy_labels.export_labels()`), wire the rendering in
  `app/document_export.write_documents` (+ the corresponding `infra/
  export/` adapter); a document format is added to
  `GENERATION_EXPORT_FORMATS` to be offered at generation time.
- **Change the glossary retriever**: implement `GlossaryRetriever`
  (Protocol) — currently TF-IDF, tomorrow perhaps embeddings.
- **Migrate the SQLite schema**: create `core/migrations/vXX_to_vYY.py`
  and register it in the chained `MigrationRunner`.
