# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Fahmi2 turns courses (videos, audio files, text documents — pdf/docx/md/txt
— **and** single YouTube links) into consolidated Markdown documents
(rephrased, structured, with a glossary) through a STT + 7 DeepSeek LLM
phase pipeline. Single-user Windows desktop application, PySide6, packaged
as a portable `.zip` (double-click installation, bundled ffmpeg).

**Supported languages** (input and output, for the 3 features): French,
English, German, Spanish, Italian, Chinese, Arabic (`Language`, 7 values).

The app is organised in **feature tabs** (Generation; Revision materials —
8 types of revision materials with Anki/Markdown/PDF/HTML/DOCX exports;
**Dialogue** — chat anchored on the corpus, cited answers + streaming,
lexical/semantic retrieval; **Visualizations** — two fully self-contained
interactive HTML deliverables, a knowledge map [typed concept/term/idea/example
graph] and a generated-diagram gallery, **Latin-script languages only**
fr/en/de/es/it): a `Project` only carries its name + location, the business
settings living per feature (`GenerationSettings`, `PedagogySettings`,
`ChatSettings`, `VisualsSettings`).

**Interface language**: French (source) or English. Picked from **Edit →
Global settings → Language**, persisted in `ui_prefs.json`; effective at
the next launch.

## Language and working conventions

- **All in French** in **code**: code comments, docstrings, **user-facing
  messages** (literal FR sources of `tr()` / `QCoreApplication.translate`),
  logs, **commit messages**. Perfect spelling with accents and diacritics
  (never ASCII substitutes). Code identifiers stay in their original form.
- **All in English** in **documentation**: `README.md`, `docs/`,
  `CHANGELOG.md`, `packaging/README.md`, this file. The session archives
  `docs/superpowers/specs/` and `docs/superpowers/plans/` stay in French.
- The English UI is provided by the **i18n stack** (Qt translators),
  rebuilt from the FR source via `scripts/i18n_extract.py` + `scripts/i18n_compile.py`.
- **Google Python Style Guide**: docstrings with `Args`, `Returns`,
  `Raises` sections; module-level docstring on every file.
- **Systematic end-of-task verification**: `pytest`, `ruff check .`,
  `mypy src tests` must all be clean before considering work finished. Run
  as many times as necessary until zero defects.
- Immutable domain entities (`@dataclass(frozen=True)`) + `with_*` methods
  for modified copies. Private helpers `_method`, internal modules
  `_module.py` (`_base.py`, `_pricing.py`, `_schema.sql`, `_fakes.py`).

## Commands

The venv interpreter is `.venv\Scripts\python.exe` (Python 3.12 — **not
3.13**, constraint `>=3.11,<3.13` in `pyproject.toml`). In PowerShell, it
can be activated via `.\.venv\Scripts\Activate.ps1`, but prefer calling
the exe directly.

```powershell
# Tests
.venv\Scripts\python.exe -m pytest                              # the whole suite
.venv\Scripts\python.exe -m pytest tests/unit/app               # one layer
.venv\Scripts\python.exe -m pytest tests/unit/app/test_x.py::test_name -v   # a single test
.venv\Scripts\python.exe -m pytest --cov=src/fahmi2 --cov-report=term-missing

# Quality (both must be clean)
.venv\Scripts\python.exe -m ruff check .
.venv\Scripts\python.exe -m mypy src tests

# Run the app in dev
.venv\Scripts\python.exe -m fahmi2.ui.app_main

# i18n — UI translations
.venv\Scripts\python.exe scripts\i18n_extract.py     # FR sources → .ts (Linguist)
.venv\Scripts\python.exe scripts\i18n_compile.py     # .ts → .qm (runtime)

# Build the Windows portable .zip (downloads ffmpeg, validates, builds with PyInstaller)
.\packaging\build.ps1
.\packaging\make-portable-zip.ps1
```

Windows note: git rewrites LF→CRLF (expected warnings, harmless). The
`packaging/fahmi2.spec` file is `.gitignore`d (`*.spec`) — modifying the
`.spec` to bundle new resources will not be versioned.

Export dependencies in the `.spec` (already wired, see
`packaging/fahmi2.spec`, gitignored): the PDF is rendered by **`xhtml2pdf`**
(engine **`reportlab`**, + `html5lib`, `pypdf`, `Pillow`, `svglib`,
`arabic-reshaper`, `python-bidi`, `pyHanko` — all pure Python) →
`collect_all('xhtml2pdf')` + `collect_all('reportlab')` (internal
data/fonts) + `collect_all('arabic_reshaper')`; `markdown` loads its
extensions by name → `collect_submodules('markdown')`. **`genanki` 0.13.1
inlines the schema in Python modules** (`apkg_col.py`/`apkg_schema.py`) —
**no data file to collect**, its modules are bundled by import analysis.
The **DOCX export** adds `htmldocx` (+ `beautifulsoup4`, `lxml` already
pulled by python-docx) → `hiddenimports += ['htmldocx']` +
`collect_submodules('bs4')`. **i18n** adds the compiled `.qm` files →
`datas += [("src/fahmi2/i18n/compiled/*.qm",
"fahmi2/i18n/compiled")]`. The PDF uses **system Windows fonts** (Arial
for Latin/Arabic, Microsoft YaHei for Chinese) — **nothing to bundle** on
the font side. Details in `packaging/README.md`.

## Layered architecture

Dependencies flow downwards (UI → app → pipeline/infra → domain/core).
`core` and `domain` import neither Qt, nor HTTP, nor SQL.

- `core/` — transverse: `errors` (`Fahmi2Error` hierarchy + serialisable
  `ErrorInfo` + FR messages), `retry` (`RetryPolicy` + `with_retry`),
  `logging` (JSONL + secrets redaction), `config/paths` (Windows
  `AppPaths` + runtime resolution of bundled ffmpeg), `migrations`,
  `retrieval` (TF-IDF glossary), `concurrency` (`map_bounded`: bounded
  pool, fail-fast, order preserved, honours the `PauseToken`; shared for
  parallelising I/O-bound LLM/STT calls; **`PauseToken`** — coopérative
  pause/cancel token consumed by `map_bounded`, orchestrators and UI
  controllers), `ids`, `slugify` (`slugify_anchor`: GFM anchor **single
  source** — consolidated TOC in generation, section/chapter parser,
  HTML export heading ids), `corpus` (`parse_chapters` / `parse_sections`:
  **shared consolidated-structure parser** for pedagogy / dialogue /
  visualisations; `parse_sections` exposes a **language-invariant**
  `section_path` derived from the numeric heading prefix).
- `domain/` — pure immutable entities (`Project` [minimal identity: name +
  location + per-feature settings], `GenerationSettings`,
  `PedagogySettings`, `Run`, `InputSource`, `SourceExecution`,
  `PhaseExecution`, `Term`, `Glossary`, support entities in `supports.py`:
  `Flashcard`, `QcmItem`, `TrueFalseItem`, `ClozeItem`, `OpenQuestion`,
  `RevisionSheet`, `KeyPoints`, `MockExam`, `SupportArtifact`), enums
  (generation + pedagogy: `SupportType`×8, `TargetAudience`,
  `BloomObjective`, `SupportDensity`, `ExportFormat`, `ReasoningEffort`),
  typed ULID ids, and **state machines** (`state_machine.py`) that
  validate Run and Phase transitions.
- `pipeline/` — pure execution engine for **generation**: `PipelineEngine`
  (per-phase SQLite checkpoint + retry + events + pause/cancel),
  `PhaseRegistry` (canonical order of the 8 phases),
  `PhaseHandler`/`PhaseContext` (DI), `EventBus` (generic),
  **`workspace_layout`** (single source of artifact paths:
  `transcripts/`, `candidates/`, `reformulated/`, `structured/`,
  `glossary_master.json`, `consolidated_master.md`, `per-video/`),
  `handlers/phase_N_*.py` (one per phase). The coopérative
  pause/cancel `PauseToken` lives in `core/concurrency/` since it is
  shared with `map_bounded` and the pedagogy orchestrator.
- `pedagogy/` — **revision materials** engine (modelled after `pipeline/`
  but without STT/SQLite): `SupportGenerator` (ABC) + `SupportContext` (DI),
  `SupportGeneratorRegistry` + `build_default_support_registry`,
  `sources` (consume `core/corpus`), `events`, `manifest` (freshness),
  `artifact_writer`/`artifact_reader`, `generators/` (`_base` per-chapter +
  evaluative mixin + 8 LLM generators: concept flashcards, MCQ,
  true/false, cloze, open questions, sheet, key points, mock exam),
  `labels` (FR-frozen, used in LLM prompts).
- `chat/` — **Dialogue** engine (RAG chat on corpus): `corpus` (loading +
  per-section chunking + glossary), `prompt_builder` (system/history +
  numbered passages + history guard), `citations` (`resolve_citations`:
  rewrites the LLM's `[§N]` markers as clickable numbered links
  `[[N]](anchor)`, `Citation` carrying the `number` of sequential display
  deduplicated by anchor), `query_expander` (LLM reformulation on demand),
  `retriever_factory` (`AUTO` resolution + fallback), `chat_service`
  (`answer`/`stream_answer`). Retrieval as ports: `PassageRetriever`
  (`core/retrieval`, lexical TF-IDF) + `EmbeddingProvider`
  (`infra/embeddings`, OpenAI, **configurable model** `EmbeddingModel` +
  `_pricing`) + `SemanticPassageRetriever` (`infra/retrieval`, `.npz`
  index + fingerprint including the model **+ mtime of the consolidated
  document AND glossary** → reindex on change). **Corpus freshness**:
  `ChatController.refresh_corpus_if_stale()` re-derives the corpus when
  the consolidated/glossary has changed on disk (key = language + 2
  mtimes), called before every answer **and** on the generation's
  `run_state_changed` signal → the Dialogue never cites a stale document
  after regeneration (without reloading the project). Streaming via
  `LLMProvider.chat_stream` (**additive** extension). **Exhaustive cost**:
  `consumed_cost_usd()` on retrieval/embedding ports aggregated into
  `ChatMessage.cost_usd`. Persisted conversations, **deletable**
  (`app/chat_conversation_store`); `ChatSettings` in the v2 blob.
  Citations/chunking bounded to the document outline (`##`/`###`).
  **Per-conversation corpus language**: `Conversation.language` drives the
  language **read/cited AND answered in**; a selector (populated by
  `pedagogy.sources.available_content_languages`) picks it at conversation
  creation (among the produced `consolidated.{lang}.md`; hidden if a
  single language; the side list **prefixes** each conversation by its
  language code, a conversation's language being **fixed**). The corpus,
  the injected glossary (pre-localised term + definition), and the `.npz`
  index (already **per language**, built **lazily**) follow;
  `_resolve_content_language(project, target)` prefers the conversation
  language, falls back to source then to the 1st produced one.
  **Known limitation (Chinese)**: the **lexical** TF-IDF retrieval
  tokenises on `\b\w+\b`, poorly suited to Chinese (no spaces between
  words) → prefer the **semantic** mode for Chinese (the `AUTO` default
  routes there as soon as an OpenAI key is present). Arabic (words
  separated by spaces) is not affected.
- `visuals/` — **Visualizations** engine (GraphRAG-lite, modelled after
  `pedagogy/` — lightweight orchestrator, no SQLite/STT): `sources`
  (`load_text_units`: consolidated doc → per-section `TextUnit` via
  `core/corpus.parse_sections`, fragmented past `MAX_UNIT_CHARS`;
  `available_visuals_languages` restricts to **Latin** `VISUALS_LANGUAGES`;
  `structure_language` / `outputs_present`), `_constants` (all magic numbers:
  gleaning rounds, per-density node/diagram caps, entity-merge cosine
  threshold, Louvain seed…), `_excerpts` (`SectionIndex` for embedded source
  excerpts), `extractors/` (`graph_extractor` [glossary backbone + LLM
  semantic layer + **gleaning** recall pass], `entity_resolver` [embedding
  cosine merge + glossary spine + **AUTO** label-normalisation fallback when
  no OpenAI key], `community_reporter`, `idea_chains` [map-reduce over
  community reports], `diagram_author` [typed diagram payloads], `label_translator`
  [localise graph/board labels — structure extracted **once**, labels
  translated per language]), `community` (`detect_communities`: networkx
  Louvain with fixed seed → deterministic; `assemble_graph`), `events`,
  `manifest` (per-language freshness: settings hash + structure/glossary/content
  mtimes). The **structure is extracted once** in a structure language, then
  each Latin language is a label-translation + render pass. **Zero rendering
  DSL** (no Mermaid): the LLM emits typed JSON only.
- `infra/` — adapters (ports/adapters): `stt/` (FasterWhisper local +
  OpenAI cloud + fakes; **per-provider configurable model**
  `LocalSttModel`/`CloudSttModel` + `_pricing` USD/min; cloud `gpt-4o-*`
  without timestamps → single segment), `embeddings/` (port
  `EmbeddingProvider` + OpenAI + `_pricing` + fakes), `retrieval/`
  (`SemanticPassageRetriever`), `llm/` (DeepSeek + `_pricing` +
  `invocation` + fakes; `max_tokens` at model ceiling + `finish_reason`
  anti-truncation guard), `audio/ffmpeg_extractor` +
  `cloud_audio_preparer` (Opus compression + silence-based splitting:
  crosses OpenAI Whisper's 25 MB limit, injected into the cloud STT
  adapter), `ingestion/` (dispatcher `source → transcription` injected in
  phase 0: `classify` [video/audio/document extensions] +
  `SourceIngestor` port + `MediaIngestor` [video+audio via ffmpeg+STT] +
  `DocumentIngestor` [pdf/docx/md/txt → transcription with a **single
  segment**, via `TextExtractor` pypdf/python-docx] + `YoutubeIngestor`
  [URL → `YtDlpDownloader` downloads the audio (resolved/replaceable
  yt-dlp binary) → delegates to `MediaIngestor`]),
  `anki/genanki_exporter` (`.apkg`), `export/markdown_pdf` (Markdown +
  HTML + PDF) + `export/markdown_docx` (DOCX via htmldocx, reuses
  `render_markdown_body`), `export/knowledge_map_html` + `export/diagram_board_html`
  (**Visualizations** renderers: deterministic typed-JSON → self-contained HTML;
  `_visuals_assets` reads + inlines the vendored Cytoscape libs from
  `_assets/visuals/`, **no CDN**), `storage/sqlite_state` (WAL) + `fs_artifacts`
  (atomic writes) + `feature_run_state` (shared pedagogy/visuals `run_state.json`),
  `secrets/` (Windows DPAPI), `prompts/loader` +
  `defaults/*.j2` (8 phases + 3 thematic `phase_5_*` + 8 `pedagogy_*` +
  3 `chat_*` + 5 `visuals_*`).
- `app/` — use-cases: `ProjectService` (+ `get_last_completed_run`;
  deleting a project also wipes its **workspace folder** on disk,
  best-effort, leaving the input folder and the global database alone),
  `RunOrchestrator`, `SupportsOrchestrator`, `VisualsOrchestrator` (Visualizations:
  extract structure once → per-Latin-language localise + render, freshness
  manifest + `run_state`, best-effort cost cap; **both the structure extraction
  (graph/diagrams/community-reports, via `map_units_with_progress` →
  `map_bounded(llm_workers)`, emitting `VisualsStructureProgress`) and the
  per-language localise/render are parallelised**),
  `CostEstimator`, `PedagogyCostEstimator`, `VisualsCostEstimator`,
  `pedagogy_export` (Anki/MD/PDF/HTML/DOCX) +
  `generation_export` (consolidated + glossary MD/PDF/HTML/DOCX) on the
  shared `document_export` core, `_cost_common`, `PromptsService`,
  `SecretsService`, `input_sources` (`build_input_sources`: video+audio
  folder scan → `SourceExecution`), `HardwareProbe`,
  `LanguageController` (mirror of `ThemeController`: reads/persists the
  interface language in `%APPDATA%/Fahmi2/ui_prefs.json`, installs the
  `QTranslator` **before** widget construction). (The glossary is read
  from disk — `glossary_master.json` — like the pipeline; parsing/rendering
  in `domain/glossary`, no dedicated service.)
- `ui/` — PySide6: `features/` (tab abstraction: `FeatureId`, `FeatureTab`,
  `FeatureRegistry`, `GenerationTab`, real `PedagogyTab`, `VisualsTab`),
  `viewmodels/` (logic testable **without Qt**, including
  `PedagogyProgressViewModel` / `PedagogyStateViewModel` /
  `VisualsProgressViewModel` / `VisualsStateViewModel`), `widgets/` (including
  reusable master-detail `SettingsView`, `PedagogyProgressView`,
  `VisualsProgressView`), `dialogs/` (including
  `GenerationSettingsView`, `PedagogySettingsView`, `VisualsSettingsView`),
  `theme/` (Light
  Fluent design system **+ mirrored dark mode**, tokens centralised in
  `_tokens.py` — `ThemeMode { SYSTEM, LIGHT, DARK }`, palettes
  `LIGHT_TOKENS`/`DARK_TOKENS`, shadows for `QGraphicsDropShadowEffect`;
  `apply_theme(app, mode)` loads `light_fluent.qss` or `dark_fluent.qss`,
  updates the active palette and re-installs card shadows; both QSS
  expose **exactly** the same selector set — guarded by
  `tests/unit/ui/test_theme_sync.py`), `_components.py` (shared bricks:
  `card`, `page_header`, `field_hint`, `section_label`,
  `horizontal_separator`, `install_shadow`, `localize_button_box` —
  translates standard Qt buttons via `QCoreApplication.translate(
  "StandardButtons", ...)`; `reapply_card_shadows` iterates over **live
  top-level widgets** rather than `QApplication.allWidgets()` which would
  include zombie widgets), `pedagogy_labels` (UI-translated variants of
  the FR-frozen `pedagogy/labels`), `visuals_labels` (deliverables / diagram
  types / statuses), `main_window` (sidebar + `QTabWidget`),
  `generation_controller`, `pedagogy_controller`, `visuals_controller`
  (QThread worker + `VisualsQtEventBus` bridge), `qt_event_bus`
  (`QtEventBus` + `PedagogyQtEventBus` + `VisualsQtEventBus`), `app_main` (entry
  point + full DI — instantiates `ThemeController` which reads the
  appearance preference in `%APPDATA%/Fahmi2/ui_prefs.json` and applies
  the theme, and `LanguageController` which reads/persists the interface
  language in the same file and installs the matching `QTranslator`
  **before** widget construction).
- `i18n/` — UI internationalisation (source language = French):
  `languages.py` (enum `AppLanguage { FR, EN }` + native
  `LANGUAGE_LABELS` + `DEFAULT_LANGUAGE` — module **pure Python with no
  Qt dependency**, importable by application services without pulling
  `QTranslator`), `__init__.py` (Qt functions:
  `install_translator(app, lang, dir)` + `bundled_translations_dir()`),
  `translations/fahmi2_<code>.ts` (editable sources — versioned),
  `compiled/fahmi2_<code>.qm` (binaries — **gitignored**, regenerated by
  `scripts/i18n_compile.py`, bundled at build time via
  `packaging/fahmi2.spec`). UI strings go through `self.tr(...)`
  (instance methods) or `QCoreApplication.translate(<context>, ...)`
  (free functions); extraction via `scripts/i18n_extract.py` (wraps
  `pyside6-lupdate -extensions py`), compilation via
  `scripts/i18n_compile.py` (wraps `pyside6-lrelease`). The language
  change is persisted by `LanguageController.set_language(...)` but
  applies **at the next launch**: Qt does not propagate `LanguageChange`
  to strings already rendered via `tr()` at widget construction time,
  and rebuilding the tree would be brittle.
  **Migration state: complete** (phases 0 to 4 delivered). **485
  strings** translated across **≥ 28 Linguist contexts** covering: the
  `MainWindow` pilot (phase 0); the cockpit surface — sidebar, tabs,
  dock, stats, logs (phase 1); all configuration dialogs —
  GlobalSettings, NewProject, GenerationSettings, PedagogySettings,
  ChatSettings, PromptsEditor, CostEstimate — + internal widgets
  (PhaseConfigs, SourceOrder, LanguageSelection) + helpers
  (`localize_button_box` replaces `frenchify_button_box`; centralised
  labels `_model_labels` / `pedagogy_labels` exposed as **functions**
  returning dicts translated on use) (phase 2); Dialogue view
  (`chat_view` / `_chat_bubble`), cost matrix, pedagogy progress view +
  all the QMessageBoxes of the 3 controllers (phase 3); document-export
  helper, viewmodels (run_matrix, pedagogy_state) + fs helpers (phase 4).
  **Frozen FR domain**: `pedagogy/labels.py` stays in French (used in
  LLM prompts; the quality of materials depends on the linguistic
  stability of the prompts); the translated UI variants are exposed via
  `ui/pedagogy_labels.audience_display_label` / `bloom_display_label` /
  `density_display_label`.
  **Guard tests**: `tests/unit/i18n/test_i18n.py` parametrises ~60
  critical strings (≥ 1 per migrated context) which validate end-to-end
  that the compiled `.qm` contains the expected translation — a FR
  source rename without re-extraction/compilation fails the suite.
  **Qt pitfalls**: `pyside6-lupdate` does not extract strings passed to a
  function wrapper (``_tr(source)``) — always call
  ``QCoreApplication.translate("Context", "literal source")`` directly
  with BOTH context and source literal. Same for `self.tr()`: the
  context is the **class name** where it is called
  (`PedagogyProgressView`, not `PedagogyProgress` even if there is a
  human alias). The previously installed `QTranslator` is cleaned up via
  `setParent(None) + deleteLater()` at each `install_translator`
  (without this, orphan QObjects continue to receive `LanguageChange`
  and can corrupt memory in long test sessions). PySide6 stubs type
  `QT_TRANSLATE_NOOP` as `object` → `typing.cast(str, ...)` required for
  strict mypy.

## The pipeline in 8 phases

Canonical order in `phase_registry.py`. Each handler declares
`is_per_source` (a source = video, audio, document, or YouTube link):

| Phase | Handler | Mode |
|-------|---------|------|
| 0 STT | `phase_0_stt` | **per source** |
| 1 Term extraction | `phase_1_term_extraction` | **per source** |
| 2 Glossary reconciliation | `phase_2_glossary_reconciliation` | batch |
| 3 Rephrasing | `phase_3_reformulation` | **per source** |
| 4 Structuring | `phase_4_structuration` | **per source** |
| 5 Consolidation | `phase_5_consolidation` (dispatcher `ORDERED`/`THEMATIC`) | batch |
| 6 Translation (+ glossary localisation) | `phase_6_translation` | batch (sources × languages loop) |
| 7 Coherence | `phase_7_coherence` | batch (languages loop) |

`PipelineEngine._execute_one` persists each `PhaseExecution` in SQLite. A
phase already `SUCCEEDED` is **skipped** (turned into `SKIPPED`). This is
the checkpoint/resume base. Batch phases are persisted with
`source_id IS NULL`.

**Parallelism**: the engine executes per-source phases via
`core/concurrency/map_bounded` bounded by
`PhaseHandler.max_parallel_workers(ctx)` (default 1; phase 0 =
`parallelism.stt_cloud_workers` if cloud STT, otherwise 1 — 1 local GPU;
phases 1/3/4 = `parallelism.llm_workers`). Batch phases parallelise their
inner loops: 6 over `(language × document)`, 7 over languages, 5 over
per-source summaries (result order preserved → deterministic assembly).
The barriers remain the batch phases 2 and 5 (the engine stays
"phase-by-phase"). `ParallelismConfig` is wired and adjustable in the UI
(default `llm_workers=16`, `stt_cloud_workers=3`). Details:
`docs/superpowers/specs/2026-05-21-parallelisation-traitements-design.md`.

## Cross-cutting mechanisms (to know before modifying)

- **Consolidation modes (phase 5)**: `GenerationSettings.consolidation_mode`
  (`ConsolidationMode`, default `ORDERED`, *lenient* migration) selects a
  **strategy** (`pipeline/handlers/_consolidation/`: ABC
  `ConsolidationStrategy` + deterministic helpers shared in `_base.py`;
  `ordered.py` = historical behaviour; `thematic.py` = new).
  `phase_5_consolidation.py` is now just a **dispatcher** (+ compat
  re-exports for historical tests). `ORDERED`: 1 source = 1 chapter,
  content copied. `THEMATIC`: **cross-cutting thematic rewrite** by the
  LLM (strict on facts / flexible on form) as provenance-tracking
  map-reduce — T1 factual ledger per source (traced ids `source#n` +
  verbatim excerpt, `consolidation/facts_master.json` + `facts.md`
  artefacts), T2 thematic plan (deterministic coverage #1 → "Additional
  elements" safety-net chapter), T3 per-chapter writing (coverage #2,
  conflicts shown per source), T4 meta + reused deterministic assembly.
  **Technical identifiers (ULID, `source#n`) never leak into the
  deliverable**: the LLM only receives readable "Source N" labels for
  attribution, and `_strip_provenance_ids` replaces any residual id
  (deterministic safety net). Intra-phase resume via *consistency hash*
  (without touching `PipelineEngine`). Cost: dedicated factor in
  `CostEstimator` (no runtime enforcement in generation). UI: selector in
  `GenerationSettingsView` + "order has no effect" note on
  `SourceOrderView`. 3 prompts `phase_5_fact_ledger`/`_thematic_plan`/
  `_thematic_chapter`. Spec:
  `docs/superpowers/specs/2026-05-26-modes-consolidation-thematique-design.md`.
- **Glossary terminology localisation (phase 6)**: the glossary **terms**
  are localised **by target language** (translated-unless-international;
  acronym preserved; invariant `acronym_expansion`) by a **structured LLM
  call** (`_localize_glossary`, prompt `phase_6_glossary_localization`).
  **By-position pairing** (the prompt forces one JSON object per term **in
  order**) — robust to imperfect re-emission of the `source` field
  (otherwise **acronyms** had their **definition** falling back to the
  source language); fallback to source-term pairing then per-term if the
  count differs. The **definition is always translated** (even for a kept
  acronym); only the `acronym_expansion` stays in the source language.
  Phase 6 (1) **renders `glossary.{L}.md` deterministically** (the
  glossary is **no longer a `_TranslationTask`**), (2) injects the real
  `source → target` equivalents into the translation of the
  consolidated/per-source docs, (3) **persists `cross_lang` in
  `glossary_master.json`** (atomic write, for downstream). **Single
  source**: `domain/glossary.localize_glossary_terms(terms, language)` (=
  `cross_lang[L]`, fallback on the source term). **Propagation**: the
  **Pedagogy** (`SupportsOrchestrator`) and **Dialogue**
  (`corpus.load_corpus_chunks`) **pre-localise** the glossary to the
  **content language** they load (generators / `format_glossary_terms` /
  `_glossary_chunks` unchanged). `cross_lang` carries **term + definition**
  (`domain/glossary.LocalizedTerm`; persisted by `_persist_cross_lang`
  **without an additional LLM call** since the translated definition is
  already computed; *lenient* parsing: `{term,definition}` object or
  **legacy string** = term only, definition falling back on the source) →
  the glossary is **fully localised downstream** (Pedagogy/Dialogue), not
  just the term. Only the `acronym_expansion` (*Meaning* column) stays
  **invariant** per language (intended). Specs:
  `docs/superpowers/specs/2026-05-27-localisation-terminologique-glossaire-design.md`
  + `docs/superpowers/specs/2026-05-27-dialogue-langue-corpus-design.md`.
- **Multi-feature shell**: the project area is a `QTabWidget` populated by
  a `FeatureRegistry` (modelled after `PhaseRegistry`). A `Project` only
  carries name + location (immutable after creation); the business
  settings are per feature (`GenerationSettings`, `None` = "to be
  configured"). The workspace has one folder per feature
  (`<location>/generation/…`). The `projects.settings_json` blob is in
  **v2** (`{version, workspace_folder, generation, pedagogy}`) with
  *lenient* v1→v2 migration on read. Adding a feature = registering a
  `FeatureTab`, without touching `MainWindow` or `Project`.
- **Polymorphic inputs (ingestion)**: phase 0 delegates to
  `IngestionDispatcher` (injected into `PhaseContext`) which routes
  depending on the `SourceKind` of an `InputSource`
  (`SourceExecution.source`; file **or** URL). `MediaIngestor`
  (video/audio) extracts the audio then STT; `DocumentIngestor`
  (pdf/docx/md/txt) extracts the text into a **single-segment**
  `Transcription` (the full text, structure preserved —
  `_load_transcription_text` joins segments by a space, so a *single*
  segment avoids any flattening). `build_input_sources` (formerly
  `scan_input_folder`) scans the folder via `classify_file`, then **adds
  afterwards** the YouTube links from `GenerationSettings.youtube_urls`
  (**single videos**, `--no-playlist`) downloaded by `YtDlpDownloader`
  (**resolved/replaceable** yt-dlp binary: `resolve_ytdlp_binary_or_none`,
  override `FAHMI2_YTDLP`). A document has no STT
  (`duration_seconds=0`). The `GenerationSettings.reformulate_documents`
  flag (default `True`): if disabled, phase 3 does a **pass-through** (the
  document is inserted as-is, cost 0) instead of rephrasing. The
  `CostEstimator` reasons in `SourceWeight` (audio duration **or** text
  tokens, `reformulated` flag). **Order & exclusion**: `source_order`
  (ordered keys of included sources) + `excluded_sources` (excluded
  keys) are reconciled at scan by the pure function
  `reconcile_source_order` (shared `build_input_sources` ↔ UI widget
  `SourceOrderView` dual list); stable keys =
  `InputSource.order_key()` (file name / URL); obsolete keys are
  ignored, new ones added at the end.
- **Checkpoint / resume after error**: a Run keeps the same `RunId` from
  start to end. `RunOrchestrator.resume_or_create_run(project)` resumes
  the last Run if it is `FAILED`/`PAUSED`/`RUNNING`-orphan (`SUCCEEDED`
  phases will be skipped), otherwise creates a new Run. The state
  machine therefore allows `FAILED → RUNNING`. Never re-`create_run` to
  "resume": this forges a new `RunId` and loses all the checkpoint.
- **SQLite `UNIQUE` + `NULL` pitfall**: SQLite treats `NULL` as distinct
  in a `UNIQUE` constraint, so `ON CONFLICT(run_id, phase_id, source_id)`
  **never** triggers for batch phases (`source_id IS NULL`).
  `SqliteState.upsert_phase_execution` does an explicit `DELETE + INSERT`
  in this case. Any schema evolution goes through `_apply_soft_migrations`
  (idempotent, `ALTER TABLE ADD COLUMN` or data cleanup).
- **DeepSeek thinking**: `DeepSeekAdapter` sends the reasoning mode via
  `extra_body={"thinking": {"type": "enabled"|"disabled"},
  "reasoning_effort": "high"|"max"}`, configurable **per phase**
  (`PhaseConfig.thinking_enabled` + `reasoning_effort`). `CostEstimator`
  applies a multiplier on the output tokens depending on this level (×2.5
  / ×3.5 HIGH / ×6 MAX) — reasoning tokens are billed at the output
  rate.
- **Prompt overrides**: `PromptLoader` loads `%APPDATA%/Fahmi2/prompts/<name>.j2`
  first if it exists and is a valid Jinja2, otherwise the default bundled
  in `infra/prompts/defaults/`. `PromptsService` + `PromptsEditorDialog`
  expose this in the UI. Modifying a `.j2` in `defaults/` changes the
  base for everyone, but an `%APPDATA%` override masks it. The catalogue
  covers the 8 phases, the **3 `phase_5_*` templates of the thematic
  mode**, **and** the 8 `pedagogy_*` templates (all editable the same
  way).
- **Revision materials**: 8 types, all LLM, generated by a **dedicated
  lightweight orchestrator** (`SupportsOrchestrator`, **not** the
  `PipelineEngine`) which **parallelises the units (language × material)**
  via `core/concurrency/map_bounded` (bounded by
  `PedagogySettings.llm_workers`, default 16, range 1–64 exposed as a
  setting; lock on the manifest, shared cost counter). The **cost cap is
  best-effort** in parallel (slight overshoot tolerated by in-flight
  requests). Details:
  `docs/superpowers/specs/2026-05-21-parallelisation-traitements-design.md`.
  Inputs are read **from disk** like the pipeline: consolidated document
  (parsed into chapters; a **content language** is resolved among the
  existing `consolidated.{lang}.md` — the target language can therefore
  differ) and glossary (`glossary_master.json`; no SQLite table).
  Materials are written by the LLM in the chosen **target language**,
  independently of the source document's language. No SQLite checkpoint:
  freshness is tracked by `pedagogy/manifest.json` (settings hash +
  per-language source mtime), a regenerated source **stales** the
  materials (UI state banner). **Alignment with generation**
  (`_is_complete`): re-running a **complete** set (all present + fresh)
  **regenerates** everything (overwrites, like a new run); an
  **incomplete** set (interruption / cap) is **resumed** *coarsely*
  (fresh materials skipped, missing ones generated). The status of the
  last execution is persisted to disk (`pedagogy/run_state.json`:
  `RunStatus` + timestamps + cost) for a status consistent with the
  generation (sidebar, tiles), readable outside an active session. The
  `SupportsOrchestrator` enforces a **cost cap**
  (`PedagogyCostEstimator`). The LLM generators share the pipeline's
  retry (`core/retry/classification.default_classify`) via
  `pedagogy/generators/_base.py` (typed JSON parsing). The "separate
  answer key" **evaluative** materials produce a `<support>.corrige.md`
  file distinct from the subject. Exports: `.apkg` (genanki) via
  `app/pedagogy_export.py`, **one Markdown/PDF/HTML/DOCX file per
  material and per answer key** (`<support>.<lang>(.corrige).<ext>`) via
  the shared core `app/document_export.py` (`write_documents`:
  collector → per-format writing; `infra/export/markdown_pdf` and
  `markdown_docx` stay pure *renderers*). `ExportDocument` carries the
  content **language** (drives font/direction of PDF/HTML rendering).
  The **generation** has its own documentary export
  `app/generation_export.py` (consolidated + glossary, one file per
  language, MD/PDF/HTML/DOCX; `GenerationSettings.export_formats`
  setting, opt-in). On the UI side, the shared helper `ui/_export_ui.py`
  (`choose_export_format` + `run_document_export`) factorises format
  choice → folder → errors → log for both controllers. Prompts allow
  light Markdown in content; the Anki export **converts the Markdown
  fields to HTML** (`genanki_exporter._md_to_html`) — except for cloze
  text (mechanics `{{cN::}}` preserved). MD/PDF/HTML/DOCX consume the
  rendered Markdown as-is; the **HTML body is rendered once** by
  `render_markdown_body` (extensions `tables`+`toc`), reused by HTML,
  PDF **and** DOCX. **Table normalisation** (`_normalize_table_blocks`,
  shared therefore HTML/PDF/DOCX): LLM outputs often glue a pipe table
  to the introducing sentence or indent it in a numbered list →
  python-markdown does not activate it (literal bars). We guarantee a
  blank line before/after + de-indent. *python-markdown limit*: a table
  cannot be nested in an `<li>` → it comes out; the numbering of the
  following list is restored by `_renumber_lists_split_by_tables`
  (`<ol start>` attribute, honoured by the browser + xhtml2pdf PDF).
  Reused by HTML, PDF **and** DOCX (`markdown_docx` → htmldocx →
  python-docx; Word natively handles CJK and line breaking; **Arabic**
  gets explicit RTL direction (`w:bidi` paragraphs, `w:rtl` runs,
  `w:bidiVisual` tables → inverted columns, like `direction:rtl` PDF /
  `dir="rtl"` HTML), toggles inserted at the correct OOXML schema
  position via `insert_element_before`; **landscape orientation** —
  `landscape` option, e.g. glossary — is set on the document sections
  via `WD_ORIENT.LANDSCAPE` + width/height swap.
  **htmldocx translates neither CSS borders nor `width:100%`** (tables
  without borders, width adjusted to content) →
  `markdown_docx._format_docx_tables` reformats **all** tables after
  conversion: built-in `Table Grid` style (borders) + `tblW` to `pct`
  5000 (100 %), to align with HTML/PDF.
  **PDF/HTML rendering (`infra/export/markdown_pdf`)**: the **PDF is
  rendered from the HTML via `xhtml2pdf`** (ReportLab engine, pure
  Python, *bundleable*) — real pagination (multi-page lists/tables), CSS
  typography, landscape orientation. Gotchas: (1) GFM pipe tables →
  python-markdown `tables` extension (otherwise literal text); (2)
  **clickable** TOC via the `toc` extension + `core/slugify.slugify_anchor`
  (heading ids = TOC anchors; `slugify_anchor` keeps Unicode letters →
  valid CJK/Arabic anchors); (3) `app.document_export.ExportDocument`
  carries the **`landscape` orientation** (PDF **and** DOCX), the **PDF
  column widths** (`pdf_column_widths`), and the **language** — the
  **glossary** exports in landscape (PDF + DOCX) + dedicated widths
  (PDF); (4) xhtml2pdf only honours column widths set on **each** cell
  and collapses empty cells → `_layout_table_cells` (widths +
  `&nbsp;` filling); (5) ReportLab+Arial does not render
  U+2010/2011/2012/2015 (square) → `_normalize_for_pdf` normalises them
  (em-dash/en-dash kept); (6) more broadly, any character **without a
  glyph** in the active font (decorative emojis 📖/📝/💡/🎯…) is
  **stripped** before rendering (`_strip_unrenderable_for_pdf`; coverage
  via `pdfmetrics.getFont(...).face.charToGlyph`, Cc/Cf/Zs/Zl/Zp
  categories preserved including ZWJ/RLM for Arabic) — otherwise
  ReportLab draws a square (no colour emojis, no glyph fallback);
  HTML/DOCX, on the other hand, keep them; (7) **Chinese is written
  without spaces** and ReportLab only breaks at spaces (the
  `-pdf-word-wrap: CJK` CSS mode of xhtml2pdf 0.2.17 crashes on
  `<p>`/`<li>`) → CJK prose is **pre-broken** with `<br/>`
  (`_prewrap_cjk_runs` via `reportlab…wordSplit` + BeautifulSoup, width
  derived from the A4/margin constants) and **cells** by the CSS rule
  `-pdf-word-wrap: CJK` (the only context where it works); both apply
  only to CJK languages (`_CJK_LANGUAGES`). The pre-formatting operates
  **block-by-block** (paragraph/li/heading) on the **flattened text** —
  **bold/italic fragments included**: cutting node by node placed the
  1st line following a bold term *after* that term → overflow on the
  right. The target width reserves **one ideogram** (`_CJK_WIDEST_CHAR`)
  because `wordSplit` overshoots its target by the last character
  added. **Per-language PDF font**: Latin (fr/en/de/es/it) → system
  Arial (resolved as Helvetica by xhtml2pdf, covers Latin-1); **Chinese**
  → Microsoft YaHei (system `msyh.ttc`, loaded via `subfontIndex`)
  injected into `xhtml2pdf.default.DEFAULT_FONT` (`EXPORT.NO_CJK_FONT`
  guard if missing); **Arabic** → Arial (Arabic glyphs) + `direction:rtl`
  + tag `<pdf:language name="arabic"/>` which triggers contextual
  reshaping + bidi (`arabic-reshaper`/`python-bidi`, xhtml2pdf
  transitives). ⚠ **Arial Italic/Bold-Italic have no Arabic glyphs**
  (Arabic has no italic forms) → Arabic in emphasis (`*…*`) came out as
  squares; `_ensure_arabic_font_registered` registers a dedicated family
  `AppArabic` whose **italic/bold-italic point to the upright variants**
  (regular/bold), which cover Arabic.
  `domain.languages.is_rtl` = **single RTL source** (PDF `direction`,
  HTML `dir`, DOCX `bidi`/`bidiVisual`); `_text_direction` derives the
  CSS value from it; font sizes and `@page` margin **centralised**
  (single source for the CSS template ↔ CJK pre-formatting width
  computation). **All system Windows fonts — nothing to bundle.**
- **Visualizations (standalone HTML deliverables)**: an **on-demand feature**
  (Pedagogy model) producing two **fully self-contained** interactive HTML
  pages per Latin language — a **knowledge map** (typed graph of
  concept/glossary-term/idea/example nodes with typed relations) and a
  **generated-diagram gallery** (flowchart/timeline/comparison/hierarchy/
  cycle/decision-tree). **GraphRAG-lite pipeline** (`visuals/`): deterministic
  skeleton (glossary as backbone) + LLM semantic layer + **gleaning** recall
  pass; **entity resolution** via embedding cosine merge (OpenAI) with a
  glossary spine and an **AUTO label-normalisation fallback** when no OpenAI
  key; **networkx Louvain** community detection (**fixed seed** →
  deterministic) feeding dual-use community reports; **idea-chains** as a
  map-reduce over those reports. **Multilingual = structure extracted once +
  labels localised**: the graph/board is built in a single *structure
  language*, then each Latin language is a `label_translator` pass + a render
  — far cheaper than re-extracting per language. **Latin-script only**
  (`VISUALS_LANGUAGES` = fr/en/de/es/it): Chinese & Arabic are **deliberately
  excluded** (no down-levelling the interactive rendering for RTL/CJK
  constraints). **Zero rendering DSL** (no Mermaid): the LLM emits **typed
  JSON**; `infra/export/knowledge_map_html` / `diagram_board_html` render it
  deterministically to HTML, **inlining** the vendored **Cytoscape.js** core +
  extensions (`fcose` network ↔ `dagre` tree on click, `expand-collapse`,
  `concentric` cycle) from `infra/export/_assets/visuals/` — **no CDN, no
  network at view time**. **Embedded source excerpts** (`_excerpts.SectionIndex`,
  bounded by `EXCERPT_MAX_CHARS`) make each page self-explanatory. Inputs read
  **from disk** like Pedagogy (consolidated doc parsed by
  `core/corpus.parse_sections` into language-invariant `section_path`; glossary
  pre-localised). **Freshness**: `visuals/manifest.json` (per-language settings
  hash + structure/glossary/content mtimes) → coarse resume of an interrupted
  set, full regenerate of a complete one; `visuals/run_state.json` (shared
  `feature_run_state`) drives the sidebar pastille + tab banner. **Cost cap**
  best-effort (`VisualsCostEstimator` for the pre-run estimate). **Throughput &
  observability**: the structure extraction parallelises its per-unit/per-community
  LLM calls via `extractors/_base.map_units_with_progress` (bounded by
  `llm_workers`, honours the `PauseToken`, **order preserved → deterministic**) and
  emits `VisualsStructureProgress` events; the progress UI shows a **Structure**
  column **before** the per-language columns + per-step logs (the structure phase is
  the long pole and runs once on the structure language). All magic
  numbers (gleaning rounds, per-density node/diagram caps, cosine threshold,
  Louvain seed, excerpt length) centralised in `visuals/_constants.py`. Spec:
  `docs/superpowers/specs/2026-05-29-visualisations-html-autonomes-design.md`.
- **Errors → UI**: an exception raised by a handler **must** be a
  `Fahmi2Error` (code + user_message + technical_details). The engine
  converts it to an `ErrorInfo`, propagates it in `PhaseFinished.error`,
  and `generation_controller._to_log_event` exposes it in the Logs panel
  (code + message + details) and `events.jsonl`.
- **UI threading & displayed project**: a Run runs in a `QThread`
  worker. The `GenerationController` (decoupled from `MainWindow`: it
  receives header/stats/matrix/logs) distinguishes `_current_project`
  (shown in the dashboard) from `_active_worker_project_id` (project of
  the active worker) — pipeline events only refresh matrix/stats if the
  two coincide, to avoid overwriting the dashboard when the user
  navigates between projects during a Run. The worker→UI bridge passes
  through `QtEventBus` (EventBus → Qt Signal).
- **Secrets**: API keys encrypted via Windows DPAPI (`DPAPISecretsStore`),
  never plaintext on disk or in the logs. Outside Windows (dev),
  `InMemorySecretsStore` fallback.

## Tests

Key fixtures (in `tests/conftest.py`): `make_generation_settings` builds
valid `GenerationSettings`, `make_project` a minimal `Project`; pass
kwargs to override. Real providers have `_fakes.py` doubles
(`FakeLLMProvider`, `FakeSTTProvider`). UI viewmodels are tested without
Qt; widgets have `pytest-qt` smoke tests. `mypy --strict` is active:
beware of narrowing after an `assert` followed by a mutating call (work
around via `getattr` rather than accepting a false `unreachable`).

## Systematic directives

0. **Always validate the completeness of the plan**
1. **Constants centralization** — no magic string, magic number, or
   default value directly in the code, only in constants
2. Conformity with existing codebase patterns (reuse existing classes,
   methods, helpers, constants, mixins, base classes)
3. Follow the Google Python Style Guide — Google-style docstrings with
   Args, Returns, Raises sections; module-level docstrings on every file
4. Verify naming consistency (imports, classes, methods, variables,
   constants) and that all arguments are properly defined and passed
5. Respect framework patterns
6. Respect DRY, YAGNI, KISS, SRP, SoC, Boy Scout Rule, Composition over
   Inheritance
7. Write generic, extensible code — no duplication, reuse validator
   mixins and base classes
8. Update all documentation in `docs/` as well as all cross-cutting
   docs, `README.md`
