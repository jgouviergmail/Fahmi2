# Changelog

All notable changes to the Fahmi2 project.

The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and the project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Changed — Visualizations: density now controls the knowledge-map size

- The **content-quantity** setting (`SupportDensity`: light / standard / dense) now
  **noticeably** drives the size of the **knowledge map**. Previously it only capped the
  per-unit semantic-node count (4 / 7 / 12) while the **entire glossary** was dumped as
  nodes (density-invariant) with **no pruning** — so on a rich corpus "light" was still a
  huge, barely-distinguishable map.
- New pure module `visuals/_pruning.py` (`prune_knowledge_graph`): **edge-first
  selection** — edges are ranked by the sum of their endpoints' degrees and accumulated
  until a per-density node budget, which **guarantees by construction** that no kept node
  is isolated (never an empty map as long as an edge exists). Isolated nodes (glossary
  terms never linked) are dropped at **all** levels. Budget = `ratio × connected`
  (0.25 / 0.50 / 1.0) bounded by a cap (40 / 90 / none for dense) and a floor (12), all
  centralised in `_constants.py`. Inserted between `resolve_graph` and `assemble_graph`
  so communities / reports / idea-chains operate on the reduced graph.
- Measured on a real 12-course corpus: **388 → 40 (light) / 90 (standard) / 355 (dense)**
  nodes, 0 residual isolated, none empty. Note: "dense" is now slightly smaller than
  before (unlinked glossary terms leave the map — they remain in the exported glossary).

### Fixed — Visualizations: cost traceability in the progress matrix

- The progress matrix showed **$0.0000** in every cost cell/total (cells carried no
  cost) while the Cost tile showed the real total — misleading. Costs (already computed
  per deliverable in the orchestrator) are now **attributed per cell**
  (deliverable × {Structure, languages}) via two new fields on
  `VisualsStructureFinished` / `VisualsLanguageFinished`, populated in
  `VisualsProgressViewModel`. The grid totals now sum to the authoritative total; the
  live tile also includes the structure cost.
- The per-cell breakdown is also **persisted** in `visuals/manifest.json` (per-language
  localization costs + global structure costs, v2 format, backward-compatible) and
  reconstructed by `load_persisted`, so the matrix stays correct **after re-opening a
  finished project** — not only during a live run — mirroring how Generation (SQLite) and
  Pedagogy (per-artifact JSON) persist their per-cell costs.

## [1.6.0] — 2026-05-30

### Added — Visualizations: two standalone interactive HTML deliverables

- New **Visualizations** feature tab (on-demand, Pedagogy model): produces two
  **fully self-contained** HTML pages per Latin-script language — an interactive
  **knowledge map** (typed graph of concept / glossary-term / idea / example
  nodes with typed relations; reorganises from **network to tree on click**,
  with embedded source excerpts) and a **gallery of generated diagrams**
  (flowchart, timeline, comparison, hierarchy, cycle, decision tree).
- **GraphRAG-lite pipeline** (`visuals/`): deterministic glossary backbone + LLM
  semantic layer + **gleaning** recall pass; **entity resolution** via OpenAI
  embedding cosine merge with a glossary spine and an **AUTO label-normalisation
  fallback** when no OpenAI key; **networkx Louvain** community detection with a
  **fixed seed** (deterministic); **idea-chains** via map-reduce over community
  reports.
- **Multilingual by design**: the structure (graph + diagrams) is extracted
  **once** in a structure language, then **labels are translated** per language
  — far cheaper than re-extracting. **Latin-script languages only**
  (fr/en/de/es/it); Chinese and Arabic are **deliberately excluded** (no
  down-levelling of the interactive rendering for RTL/CJK).
- **Zero rendering DSL** (no Mermaid): the LLM emits **typed JSON**; deterministic
  Python → HTML renderers (`infra/export/knowledge_map_html` /
  `diagram_board_html`) **inline the vendored Cytoscape.js** core + extensions
  (`fcose` / `dagre` / `expand-collapse`) from `infra/export/_assets/visuals/` —
  **no CDN, no network at view time**.
- **Lightweight orchestrator** (`app/visuals_orchestrator`, no `PipelineEngine`):
  per-language parallelism (`map_bounded`), freshness `manifest.json`
  (settings hash + structure/glossary/content mtimes → coarse resume),
  `run_state.json` (shared `feature_run_state`), best-effort cost cap +
  `VisualsCostEstimator` pre-run estimate.
- **UI**: `VisualsTab` + `VisualsController` (QThread worker + `VisualsQtEventBus`),
  `VisualsSettingsView` (deliverables / content / AI generation),
  `VisualsProgressView` (status grid + tiles), state/progress viewmodels
  (testable without Qt). Sidebar gains a **third status** (Visualizations) in
  the aggregated pastille + subtitle + tooltip. 5 `visuals_*` prompts editable
  from the PromptsEditor.
- **i18n**: 96 new strings translated to English (`.ts`/`.qm`), guard tests
  extended (≥ 1 string per new context).
- **Packaging**: `.spec` bundles the vendored `_assets/visuals/*` and
  `collect_submodules('networkx')`.

### Changed — Visualizations: parallel structure extraction + progress visibility

- The structure-extraction phase (graph / diagrams / community reports) now
  **parallelises its per-unit/per-community LLM calls** via the shared
  `extractors/_base.map_units_with_progress` (bounded by `llm_workers`, honours the
  `PauseToken`, **order preserved → deterministic**). Previously it was fully
  sequential and ignored the configured worker count — a 2-video test course
  (~32 units, thinking on) took tens of minutes; it now completes in minutes.
  Token cost is unchanged (per-token billing): a 12-video nominal run is ~$0.20.
- **Progress visibility**: new `VisualsStructureStarted` / `VisualsStructureProgress`
  / `VisualsStructureFinished` events; the progress matrix gains a **Structure**
  column **before** the per-language columns (per-deliverable status + `Graph 12/32`
  tooltip), and the Logs panel shows per-step advancement. The structure phase
  (the long pole, run once on the structure language) is no longer invisible.

### Fixed — Visualizations: dense diagram legibility (diagrams gallery)

- Graph diagrams (flowchart/hierarchy/decision tree/cycle) were squeezed into a
  **fixed 280 px** canvas by `cy.fit()` with zoom/pan disabled — verbose node
  labels became unreadable. The canvas height is now **adaptive to node count**
  (computed server-side, `clamp(210 + nodes×52, 300, 560)` px → no layout shift),
  fonts are slightly larger, and an **initial-zoom floor** (≥ 0.62) guarantees
  legibility; **wheel-zoom and drag-pan are enabled** (grab cursor). Timelines/
  comparisons (HTML) keep the default scrollable height.
- **Robust for complex diagrams**: every card gains an **« Enlarge » (fullscreen)
  button** opening a full-window overlay (localized close, Esc to dismiss) where a
  graph is re-rendered in a fresh Cytoscape instance fit to the whole viewport
  (zoom/pan) — a dense 17+-node hierarchy stays fully legible. Linear diagrams are
  cloned into the overlay (scrollable). No card size can show an arbitrarily complex
  graph legibly, so the fullscreen view is the durable answer.

### Notes

- **1219 → 1362 tests** (Visualizations engine, renderers, orchestrator, UI
  viewmodels, i18n guards). `pytest` green ×3 runs, `ruff check .` and
  `mypy --strict src tests` clean (464 files).
- **End-of-branch exhaustive review** (10 clusters × 9 directives, adversarial
  per-finding verification): 0 critical / 0 high; 31 confirmed quality findings
  all fixed — notably two shared modules extracted to remove duplication
  (`pipeline/generation_outputs.py` shared by Pedagogy/Visualizations source
  loaders; `ui/widgets/_progress_view.py` shared by the three progress views),
  knowledge-map accessibility (`aria-label` / `aria-pressed` / labelled search),
  named zoom-bound constants, and `--danger` design token.
- **Two deliberate divergences from the spec** (documented in the design doc):
  entity-description canonicalisation is **deterministic** (no extra LLM step);
  community detection uses a **flat Louvain partition** (the `level` / `parent_id`
  fields are kept for a future multi-level dendrogram).

## [1.5.2] — 2026-05-29

### Fixed — Critical: `Project.chat` was reset on every Run

- `RunOrchestrator.execute()` rebuilt the `Project` field-by-field after
  each run and **silently dropped** the `chat` field (added later than
  the original code). The Dialogue settings were therefore reset to
  `None` on every generation run. Now uses `dataclasses.replace(project,
  ...)` which preserves all fields, including any future ones.
- Added regression test `test_execute_preserves_chat_settings` mirroring
  the existing pedagogy guard.

### Changed — Architecture cleanup (post v1.5.1 code review)

- **`PauseToken` moved from `pipeline/` to `core/concurrency/`**. The
  token is shared by `core.concurrency.map_bounded`, the generation and
  pedagogy orchestrators, and the UI controllers — keeping it in
  `pipeline/` made `core` depend on `pipeline`, violating the documented
  dependency flow (UI → app → pipeline/infra → domain/core).
- **New `pipeline/workspace_layout.py`** as single source of truth for
  artifact paths: `transcripts/`, `candidates/`, `reformulated/`,
  `structured/`, `per-video/` subdirs and `glossary_master.json`,
  `consolidated_master.md` filenames (previously hardcoded in 7+
  modules). Exposes typed helpers `transcript_path()`,
  `candidates_path()`, `reformulated_path()`, `structured_path()`,
  `glossary_master_path()`, `consolidated_master_path()`.
- **DRY cleanup**: `load_transcription_text` and `load_reformulated_text`
  centralised in `pipeline/handlers/_base.py` (duplicated across phases
  1, 3, 4) ; `DEFAULT_TOP_K_GLOSSARY=30` centralised (duplicated phases
  3 & 4) ; `MIN_SECRET_LENGTH=4` exported from `core.logging.sink`
  (duplicated in `secrets_service`) ; `DEFAULT_FFMPEG_BINARY` /
  `DEFAULT_FFPROBE_BINARY` / `FFMPEG_LOGLEVEL_ERROR` centralised in
  `infra/audio/_ffmpeg_common.py` (duplicated between extractor and
  cloud preparer).
- `GenerationSettings.__post_init__` error message now derives the list
  of allowed export formats from `GENERATION_EXPORT_FORMATS` rather than
  a hardcoded `{markdown, pdf, html}` string (stale since DOCX support).
- `chat.retriever_factory.build_passage_retriever` docstring completed
  to document the `glossary_mtime_ns` parameter.

### Notes

- 1218 → **1219 tests** (added regression guard).
- Net code: −150 lines (231 added, 384 removed) over 38 files.
- No public API breakage. Internal `PauseToken` import path changes
  from `fahmi2.pipeline.pause_token` to
  `fahmi2.core.concurrency.pause_token` — all in-tree call sites
  migrated.

## [1.5.1] — 2026-05-29

### Added — Per-source cost attribution for batch phases in the Generation matrix (cross-cutting refactor)

- Phases 5 (consolidation) and 6 (translation) are batch phases at the
  engine level (single `PhaseExecution` with `source_id=NULL`) but have
  internal operations that ARE attributable to a specific source:
  - Phase 5 ordered: T1 video-summary per source.
  - Phase 5 thematic: T1 fact-ledger per source.
  - Phase 6: translation per (source × language) — aggregated to source.
- The Generation matrix now displays the per-source attributable cost on
  each cell for these phases, instead of the previous fallback to the
  "first-cell-only" rendering (which remains correct for purely batch
  phases 2 and 7). The column total stays the authoritative `cost_usd`
  (includes per-source attributed + residual: glossary localisation,
  thematic plan, meta…). If the vertical sum of visible cells is below
  the column total, that difference is the non-attributable batch
  residue.
- Cross-cutting refactor:
  - `PhaseExecution.per_source_costs: Mapping[SourceId, float]`
    (immutable via `MappingProxyType`, defaulting to empty mapping).
  - New SQLite column `phase_executions.per_source_costs_json` (NULL =
    no attribution, full back-compat). Soft migration via
    `ALTER TABLE ADD COLUMN`.
  - `ConsolidationResult` carries the dict alongside the total.
  - Phase 6 `_TranslationTask` enriched with `source_id: SourceId | None`
    (None for the cross-source consolidated translation, which remains in
    the batch residue).
  - `build_succeeded_phase(per_source_costs=...)` and
    `PipelineEngine` propagate the dict end-to-end (handler → engine →
    SQLite → viewmodel).
- Phase 5 thematic intra-phase resume: the per-source attribution is
  persisted in `facts_master.json` under the `per_source_costs` key, so
  that a resume after a mid-phase failure (`fresh=True`) preserves the
  T1 attribution instead of producing an empty mapping.
- 4 dedicated regression tests + 1 e2e (`test_engine_preserves_handler_per_source_costs_through_persistence`,
  `test_thematic_resume_intra_phase_preserves_per_source_costs`,
  `test_grand_total_no_double_counting_when_batch_phase_attributes_per_source`,
  `test_execute_attributes_translation_cost_per_source`,
  `test_phase_execution_per_source_costs_round_trip`).

### Fixed — Generation matrix: batch phase costs no longer hidden behind a tooltip

- Before this release, batch phases (Glossary, Consolidation,
  Translation, Coherence) had their cost only visible in the column
  total at the bottom; every cell of the column showed `—` with a
  tooltip "(coût au niveau du run)" on hover. Users naturally read that
  as "the per-cell cost is missing" without finding the tooltip.
- Fix: for purely batch phases (no per-source attribution), the batch
  cost is now rendered on the **first row** of its column; other rows
  stay `—` to prevent a mental "cost × N rows" miscount. For batch
  phases with per-source attribution (5/6, cf. the refactor above),
  every relevant cell now carries its own attributed cost.

### Fixed — Pedagogy: cumulative cost reset to zero on every resume

- Symmetric to the engine fix below, but tracked through a different
  mechanism (the pedagogy orchestrator does not use SQLite — cost is
  persisted in `pedagogy/run_state.json`). At each `generate()` call
  the orchestrator was unconditionally writing `total_cost_usd = 0.0`
  to disk and reinitialising the in-memory accumulator to `0.0`, so a
  resume after `FAILED` or `PAUSED` lost the historical total and the
  cost ceiling was effectively reset to its full budget each time —
  the user could re-run indefinitely past their declared cap.
- Fix: at startup, `SupportsOrchestrator.generate` reads the previous
  `PedagogyRunState`. If the previous status is in the resumable set
  (`FAILED`, `PAUSED`, `RUNNING`-orphan from an app crash), the cost
  accumulator is **rebased** on the historical total. Otherwise
  (`CREATED`, `COMPLETED`, `CANCELLED`, or no previous state), the
  accumulator starts at `0.0` — a new generation, not a resume.
  Resumable statuses set kept in parity with the pipeline
  (`_RESUMABLE_RUN_STATUSES` in `app/run_orchestrator`).
- The cost ceiling check now operates against the cumulative total
  (historical base + current pass). Consequence: if the user wants to
  resume after `PAUSED` (cap reached) without the ceiling
  short-circuiting the new pass immediately, **they must raise the
  cap** in the settings before relaunching. This is the correct
  behaviour: previously the cap was a per-run promise that hid the
  real spend; now it is a project-level promise that holds across
  resumes.

### Fixed — Engine: resumed runs lose `SUCCEEDED` state (and cumulative cost) after the first resume

- Each resume of a failed run overwrote the persisted `SUCCEEDED` state
  of every per-source phase with `SKIPPED` (`cost_usd=0`), via an extra
  `upsert_phase_execution` in the engine's skip path. After **one**
  successful resume the database held `SKIPPED` instead of `SUCCEEDED`;
  the **next** resume could no longer recognise the phase as already
  done and re-ran the whole per-source pipeline from scratch — losing
  cumulative cost AND artefacts.
- Fix: `pipeline/engine.py` no longer rewrites the state on skip. The
  `PhaseFinished(SKIPPED)` event is still emitted to the UI for
  consistency, but the persisted status stays `SUCCEEDED`. The skip
  condition also accepts `SKIPPED` legacy entries (defensive against
  pre-fix databases).
- Regression test: 2 successive resumes of a failed run keep the
  per-source `SUCCEEDED` status **and** the recorded `cost_usd` intact.

### Hardened — Two failure modes called out by DeepSeek's docs

After the JSON mode strict fix landed, a doc-driven review surfaced two
DeepSeek-documented behaviours that were not handled cleanly. Both are
now typed errors with appropriate retry semantics, instead of falling
through to the generic `LLM.INVALID_JSON` (which is non-retryable).

- **`LLM.EMPTY_CONTENT`** (retryable). DeepSeek's JSON mode docs warn:
  "the API may occasionally return empty content". `parse_llm_json` now
  raises this typed error when the response is empty or whitespace-only
  (including an empty fence ``` ```json``` ```), instead of letting
  `json.loads("")` raise `LLM.INVALID_JSON` (which would kill the phase
  on a behaviour the provider explicitly calls transient). Added to
  `_RETRYABLE_LLM_CODES`.
- **`LLM.UNEXPECTED_JSON_SHAPE`** (retryable). When the LLM returns a
  syntactically-valid JSON whose shape doesn't match what the parser
  expects (e.g. `_localize_glossary` receiving a dict without the
  `"items"` key), we now raise this typed error instead of silently
  falling back to `[]` (which would have produced a "localised"
  glossary identical to the source language with no warning). Retried,
  since LLMs are non-deterministic — a second attempt may produce the
  expected shape.

### Added — Diagnostic enrichment on `LLM.INVALID_JSON` errors

- The previous error reported a `raw_content` truncated at 500 chars
  with no `finish_reason` and no real length, making it impossible to
  tell a silently-truncated provider output from a fully-emitted but
  malformed JSON (see the Triple F case above). `parse_llm_json` now
  reports `raw_content` up to **50 000 chars**, plus `content_length`
  (real LLM output size), `truncated_in_log` (bool), and
  `finish_reason` propagated from the provider through
  `LLMResponse.finish_reason`. Already in place since commit `01f8b41`
  but re-stated here for completeness.

### Fixed — Phase 6 translation: `LLM.INVALID_JSON` from unescaped quotes in target-language definitions

- DeepSeek can produce straight quotes `"..."` inside a string value (especially
  when highlighting a term inside an Arabic / German definition like
  `"الحب المالي" (Love money)`) **without escaping them**, which breaks the
  JSON parser downstream and fails the entire phase 6 with
  `LLM.INVALID_JSON` even though `finish_reason="stop"`. Observed in
  production on the term "Triple F" (1 occurrence over 114 glossary terms
  on a real accounting course → triggered systematically when running the
  glossary localisation in Arabic).
- Fix: **JSON mode strict** on the provider side
  (`response_format={"type": "json_object"}`, supported by DeepSeek through
  the OpenAI-compatible API). The server now guarantees a syntactically
  valid JSON output — it escapes its own quotes inside string values.
- Implementation: new constant `JSON_OBJECT_RESPONSE_FORMAT` in
  `infra/llm/interface.py` (single source of truth). `LLMProvider.chat` +
  `chat_stream` extended with a `response_format: dict | None = None`
  additive kwarg (defaults to `None` → unchanged behaviour, retro-compat
  with existing scenarios and tests). Propagated through
  `invoke_llm_chat`, `invoke_llm` (pipeline), and `invoke_support_llm`
  (pedagogy). Wired in every call site that parses JSON downstream:
  pipeline phases 1, 2, 5 (ordered + thematic ×4) and 6, and all 9
  pedagogy generators (concept flashcards, MCQ, true/false, cloze, open
  questions, sheet, key points, mock exam).
- Prompt restructuring: `phase_6_glossary_localization.j2` now requests
  a root **object** `{"items": [...]}` instead of a root array `[...]`
  (the OpenAI/DeepSeek JSON mode requires an object root). All other JSON
  prompts (pipeline + pedagogy) already returned object roots — no other
  prompt touched. `_localize_glossary` reads `payload["items"]` with a
  defensive fallback on array-root payloads (handles legacy user
  overrides of the prompt).
- **User-facing notice**: if you have overridden
  `phase_6_glossary_localization.j2` in `%APPDATA%/Fahmi2/prompts/`,
  click **Edit → Edit prompts → ↩ Reset to default** on this template
  to pick up the new `{"items": [...]}` skeleton (the fallback parser
  accepts your previous array-root version too, but you lose the
  provider-side escaping guarantee).

## [1.5.0] — 2026-05-28

### Added — UI/UX redesign (cards + dark mode + plain-language labels + chat bubbles)

- **Light Fluent design system + mirrored dark mode.** Tokens centralised
  in `ui/theme/_tokens.py` (`ThemeMode { SYSTEM, LIGHT, DARK }` +
  `LIGHT_TOKENS` / `DARK_TOKENS` palettes + drop-shadows for
  `QGraphicsDropShadowEffect`); `apply_theme(app, mode)` loads
  `light_fluent.qss` or `dark_fluent.qss`, updates the active palette, and
  re-installs card shadows. Both QSS expose **exactly** the same selector
  set (anti-regression guard `tests/unit/ui/test_theme_sync.py`). New
  **Edit → Global settings → Appearance** entry persists the choice in
  `ui_prefs.json` (`ThemeController`).
- **Cards with soft shadows everywhere.** The 6 settings screens
  (GlobalSettings, NewProject, GenerationSettings, PedagogySettings,
  ChatSettings, PromptsEditor) and dashboards switch to a card-based
  visual rhythm — `card()`, `page_header()`, `section_label()`,
  `field_hint()`, `horizontal_separator()`, `install_shadow()` in
  `ui/_components.py` (shared bricks).
- **Plain-language glossary labels.** The glossary header replaces
  "term / acronym / meaning / definition" with friendlier wording aimed
  at non-technical end users; LLM prompts stay aligned with the new
  rendered text.
- **Project sidebar redesigned.** Each project shows a coloured status
  pill + name + subtitle (last run summary), wider list, hover/selected
  states reworked, scrollable settings pages.
- **Chat bubbles aligned + citation chips.** Dialogue bubbles use proper
  rounded shapes (custom `QPainter` background, no more pixel-grained
  edges); citation chips floated under each answer.
- **Cost-estimate dialog redesigned as a card layout** (sections, totals,
  ranges, cap warnings).
- **Polish round** after capture-by-capture review: spinbox arrows
  visible again (native arrows + `padding-right`), spinbox hit-areas,
  dialog footers, `SourceOrderView` refresh, "Reasoning intensity"
  greyed out when "Deep reasoning" is off, label homogenisation, dark
  mode audit (`CostMatrixView` honours the active theme).

### Added — Native Qt internationalisation (French / English)

- The whole user interface is now **fully internationalised** through the
  native Qt translation stack. Source language is **French** (literal strings
  in code); the **English** target is generated from `.ts` editable sources
  compiled into `.qm` binaries and loaded at startup by `QTranslator`.
- New `i18n/` layer (`src/fahmi2/i18n/`):
  - `languages.py` — pure-Python (no Qt deps) `AppLanguage { FR, EN }` enum,
    `LANGUAGE_LABELS` native labels, `DEFAULT_LANGUAGE`. Importable by
    services without pulling Qt.
  - `__init__.py` — Qt-aware: `install_translator(app, lang, dir)` +
    `bundled_translations_dir()` + module-level `_ACTIVE_TRANSLATORS` cache
    that detaches previous translators with `setParent(None) +
    deleteLater()` (prevents Windows heap corruption `0xc0000374` under
    test).
  - `translations/fahmi2_<code>.ts` — editable XML sources, versioned.
  - `compiled/fahmi2_<code>.qm` — binary compiled output, **gitignored**,
    regenerated by `scripts/i18n_compile.py`, bundled at build time via
    `packaging/fahmi2.spec` (`datas`).
- New `LanguageController` (`src/fahmi2/app/language_controller.py`,
  mirror of `ThemeController`) reads/persists the chosen language in
  `%APPDATA%/Fahmi2/ui_prefs.json` (`ui_preferences.py` extended with a
  `language: AppLanguage` field) and installs the matching `QTranslator`
  **before** widget construction (Qt does not propagate `LanguageChange`
  retroactively to `tr()` strings).
- New entry **Edit → Global settings → Language**: pick *Français* /
  *English*; the change applies at the next launch.
- Translation patterns enforced across the UI:
  - `self.tr("…")` for class methods (the context is the class name).
  - `QCoreApplication.translate("LiteralContext", "literal FR source")` for
    free functions and helpers (literal context, never a variable —
    `pyside6-lupdate` does not follow wrappers).
  - `QT_TRANSLATE_NOOP` + `typing.cast(str, …)` for module-level constants.
  - `localize_button_box` (replaces `frenchify_button_box`) translates Qt
    standard buttons via `QCoreApplication.translate("StandardButtons", …)`.
- Labels exposed as **functions** returning dicts (e.g.
  `llm_model_labels()`, `embedding_model_labels()`, `cloud_stt_model_labels()`,
  `export_labels()`) so the resolution happens at each call → re-translatable
  if the language changes between launches.
- Domain-FR vs UI-EN dichotomy: `pedagogy/labels.py` stays in French (used in
  LLM prompts to preserve generation quality); the UI translates
  independently through `ui/pedagogy_labels.py` helpers
  (`audience_display_label()`, etc.).
- New scripts: `scripts/i18n_extract.py` (wraps `pyside6-lupdate -extensions
  py`), `scripts/i18n_compile.py` (wraps `pyside6-lrelease`),
  `scripts/i18n_inventory.py` (inventory of untranslated strings).
- ≥ 28 distinct Linguist contexts, 485 strings, 100 % translated to
  English. Parametric anti-regression tests cover ≥ 1 string per context.
- Documentation: full new section in **§5** of
  [docs/06-procedures-techniques.md](docs/06-procedures-techniques.md) (extract /
  compile / inventory / adding a language / source patterns). Bundling
  recipe in [packaging/README.md](packaging/README.md).

### Migration phases

- **Phase 0** (commit `67ae0f1`) — foundations + `MainWindow` pilot (menus,
  "About" dialog).
- **Phase 1** (commit `c716aa2`) — main cockpit surface (sidebar, tabs,
  dock, stats, logs).
- **Phase 2** (commit `cbee8af`) — all configuration dialogs + internal
  widgets.
- **Phase 3** — chat view, cost matrix, pedagogy progress, controllers'
  `QMessageBox`es.
- **Phase 4** — helpers (`_export_ui`, `_fs`), viewmodels (`run_matrix`,
  `pedagogy_state`).
- **Phase 5** — extended parametric smoke tests (~60 strings) + CLAUDE.md
  sync + documentation translation (this entry).

### Documentation — Full translation to English

- All user-facing documentation is now in **English**: `README.md`,
  `packaging/README.md`, `CHANGELOG.md`, `CLAUDE.md`,
  [docs/01-presentation-fonctionnelle.md](docs/01-presentation-fonctionnelle.md),
  [docs/02-presentation-technique.md](docs/02-presentation-technique.md),
  [docs/03-installation.md](docs/03-installation.md),
  [docs/04-parametrage.md](docs/04-parametrage.md),
  [docs/05-exploitation.md](docs/05-exploitation.md),
  [docs/06-procedures-techniques.md](docs/06-procedures-techniques.md),
  [docs/07-guide-utilisateur.md](docs/07-guide-utilisateur.md).
- Project convention **unchanged**: code, comments, docstrings, log
  messages, user-facing UI strings (FR source), and commits remain in
  French. Only the **documentation** has been translated. The
  `docs/superpowers/specs/` and `docs/superpowers/plans/` archives stay in
  French (session archives).

## [1.4.3] — 2026-05-28

### Added — Dialogue: readable, clickable citations

- Dialogue citations are now **numbered markers `[1]`, `[2]`… clickable**
  inline in the answer (instead of the raw `[§N]` marker), linked to a
  **"Sources"** list **identically numbered** (`[N] Chapter › Section`).
  Clicking a marker — in the text or in the list — opens the source
  excerpt. Internally, `resolve_citations` rewrites the LLM's `[§N]`
  markers as Markdown links `[[N]](anchor)` (**sequential numbering,
  deduplicated by anchor**; out-of-range markers stripped); `Citation`
  carries the **display number**, persisted with **by-position migration**
  for older conversations. Language-independent (marker not localised,
  anchors aligned on the conversation's language).

## [1.4.2] — 2026-05-28

### Changed — Dialogue: language displayed in the conversations list

- Each conversation in the side list is now **prefixed by its language
  code** (e.g. "EN · what is ebitda?"). Because a conversation keeps a
  **fixed** language (reading, citations, and answer), this prefix lifts
  the ambiguity between conversations in different languages — previously
  indistinguishable in the list.

## [1.4.1] — 2026-05-28

### Added — Dialogue: selectable corpus language

- **Per-conversation language choice.** The Dialogue is no longer limited
  to the source language: a selector (on the left, visible as soon as at
  least **2 languages** have been produced) sets the language of a **new
  conversation**. This language drives **everything**: the document read,
  the **cited references**, and the **answer language**. One conversation =
  one language (to change, create a new conversation). The semantic index
  stays **per language** and is built **on demand** (no embeddings for
  unused languages; lexical stays free). Relies on
  `Conversation.language` (already persisted); no data migration.

### Fixed — Glossary fully localised downstream (Pedagogy + Dialogue)

- Glossary **definitions** stayed in the **source language** in revision
  materials and the Dialogue (only the term was localised). The
  translated definition, **already computed** by phase 6 (proven by the
  exported `glossary.{lang}.md`) but **thrown away** at persistence time,
  is now **kept**: `cross_lang` carries **term + definition**
  (`LocalizedTerm`). **No additional LLM call.** The glossary chunks cited
  in the Dialogue and the terminology injected into the materials are
  therefore **fully in the target language**. The `acronym_expansion`
  column (*Meaning*) stays invariant (business convention). Parser is
  **tolerant** to the legacy format (term only → definition falls back on
  the source).

## [1.4.0] — 2026-05-27

### Added — 5 additional languages (German, Spanish, Italian, Chinese, Arabic)

- The `Language` enum goes from **2 to 7 languages**: addition of
  **German**, **Spanish**, **Italian**, **Chinese**, and **Arabic**, on top
  of French and English. The 7 languages are handled **on input and on
  output** for the **3 features** (Generation, Revision materials,
  Dialogue): STT detection, glossary, materials, and chat included.
- **STT**: Whisper language detection aliases (OpenAI full name → ISO
  code) extended to the 5 new languages ("german" → `de`, "chinese" →
  `zh`, …).
- **Localised glossary**: table headers (Term / Acronym / Meaning /
  Definition) and glossary title translated for all 7 languages
  (`_HEADERS_BY_LANGUAGE`, `_TITLE_BY_LANGUAGE` in `domain/glossary`).
- **Centralised language labels** (`domain/languages`: `language_label` /
  `language_display_label`), **single source** reused by the UI
  (capitalised language combos), the PDF/HTML/DOCX, and the Dialogue.
- **Known limitation (Chinese)**: the Dialogue's **lexical** retrieval
  (TF-IDF, `\b\w+\b` tokenisation) is poorly suited to Chinese (no spaces
  between words) → prefer the **semantic** mode (the `AUTO` default routes
  there as soon as an OpenAI key is present). Arabic (words separated by
  spaces) is not affected.

### Added — Word export (`.docx`)

- New **Word `.docx`** export format for **Generation** (consolidated +
  glossary, one file per language) and **Revision materials** (one file
  per material and per answer key), alongside Markdown / PDF / HTML /
  Anki. The HTML body is **rendered once** (`render_markdown_body`,
  `tables` / `toc` extensions, shared HTML/PDF/DOCX) then converted to
  `.docx` via **`htmldocx`** (on top of `python-docx`). Settings:
  `GenerationSettings.export_formats` / `PedagogySettings.export_formats`
  (opt-in).
- **Tables**: `htmldocx` translates neither CSS borders nor `width:
  100%` → its tables come out borderless and at automatic width; they are
  reformatted after conversion (style **Table Grid** + width **100 %**,
  `tblW` in percent) to match the HTML/PDF rendering.
- **Landscape orientation** (option `landscape`, e.g. glossary) applied
  to the document sections (`WD_ORIENT.LANDSCAPE` + width/height swap),
  like the PDF.
- **Right-to-left Arabic**: explicit RTL direction — `w:bidi` on
  paragraphs, `w:rtl` on runs, `w:bidiVisual` on tables (column order
  reversed) — aligned on the PDF (`direction:rtl`) and HTML (`dir="rtl"`).
  Toggles inserted at the valid OOXML schema position via
  `insert_element_before`. Word handles **natively** CJK font substitution
  and line breaking: nothing to declare on the DOCX side for Chinese.
- Export dependency **`htmldocx`** (+ `beautifulsoup4`; `lxml` is already
  pulled by `python-docx`). Wired in `packaging/fahmi2.spec`
  (`hiddenimports += ['htmldocx']` + `collect_submodules('bs4')`).

### Added — PDF rendering of the new languages (Chinese CJK + Arabic RTL)

- **Chinese**: **Microsoft YaHei** font (`msyh.ttc` system font, loaded
  via `subfontIndex`) injected into `xhtml2pdf.default.DEFAULT_FONT` (with
  `EXPORT.NO_CJK_FONT` guard if the font is missing). Because Chinese is
  written **without spaces** and ReportLab only breaks at spaces, **CJK
  prose is pre-broken** with `<br/>` (per **whole block**, width derived
  from the A4/margin constants) and **table cells** by the CSS rule
  `-pdf-word-wrap: CJK` (the only context where it does not crash in
  xhtml2pdf 0.2.17).
- **Arabic**: **Arial** font (Arabic glyphs) + `direction:rtl` + tag
  `<pdf:language name="arabic"/>` that triggers **contextual joining** and
  **bidi** (`arabic-reshaper` / `python-bidi`, transitive deps of
  xhtml2pdf).
- **Per-language PDF font**: Latin (fr/en/de/es/it) → Arial (resolved as
  Helvetica, covers Latin-1); Chinese → YaHei; Arabic → Arial + RTL.
  **All system Windows fonts — nothing to bundle.**
- **Landscape glossary** extended to **DOCX** (was already PDF); dedicated
  column widths in PDF.

### Added — Glossary terminology localisation (phase 6)

- The glossary **terms** are now **localised by target language** through
  a **structured LLM call** (`_localize_glossary`, editable
  `phase_6_glossary_localization` prompt): translate-unless-international,
  acronym preserved, acronym expansion invariant. Pairing **by source
  term** first, fallback by **position**, then fallback on the source
  term.
- Phase 6 now **renders `glossary.{L}.md` deterministically** (the
  glossary is no longer a translation task), **injects the real source →
  target equivalents** into the translation of the consolidated document
  and the per-source docs, and **persists `cross_lang`** in
  `glossary_master.json` (atomic write).
- **Propagation**: the **Pedagogy** (`SupportsOrchestrator`) and the
  **Dialogue** (`corpus.load_corpus_chunks`) **pre-localise** the glossary
  to the content language they load. **Single source**:
  `domain/glossary.localize_glossary_terms`.
- **Known limit**: only the **term** is carried by `cross_lang`
  (downstream, the **definition** stays in the source language); the
  **exported** `glossary.{L}.md`, however, is fully localised.

### Fixed — Table rendering (Markdown / PDF / HTML / DOCX)

- **Pipe tables glued or indented not rendered.** A Markdown table glued
  to the text (no blank line before/after) or indented came out as
  **literal `|` characters** instead of a real table (the python-markdown
  `tables` extension requires blank lines around it). Deterministic
  normalisation upstream of the 4 formats (`_normalize_table_blocks`:
  blank line before/after + de-indent, **preserving code blocks**), plus
  renumbering of ordered lists split by a table (`<ol start>`).
- **Arabic squares in italics (PDF).** Arial *Italic* / *Bold-Italic* have
  no Arabic glyphs → any italic Arabic passage came out as squares. Font
  family **`AppArabic`** falls back to upright (regular / bold) for the
  italic variants.
- **Chinese overflowing on the right (PDF).** Chinese paragraphs
  overlapped / overshot the right margin, including after an inline
  **bold** term (breaks were computed per node, ignoring the bold offset).
  Fixed by pre-breaking CJK prose **at block level** (flattened text,
  inline tags included).
- **Glyphless characters (PDF).** Any character absent from the active
  font (decorative emojis 📖 / 📝 / 💡 / 🎯…) is **stripped before
  rendering** (ReportLab would otherwise draw a square; categories
  Cc/Cf/Zs/Zl/Zp kept, including ZWJ/RLM for Arabic); HTML and DOCX, on
  the other hand, **keep them**. Rare Unicode dashes (U+2010/2011/2012/2015)
  normalised on PDF rendering.

### Technical

- **`domain/languages.is_rtl`** + `_RTL_LANGUAGES`: **single source** for
  right-to-left direction (PDF + HTML + DOCX). **`_CJK_LANGUAGES`**: single
  source for the "CJK language" decision (YaHei font + pre-break).
- **`ExportDocument`** now carries the content **language** (drives font
  and direction of PDF/HTML/DOCX rendering), on top of `landscape`
  orientation and PDF column widths; populated by both features'
  collectors.
- Glossary table cell escaping (`|` → `\|`, line breaks → space)
  **centralised** (`_escape_table_cell`, applied to all 4 columns).
- PDF font sizes and `@page` margin **centralised** (single source for
  the CSS template ↔ CJK pre-formatting width computation).

## [1.3.0] — 2026-05-26

### Added

- **"Thematic rewrite" consolidation mode (phase 5).** New setting
  `GenerationSettings.consolidation_mode` (default `ORDERED`, unchanged):
  in `THEMATIC` mode, the LLM **aggregates and restructures** content
  from all sources by theme (a journalist-style synthesis), instead of one
  chapter copied per source. **Strict on facts** (no invented or added
  facts; figures/data/reasoning preserved; conflicts between sources shown
  without arbitration) and **flexible on form** (merging, deduplication,
  transitions). Implemented as **provenance-tracking map-reduce** (factual
  ledger per source → thematic plan → per-chapter writing → meta) with
  **double deterministic coverage check** (no content loss) and **no
  technical identifier in the deliverable**. Artefacts kept and inspectable
  under `generation/consolidation/` (including `facts.md`). Intra-phase
  resume via consistency hash. Phase 5 refactored as a **strategy
  dispatcher** (`ORDERED` unchanged). 3 editable prompts
  (`phase_5_fact_ledger`, `phase_5_thematic_plan`,
  `phase_5_thematic_chapter`). Selector in the settings (**Style** page);
  in thematic mode, source order has no effect (UI note). Cost estimation
  includes a dedicated factor.

### Fixed

- **Dialogue: corpus freshness after regeneration.** The Dialogue's
  corpus was loaded once at project selection; after a document
  regeneration, the Dialogue kept citing the **old** corpus (stale
  chapters/sections). It now **automatically reloads** its corpus as soon
  as the consolidated document or glossary has changed on disk (before
  every answer and on the generation-finished signal), without reloading
  the project. The semantic index fingerprint additionally includes the
  **glossary mtime** (a definition edit at constant term count no longer
  leaves stale embeddings around).

### Changed

- **Project deletion: project folder is also wiped.** Deleting a project
  now also wipes, on top of its runs/metadata in the database, its
  **workspace folder and all its content** on disk (best-effort;
  confirmation shows the path). The **input folder** (source files) and
  the global database are not touched.

## [1.2.0] — 2026-05-26

### Fixed

- **Dialogue: typed and localised embedding errors.** A failed OpenAI
  embedding computation (key refused, rate limit) bubbled up as a raw
  exception, unlike the STT/LLM adapters. It is now converted to a typed
  `EmbeddingError` with a French message and an advice ("switch the
  retrieval to lexical").
- **Dialogue: citations aligned with the document outline.** The corpus
  was chunked/cited on **all** heading levels (`####`+ included), so that
  sub-sub-sections **absent from the outline** (deep headings with
  inherited numbering, e.g. "5.2.1") appeared as sources. Chunking is now
  done at the **same levels as the outline** (`##`/`###`, depth 3); `####`+
  remain indexed content attached to their parent section. Citations
  therefore only reference sections **actually present in the final
  document**. *(Immediate effect, no regeneration.)*
- **Consolidation: inconsistent numbering of deep headings.** The
  renumbering only handled `##`/`###` headings; `####`+ headings (beyond
  the TOC depth) **kept the source's inherited numbering** (e.g. `#### 5.2.1`
  next to a renumbered `### 1.6.1`), giving the impression of two
  documents mixed in the consolidated file. These deep headings are now
  **stripped of inherited numbering** (they remain unnumbered by design).
  *(Regenerate to refresh an existing consolidated document.)*
- **Dialogue: answer sources on distinct lines.** Cited sources
  (`§ Chapter › Section`) were displayed side by side on a single line
  (unreadable with several of them); they are now listed one per line.
- **Generation: truncated output for large sources.** LLM phases
  (rephrasing, structuring, translation, coherence) process each source
  in one call and didn't set `max_tokens` → DeepSeek applied its **small
  default** and **silently truncated** long outputs (large
  document/transcription), causing an incomplete `consolidated.{lang}.md`.
  Now: `max_tokens` set to the **model maximum**
  (`DEFAULT_MAX_OUTPUT_TOKENS = 384_000`, output ceiling shared by both
  DeepSeek V4 models) **and** detection of residual truncation
  (`finish_reason="length"` → explicit `LLM.OUTPUT_TRUNCATED` error instead
  of a silent loss). This ceiling is now **the default for all DeepSeek
  calls** (single source `invoke_llm_chat`): generation, **revision
  materials** (large materials like the mock exam), **Dialogue** (answers
  + query expansion) — no more truncated long outputs.
- **Generation → Settings → Input & languages**: the "Sources to process"
  and "Excluded" lists were height-bounded. The "Sources to process" list
  now follows the window height (vertically expandable, priority over
  "Excluded"), useful when there are many sources to order.

### Changed — Generation languages: a single control

- The **Input & languages** settings merge "Source language" and "Output
  languages" into **a single control**: **Produced** checkboxes + a
  **Primary** dropdown (which only lists produced languages). The primary
  is the **original** version (written directly, translation pivot, STT
  hint); the other produced languages are translations of it. Lifts the
  ambiguity of the previous pair (especially with multilingual inputs)
  and allows clearly picking any language as the primary. Behaviour and
  data model unchanged (`source_language` = primary, `output_languages` =
  produced; the primary is always produced, at least one language remains
  produced).

### Changed — Revision materials status banner

- The freshness banner becomes a **coloured status badge** (icon + short
  label, success/warning/accent palette), instead of a verbose phrase
  mixing state and instruction: *⚙ To configure*, *⚠ Generation required*,
  *● Ready to generate*, *✓ Materials up to date* (green), *⟳ Materials to
  regenerate* (amber). Styled via QSS
  (`#pedagogyStateBanner[state="…"]`), hidden when no project is
  selected.

### Changed — Unified model labels

- The **model** combos (LLM, embeddings, STT) display everywhere a
  consistent **descriptive label** ("DeepSeek V4 Flash (cheap)",
  "gpt-4o-mini-transcribe (2× cheaper)", …), in **Generation**, **Revision
  materials**, and **Dialogue**. Labels centralised in `ui/_model_labels`
  (single source) with a completeness guard (every model has a label).

### Added — STT model choice (generation)

- **Configurable transcription model**, per provider, like the LLM model
  (**Transcription** page in settings):
  - **local** (faster-whisper): `large-v3-turbo` (default), `large-v3`,
    `medium`, `small` — downloaded **on first use** (cache
    `%LOCALAPPDATA%/Fahmi2/models/`, no weights packaged);
  - **cloud** (OpenAI): `whisper-1` (default), `gpt-4o-transcribe`
    (better precision), `gpt-4o-mini-transcribe` (2× cheaper). The
    `gpt-4o-*` models do not return segment timestamps (`json`) → the
    adapter produces a **single segment per slice** (offset + duration
    from the preparer), the transcribed content staying identical.
    `whisper-1` keeps `verbose_json` (unchanged).
- **STT cost per model** (grid `infra/stt/_pricing` shared by estimation
  and real cost): pre-run estimation and real cost reflect the chosen
  cloud model.
- The irrelevant model combo (depending on the chosen provider) is
  **greyed out**; settings persisted in the v2 blob (lenient
  deserialisation → defaults).

### Added — Dialogue (corpus-anchored chat)

- New **Dialogue** tab: conversational chat anchored on the corpus
  produced by Generation (consolidated **document** + **glossary**).
  **Cited** answers (chapter › section, clickable, **passage preview as
  tooltip on hover**) and **streamed** (token by token).
- **Configurable fidelity**: **strict** mode (answer only from the
  course, polite refusal off-corpus) or **augmented** mode (clearly
  labelled "Beyond the course" complement).
- **Retrieval as an extensible port**: **lexical TF-IDF** (offline) or
  **semantic** (OpenAI embeddings); **AUTO** strategy (semantic if an
  OpenAI key is present, otherwise lexical) with **LLM query expansion**
  on demand. Semantic index persisted (`chat/index.{lang}.npz`) with a
  validity fingerprint.
- **Configurable embedding model** (cloud mode): `text-embedding-3-small`
  (default), `text-embedding-3-large`, or `text-embedding-ada-002`,
  picked in the settings like the LLM model. Changing model
  **reindexes** the corpus (the model is part of the index fingerprint).
- **Multiple conversations** persisted per project, **deletable**
  (right-click in the list → "Delete conversation", with confirmation);
  **cost** per message and cumulative **comprehensive**: it aggregates
  the answer (DeepSeek), the **embeddings** of the semantic retrieval
  (initial indexing + each question), and the query-expansion
  reformulation (pricing grid **per embedding model**, generic).
- Dedicated settings (⚙); editable prompts `chat_strict` /
  `chat_augmented` / `chat_query_expansion` from the UI.

### Technical

- New engine package `chat/` (corpus + chunking, streaming `ChatService`,
  citations, query expansion). `PassageRetriever` port (`core/retrieval`),
  `EmbeddingProvider` port (`infra/embeddings`) +
  `SemanticPassageRetriever` (`infra/retrieval`). **Additive** extension
  of the `LLMProvider` port (`chat_stream`, `stream_options.include_usage`)
  — pipeline and pedagogy **unchanged**.
- **Embedding cost accounting**: `consumed_cost_usd()` added to the
  `EmbeddingProvider` and `PassageRetriever` ports (lexical → 0; semantic
  → embeddings cost; query expander → reformulation cost). Generic pricing
  grid `infra/embeddings/_pricing` (USD/Mtok per model, default fallback).
  `ChatService` aggregates this cost into `ChatMessage.cost_usd` for an
  exhaustive total.

## [1.1.0] — 2026-05-22

### Added — Broadened generation inputs

- The generation now accepts, **on top of videos**, **audio files** (wav,
  mp3, m4a, flac, ogg, opus, aac), **YouTube links** (single videos,
  audio downloaded by yt-dlp), and **text documents** (PDF, Word,
  Markdown, txt). **Mixed** sources accepted in the same project.
- New setting **"Rephrase text documents"** (ticked by default):
  unticked, documents are inserted as-is (phase-3 pass-through, cost 0,
  structure preserved).
- **Source ordering & exclusion**: reorderable **dual-list** component
  (drag-and-drop) in **⚙ Settings** — the processing order defines the
  chapter order of the consolidated document; any source can be excluded
  then re-included. "Refresh" keeps the exclusions.
- **Ingestion as ports/adapters** (`infra/ingestion/`): `SourceKind →
  SourceIngestor` dispatcher (modelled after `PhaseRegistry`); phases 1–7
  remain unchanged (pivot "one transcription per source").

### Changed

- Foundational rename `video → source` (`SourceId`, `SourceExecution`,
  `Run.sources`, pipeline events, `LogEvent.source_id`) **and idempotent
  SQLite migration** (`video_id → source_id`; `source_kind` /
  `source_location` columns; legacy rows → `source_kind='video'`).
- **Cost estimation** reasons per **source** (`SourceWeight`: media audio
  duration **or** document text tokens; STT excluded for documents).
- "Sources"-oriented UI: matrix labels, stats strip ("Sources" card), and
  estimation dialog.

### Dependencies

- Added `pypdf` (PDF extraction) and `python-docx` (.docx extraction).
  `yt-dlp` is used as a **binary** (bundled at build time via
  `packaging/fetch-ytdlp.ps1`, replaceable without rebuild; override via
  the `FAHMI2_YTDLP` environment variable).

## [1.0.0] — 2026-05-22

First official version. Complete generation pipeline (STT + 7 LLM
phases), revision materials (8 types), Anki / Markdown / PDF / HTML
exports, parallelised processing, cloud STT with no duration limit,
portable Windows packaging.

### Added — Generation document export

- New **Export** button in the Generation tab: writes the **consolidated
  document** and the **glossary** (one file per language) in **Markdown /
  PDF / HTML** to a chosen folder. Formats configurable in **⚙ Settings →
  Export** (`GenerationSettings.export_formats`, **opt-in**: none ticked
  by default).

### Changed — Revision materials export (granularity)

- The **Markdown / PDF / HTML** exports now produce **one file per
  material and per answer key** (`<material>.<lang>.<ext>` /
  `<material>.<lang>.corrige.<ext>`), instead of one aggregated document
  per language. Each HTML is a self-contained document. The **Anki
  `.apkg`** export is unchanged.
- **Factorisation**: shared writing core `app/document_export.py`
  (`write_documents` + `ExportDocument`) + UI helper `ui/_export_ui.py`.
- **PDF engine**: the PDF is now rendered **from HTML via `xhtml2pdf`**
  (ReportLab, pure Python) instead of `fpdf2` — real pagination
  (TOC/lists/multi-page tables), CSS typography, **clickable TOC**,
  **landscape glossary** with readable columns. Dependency `fpdf2`
  replaced by `xhtml2pdf`.
- **Clickable HTML TOC**: heading ids aligned on the TOC anchors via the
  `toc` extension + `core/slugify.slugify_anchor` (single source).
- **Tables** rendered (python-markdown `tables` extension); rare Unicode
  dashes not rendered by ReportLab+Arial normalised at PDF rendering.

### Fixed — Cloud STT (OpenAI Whisper): large files & language

- **Files > 25 MB support**: the audio is now **compressed to Opus** (24
  kbps mono) before sending to OpenAI, and **split at silences** if
  necessary (courses > ~2 h), then the transcriptions are stitched back
  together. The cloud STT therefore works for **any duration** of course
  (OpenAI's 25 MB limit capped raw audio at ~13 min). Benefit: the upload
  is **much faster** (a 22 MB WAV → ~3 MB Opus), which removes the
  slowness that could be mistaken for a freeze.
- **Detected language**: fix to the parsing of the language returned by
  OpenAI Whisper (full name "french" instead of the ISO code "fr"),
  which made every cloud transcription fail.
- **Robustness**: explicit OpenAI client timeout; `libopus` encoder
  guaranteed in the bundled ffmpeg (verified at build).

### Added — Processing parallelisation (generation + pedagogy)

- **Revision materials in parallel**: the orchestrator processes the
  *(language × material)* units concurrently through a bounded thread
  pool. New **"Parallel tasks"** setting (`llm_workers`, default 16,
  range 1–64).
- **Parallelised generation pipeline**: the **per-video** phases (cloud
  STT, term extraction, rephrasing, structuring) are processed
  concurrently; the final phases parallelise translation *(language ×
  document)*, the coherence pass *(per language)*, and the consolidation
  summaries. **"Parallel transcriptions"** (`stt_cloud_workers`, default
  3, range 1–8) and **"Parallel LLM calls"** (`llm_workers`, default 16,
  range 1–64) settings. **Local** STT remains sequential (1 GPU).
  Determinism of documents and checkpoint resume are preserved; the cost
  cap is *best-effort* in parallel (slight overshoot possible by
  in-flight requests).
- **DeepSeek client timeout** raised to 600 s (absorbs slow requests
  under server keep-alive).

### Added — Sidebar: per-project status & "Reset" button

- **Sidebar status icons**: each project is prefixed by the status of the
  last **generation** run (G) then **pedagogy** (P) — e.g. `G ✓ / P ▶
  Name` —, refreshed live when a run starts or finishes (detailed
  tooltip).
- **"Reset" button** (per tab): wipes everything generated for the
  feature — disk deliverables **and** database history (runs/phases) for
  Generation; materials folder (artefacts + manifest + state) for
  Pedagogy. Confirmation required; disabled during a run.

### Added — Dashboards: generation / pedagogy homogeneity

- **Pedagogy run status persisted** (`pedagogy/run_state.json`): pedagogy
  now exposes a `RunStatus` consistent with generation (created / running
  / completed / failed / cancelled / paused), persisted to disk (the
  orchestrator writes `RUNNING` at start and the final status), so it is
  readable outside a session.
- **Pedagogy dashboard**: the **Status** tile shows "Running" during
  generation; new **Duration** tile (refreshed live).
- **Generation dashboard**: new **Languages** tile (output languages).

### Changed — Pedagogy: regeneration aligned on generation

- **Re-running regenerates**: "Generate" on a **complete** set of
  materials (all present and up to date) now **regenerates** them
  (overwrites), like re-running the Generation after a completed run —
  instead of skipping everything (which felt like a freeze). An
  **incomplete** set (interruption, cap reached) is still **resumed**
  (fresh materials are kept, only the missing ones are generated). The
  "Materials up to date" banner now indicates that re-running will
  regenerate them.

### Changed — Pedagogy: exports & language (usage feedback)

- **Pedagogical export order** (Markdown / PDF / HTML): the aggregated
  documents first present the **learning** materials from the most
  general to the most specific (sheet → key points → flashcards), then
  the **exercises** from the most specific to the most general (cloze →
  true/false → MCQ → open questions → mock exam).
- **Output language reinforced (all materials)**: the **8 material**
  prompts now insist on writing **entirely in the target language**
  (translating the source content instead of copying it, not copying the
  source phrasings) — generalises to every type (MCQ, true/false, cloze,
  open questions, mock exam, flashcards, sheet, key points) what was
  partial; fixes materials staying in the document's language when the
  target language differed.

### Fixed — PDF export: heading colour

- The PDF **headings** are now in **bold black** (instead of the
  `#960000` red default of fpdf2) and the **bullets** in dark grey —
  more sober and readable rendering.

### Added — HTML export & dedicated section

- **HTML export**: new export format for materials — a **self-contained**
  HTML document (UTF-8, embedded style sheet) openable in a browser,
  aggregated by language (subject / answer key separated).
- **Dedicated "Export" section** in the pedagogy settings: the export
  formats (Anki / Markdown / PDF / HTML) have their own category, moved
  out of "Model & cost".

### Fixed — Logs panel: level filter

- The **"Minimum level"** selector now re-filters the **existing
  display** (and not just new events): raising the threshold hides lines
  below the level, lowering it makes them reappear (all events are
  kept).

### Changed — Pedagogy: material quality & formatting

- **Enriched formatting**: materials make more use of Markdown (airy
  sheets and exams — subheadings, lists, separated paragraphs; better
  structured flashcards and justifications). The **Anki** export now
  converts the Markdown of fields into **HTML** (lists/bold rendered
  properly); the Markdown and PDF exports are unchanged. Cloze card text
  stays raw (cloze mechanics preserved).
- **Refined prompts (relevance)**: targeted directives per material type
  (homogeneous, non-guessable distractors in MCQ; non-trivial assertions
  in true/false; cloze on key concepts; analysis questions in open
  questions; hierarchised key points; progressive-difficulty exam), for
  more relevant content. Overrides in `%APPDATA%/Fahmi2/prompts/` stay
  prioritary.

### Fixed — Pedagogy: language & dashboard (usage feedback)

- **Non-blocking target language**: you can generate materials in a
  language (e.g. EN) even if Generation has only produced another (e.g.
  FR) — the LLM writes in the target language from the available
  content. The status banner no longer blocks as soon as **at least one**
  consolidated document exists (any language). Freshness follows the
  mtime of the **actually used content document** (no more false
  "stale" for a material generated from another language). Content
  language resolution centralised
  (`pedagogy/sources.resolve_content_language`, shared by the
  orchestrator and the status banner).
- **Pedagogy dashboard rebuilt on selection**: returning to an
  already-generated project re-shows the **last execution state**
  (completed materials + cost, read from disk artefacts) instead of an
  empty grid — at parity with the Generation dashboard.

### Fixed — Code review (dashboard consistency)

- **Pedagogy "Cost" tile**: now shows the **cap** and the **visual
  accent** (warning ≥ 80 %, danger ≥ 100 %), at parity with the
  Generation dashboard.
- **Pedagogy preview**: on selecting a configured project, the materials
  × languages matrix is shown **pending** (instead of an empty grid),
  consistent with the detected-videos preview on the Generation side.
- **DRY / consistency**: Run-status labels and accents centralised
  (`ui/status_labels`, shared by the two tile strips); **canonical**
  material order in the estimation dialog; bold reserved for matrix
  **totals**; matrix turned read-only (no more partial selection
  highlight); `CostMatrixView` dimension constants centralised.
- **Documentation**: `docs/02` and `CLAUDE.md` realigned (removal of
  `glossary_terms` / `GlossaryReconciler`, addition of the shared
  components `CostMatrixView` / `StatCard` / `cost_matrix`).

### Changed — Cost estimation (Lot 3d)

- **Granular pre-run estimation + range**: the "Estimate cost" dialog
  decomposes the budget **per phase** (generation) / **per material**
  (pedagogy) and displays the total as a **±33 % range** ("indicative
  estimation": `≈ $X` + `range $low – $high`), with a **warning** if the
  upper end may exceed the cap. Both dialogs share the same rendering
  (`ui/cost_estimate_dialog`). `CostEstimation.per_phase_usd` and
  `low_usd`/`high_usd` added (shared constant
  `ESTIMATE_UNCERTAINTY_RATIO`).

### Changed — Generation dashboard (Lot 3c)

- **Generation matrix migrated to the shared `CostMatrixView`
  component**: now shows the **cost per cell** (phase × video, discrete)
  and the **totals** (per video, per phase, overall). Batch phases carry
  their cost in the column total (run-level cost). New
  `SqliteState.list_phase_cells` query (status + cost per phase ×
  video). The old `RunMatrixView` widget and `#runMatrix` QSS are
  removed.

### Changed — Pedagogy dashboard (Lot 3b)

- **Revision materials dashboard aligned on Generation**: the flat table
  is replaced by a **tile strip** (Status / Materials / Languages / Cost)
  and a **2D materials × languages matrix** (status + cost per cell +
  totals, via `CostMatrixView`). The **freshness banner** is kept.

### Added — Shared dashboard UI bricks (Lot 3a)

- **`CostMatrixView`** (+ viewmodel `CostMatrixSnapshot`): generic cost
  matrix (rows × columns) where each cell carries **status + cost**,
  with **totals** (row / column / overall). Common base for the
  Generation and Pedagogy dashboards (consistency + DRY). Cost per cell
  rendered as secondary (small, grey), totals foregrounded.
- **`StatCard`**: reusable indicator card extracted from `stats_strip`
  (icon + value + sub-info + accent), base for the tile strips of both
  dashboards. No rendering change for the existing Generation strip.

### Removed — Pedagogy (Lot 1c)

- **`flashcards_glossary` material removed**: it was the glossary
  reformatted as cards (near-zero transformation value). Pedagogy now
  has **8 material types** (all LLM). The glossary stays a reference
  document and feeds the terminological injection of the prompts.
  Persisted settings referencing the old material are tolerated (unknown
  type ignored on read).

### Changed — Pedagogy (Lot 1c)

- **Material languages decoupled from generation (#4)**: the tab offers
  **all** supported languages; materials are written by the LLM in the
  chosen language even if the source document is in another language.
  The orchestrator resolves a content language (existing consolidated
  doc: the target, else the source language, else the first produced
  one) distinct from the target language.

### Fixed — Homogeneous glossary (Lot 1b)

- **Empty glossary flashcards / empty terminology injection**: pedagogy
  now reads the glossary **from disk** (`glossary_master.json`), exactly
  like the pipeline (`load_glossary_master`), instead of a never-populated
  SQLite table. The LLM generators receive the terms in their prompts
  again.

### Removed — Homogeneous glossary (Lot 1b)

- **Glossary persistence anomaly**: removal of the SQLite
  `glossary_terms` table (idempotent `DROP TABLE` migration), of the
  `upsert_glossary_term` / `list_glossary_terms` methods, and of the
  dead `GlossaryReconciler` service. Glossary master parsing and
  Markdown rendering (`parse_glossary_master_terms`,
  `render_glossary_markdown_table`) moved back up to
  `domain/glossary.py` (reused by pipeline and pedagogy). No generated
  document has a content table in the database: the glossary follows the
  same treatment (disk artefact + `PhaseExecution`).

### Added — UI polish (Lot 1a)

- **Keep audio**: new "Keep extracted audio files" checkbox in
  Settings → Transcription (unticked by default = deletion after STT,
  unchanged behaviour; ticking keeps the `.wav`). Wired on the existing
  `GenerationSettings.delete_audio_after_stt` field.

### Fixed — UI polish (Lot 1a)

- **Tabs visibility**: the feature tabs bar (Generation / Revision
  materials) is now styled (QSS) — the inactive tab is distinct (light
  grey background), the selected tab is white with an accent underline.
  Previously inactive tabs blended into the background.

### Fixed — Code review (SP1–SP3)

- **Anki export**: tags are now sanitised (spaces become `_`). A
  multi-word glossary term ("Artificial Intelligence") no longer fails
  the `.apkg` export (`genanki` refuses tags containing a space).
- **Project deletion**: all tabs are notified
  (`MainWindow.notify_project_deleted`) — the Revision materials tab no
  longer keeps a reference to the deleted project (which could
  **resurrect** it in the database upon a settings save).
- **Generation settings**: editing the generation no longer **loses** the
  Revision materials settings (rebuilds the `Project` via
  `with_generation`).
- **Export formats**: the "📦 Export" menu now only offers the formats
  **actually ticked** in the settings (`PedagogySettings.export_formats`).
- **LLM parsing robustness**: an MCQ/cloze with an invalid schema
  (out-of-range index, too many options, empty answers) raises a typed
  `LLMError` instead of an unhandled exception; `read_artifact` cleanly
  ignores a corrupt item artefact (returns `None`).
- **Pedagogy cost cap**: the `PAUSED` status is now documented and the
  log explicitly indicates "cost cap reached".
- **Miscellaneous**: working "? → About" menu (name + version); "Export
  formats" label in the settings; folder-opening helper shared
  (`ui/_file_explorer`); removal of magic numbers (cost estimator).

### Added — Markdown / PDF export (SP3/02)

- **Markdown and PDF export** of materials from the pedagogy tab: the
  "📦 Export" button now offers 3 formats (Anki / Markdown / PDF).
- Documents **aggregated by language**, **subject / answer key
  separated** (`supports.{lang}.md`, `supports.{lang}.corrige.md`, and
  `.pdf` variants).
- Pure-Python PDF rendering (`markdown` → HTML → `fpdf2`) with a system
  Unicode font; Markdown fallback if no font is resolved. New
  dependencies **`markdown`**, **`fpdf2`**.

### Added — Anki `.apkg` export (SP3/01)

- **Anki export** from the pedagogy tab ("📦 Export" button): generated
  materials are converted to a `.apkg` package (genanki) — flashcards
  (glossary + concepts) → **Basic** notes, cloze → **Cloze** notes, MCQ →
  **custom** note.
- **Stable GUIDs** (re-import without duplicates), **sub-decks per
  material** (`<Project>::<material>`), **tags** (material, language,
  level, chapter).
- Adapter `infra/anki/genanki_exporter.py`, deserialisation
  `pedagogy/artifact_reader.py`, service `app/pedagogy_export.py`. New
  dependency **`genanki`**.

### Added — Revision materials tab (SP2/04)

- **Real pedagogy tab** (replaces the stub): action bar (Settings,
  Estimate, Generate, Pause/Resume/Cancel, Open folder), **status
  banner** (not configured / generation required / ready / up to date /
  stale), and **progress table** (material × language, status, cost).
- **Master-detail settings** (`PedagogySettingsView`): Materials (+
  separate answer key), Difficulty (audience, Bloom, density,
  directives), Languages (produced), Model & cost (model, thinking,
  temperature, cap, export formats).
- **Cost estimation** (`PedagogyCostEstimator`) per material × language
  × chapter according to density and thinking; **cost cap** enforced by
  the orchestrator (clean stop at the safe boundary).
- **`PedagogyController`** (`QThread` worker, pause/cancel) +
  **`PedagogyQtEventBus`** bridging events to the progress table and the
  logs panel.
- Viewmodels testable without Qt (`PedagogyProgressViewModel`,
  `PedagogyStateViewModel`), helpers `pedagogy/sources.py` + shared cost
  heuristics `app/_cost_common.py`.

### Fixed

- Editing a project (renaming) no longer clears the **Revision
  materials** settings (`Project.pedagogy`).

### Added — LLM material generators (SP2/03)

- **8 LLM generators**: concept flashcards, MCQ, true/false, cloze, open
  questions, summary sheet, key points (per chapter), and mock exam
  (full document). Each parses a **typed JSON** response into the
  `domain/supports.py` entities and renders Markdown.
- **8 editable `pedagogy_*.j2` prompts** via "Edit → Edit prompts"
  (`PromptsService` catalogue), parameterised by target audience, Bloom
  objective, density, directives, and glossary.
- **Separate answer keys**: evaluative materials marked "separate answer
  key" produce a `<material>.corrige.md` file distinct from the subject.
- **Deterministic MCQ debiasing** (distribution of the correct-answer
  position across the question set).
- **LLM retry** mutualised with the pipeline: `default_classify` moved
  up to `core/retry/classification.py`; `SupportRetryAttempt` event.
- `pedagogy/generators/_base.py` base (generic per-chapter bases +
  evaluative mixin), `build_default_support_registry()` factory
  (9 generators).

### Added — Revision-material generator (SP2/02)

- **Pedagogy base** (`pedagogy/`): `SupportGenerator` (ABC) +
  `SupportContext` (DI), `SupportGeneratorRegistry` (canonical order of
  the 9 materials), parser of the consolidated document chapters,
  pedagogy events, **freshness manifest** (`pedagogy/manifest.json`),
  and artefact serialisation.
- **Dedicated lightweight orchestrator** `SupportsOrchestrator`
  (`app/`): generation per language × material, JSON + Markdown writing
  under `<location>/pedagogy/`, events, **coarse resume** (skip fresh
  materials), pause/cancel.
- **First vertical slice**: **glossary flashcards** generator (no LLM,
  front = term/acronym, back = definition), from the glossary of the
  last *COMPLETED* run.
- **Generalised LLM/JSON helpers** (`infra/llm/invocation.py`) reused by
  the phase handlers; `EventBus` made **generic** (`EventBus[E]`) to
  also carry the pedagogy events.
- `ProjectService.get_last_completed_run` +
  `create_project(pedagogy=…)`; centralised path constants
  (`GENERATION_OUTPUT_SUBDIR`, `consolidated_doc_filename`).

### Fixed

- A **generation** run no longer clears the **Revision materials**
  settings (`Project.pedagogy`) at its end (regression introduced by
  SP2/01).

### Changed — Multi-feature shell (SP1)

- **Tabbed interface**: the project area is now a `QTabWidget` populated
  by a `FeatureRegistry` — **Generation** tab (existing cockpit) +
  **Revision materials** tab (*stub*, to be implemented).
- **`Project` reduced to identity** (name + location, immutable);
  business parameters live in `GenerationSettings` (extracted from the
  former `ProjectSettings`).
- **Minimal project creation** (name + location); generation settings
  edited from **Generation → ⚙ Settings** (reusable master-detail view
  `SettingsView`).
- **Per-feature workspace**: generation artefacts live under
  `<location>/generation/` (deliverables under
  `…/generation/output/`).
- **Persistence**: `projects.settings_json` blob in **v2**
  (`{version, workspace_folder, generation, pedagogy}`) with lenient
  v1→v2 migration on read (no file move).
- **Internal**: `RunController` → `GenerationController` (decoupled
  from the `MainWindow`); new `ui/features/` package.

## [0.2.0] — 2026-05-19

Major UI iteration + consolidated-document rendering quality + prompt
editing + cost-estimation precision.

### Added

#### UI — theme and cockpit
- **Clear Fluent theme** (Windows 11): consistent global QSS style sheet
  (accent palette `#0078d4`, white surfaces on `#f5f7fb` background),
  `QCheckBox::indicator` styled with an inline SVG ✓ glyph.
- **StatsStrip redesigned with 5 cards**: Status, Videos, Phases,
  Duration, Cost. Each card = icon + title + large value + sub-info. The
  **Duration** card is updated live every second by an internal `QTimer`
  as long as the Run is `RUNNING` or `PAUSED`.
- **Coloured run matrix**: coloured pills per `PhaseStatus` (green ✓,
  blue ▶, grey ·, red ✗, indigo ↷), readable short headers (STT, Terms,
  Glossary, Rephras., Structur., Consolid., Translation, Coherence),
  centred alignment.
- **Logs coloured by severity** (INFO grey, WARN amber, ERROR red, FATAL
  bold red), compact `HH:MM:SS` time, monospace.
- **ProjectHeaderBar**: 17 px bold project title, primary / default /
  danger typed buttons with hover and pointer cursor.

#### Consolidated document — elegance and navigation
- **Hierarchical numbering**: `# 1. Title`, `## 1.1 Section`, `### 1.1.1
  Sub-section`. Existing LLM numbering (`1. `, `1.2 `, `1.2.3 - `, `1)
  `) is stripped before rewriting. ``` ``` ``` blocks are preserved.
- **Automatic full TOC** (chapters + `##` + `###`) with clickable GFM
  anchors and hierarchical indentation.
- **Elegant admonitions**: `[!NOTE]` / `[!TIP]` / `[!IMPORTANT]` replaced
  by blockquote + emoji (📝 Note, 💡 Example, 📖 Definition, 🎯
  Exercise).

#### Glossary — acronym-expansion column
- **Markdown table format**: `| Term | Acronym | Meaning | Definition |`
  (EN) / `| Terme | Acronyme | Signification | Définition |` (FR).
- **`Meaning` column**: literal expansion of the acronym in its source
  language (e.g. *ROI* → *Return On Investment*, *PIB* → *Produit
  Intérieur Brut*). **Never translated**: an FR glossary will contain
  `Return On Investment` for ROI, and an EN glossary will contain
  `Produit Intérieur Brut` for PIB.
- New `acronym_expansion` field on the `Term` domain, persisted in
  SQLite via soft `ALTER TABLE` migration.

#### Cost estimation — thinking awareness
- **"💵 Estimate cost"** button in the header bar. On click: input
  folder scan, ffprobe probe of each video, detailed popup (videos,
  total duration, STT cost, LLM cost, total, cap with margin or
  overshoot coloured).
- **`CostEstimator` revisited**: accepts `phases_config` and applies an
  empirical multiplier on the `completion_tokens` according to the
  `reasoning_effort`:
  - thinking off → ×1.0
  - thinking on (no effort) → ×2.5
  - thinking on, **HIGH** → ×3.5
  - thinking on, **MAX** → ×6.0
- Calibration validated on a real case: 2 videos × 19 min 27 s in HIGH on
  all phases → estimation $0.0304 vs observed real cost ~$0.03.

#### Prompt editing from the UI
- **Edit → Edit prompts… menu** opens `PromptsEditorDialog` (sidebar
  splitter + monospace editor).
- List of the 8 LLM templates (phases 1–7 + 5a sub-prompt) with an
  asterisk ` *` if an override is active.
- **Save** (mandatory Jinja2 validation — refusal if syntax is invalid)
  and **Reset to default** (override removal with confirmation) buttons.
- Protection against loss of changes: confirmation on phase change if
  changes are unsaved.
- New `PromptsService` service (app/) acting as a stable API for the
  dialog.

### Changed

- **`SqliteState.upsert_phase_execution`**: explicitly handles the
  `video_id IS NULL` case (batch phases) via `DELETE + INSERT`. SQLite
  treats `NULL` as distinct in a `UNIQUE` constraint, so the `ON
  CONFLICT(run_id, phase_id, video_id)` never triggered for batch phases
  — duplicates accumulated and the matrix could show RUNNING even after
  SUCCEEDED. Cleansing soft migration of existing duplicates at startup.
- **`RunController._refresh_views_with_last_run`**: reset of the views
  (empty snapshots) if the selected project has no Run yet, to avoid
  displaying the state of a Run belonging to another project.
- **`ProjectsSidebar.contextMenuEvent`**: uses
  `viewport().mapFromGlobal(event.globalPos())` to stay insensitive to
  QSS padding on `QListWidget` (cause: the Edit / Delete context menu
  no longer showed up after the theme was applied).
- **`StatsSnapshot`**: addition of `started_at`, `finished_at`,
  `elapsed_seconds` fields (driver of the live Duration card).

### Fixed

- Project-deletion confirmation never valid (was using `is` instead of
  `==` to compare a `QMessageBox.StandardButton` return).
- Duplicates accumulated in `phase_executions` for batch phases on
  pre-existing DBs (see soft migration above).
- Cost estimation massively underestimated when thinking mode was on
  (2 to 6 factor gap).

### Metrics

- 445+ passing tests (+40 vs 0.1.0).
- `mypy --strict` and `ruff` clean on 186+ source files.

## [0.1.0] — 2026-05-19

First version (alpha). Full functional pipeline, dense cockpit UI,
working portable Windows packaging.

### Added

#### Technical base
- Typed exception hierarchy (`Fahmi2Error` + 9 specialisations) with
  stable codes and a localised FR message registry.
- Bounded exponential `RetryPolicy` with jitter and `with_retry` runner.
- Structured JSONL logging + Qt sink + automatic global redaction of
  recorded secrets.
- Generic forward-only `MigrationRunner` + baseline v0→v1 migration.

#### Domain
- Immutable entities (`Project`, `Run`, `VideoExecution`,
  `PhaseExecution`, `Term`, `Glossary`) + exhaustive `ProjectSettings`
  with cross-field validations.
- Typed ULID identifiers (`ProjectId`, `RunId`, `VideoId` via shared
  `_UlidIdBase` base).
- Run and Phase state machines with transition validation.

#### Infra
- WAL-mode `SqliteState` with 1 connection per thread, `busy_timeout`,
  `SQLITE_BUSY` retry, 4-thread × 100-write concurrency test.
- `FsArtifactStore` with atomic writes (`.tmp` then `rename`).
- Windows `DPAPISecretsStore` (user-DPAPI encryption).
- `FFmpegExtractor` (subprocess with ffprobe pre-check on the audio
  track).
- 2 STT providers: `FasterWhisperAdapter` (CUDA required) +
  `OpenAIWhisperAdapter` (verbose JSON, error mapping).
- `DeepSeekAdapter` (OpenAI-compatible SDK, `thinking` mode via
  `extra_body`).
- `TfidfGlossaryRetriever` (scikit-learn cosine similarity).
- `PromptLoader` with `%APPDATA%/Fahmi2/prompts/` user-override layer +
  8 default Jinja2 templates bundled.
- DeepSeek v4 pricing constants (Flash + Pro) centralised in
  `_pricing.py`.

#### Pipeline
- `PipelineEngine` with per-phase SQLite checkpoint, retry policy, typed
  events, cooperative pause/cancel via `PauseToken`.
- Thread-safe `EventBus` + 6 event types (`RunStarted`, `PhaseStarted`,
  `PhaseProgress`, `PhaseFinished`, `RetryAttempt`, `RunFinished`).
- 8 phase handlers:
  - Phase 0 STT (audio extraction + transcription)
  - Phase 1 glossary-term extraction
  - Phase 2 glossary reconciliation (batch)
  - Phase 3 rephrasing (with top-K glossary injection)
  - Phase 4 Markdown structuring (semantic admonitions)
  - Phase 5 consolidation (intermediate summaries + meta elements,
    chapter content copied as-is)
  - Phase 6 translation (copies for source language, LLM for the others)
  - Phase 7 per-language final coherence

#### App services
- `ProjectService` CRUD projects.
- `RunOrchestrator` Run lifecycle (automatic video scan, pipeline
  execution, persistence, pause/cancel/resume).
- `CostEstimator` pre-run STT + LLM heuristic per phase and language.
- `GlossaryReconciler` (import payload, load, render Markdown).
- `SecretsService` wrapper with auto log redaction.
- `HardwareProbe` (CUDA/GPU detection).
- `VideoScanner` (extensions `.mp4 .m4v .mkv .mov .webm`).

#### PySide6 UI
- Dense cockpit `MainWindow` (projects sidebar + header bar + stats
  strip + videos × phases matrix + logs dock).
- `RunMatrixViewModel` and `StatsStripViewModel` testable without Qt.
- `QtEventBus` EventBus → Qt Signal adapter.
- `NewProjectDialog` 1-page wizard with local STT lock without a GPU.
- `GlobalSettingsDialog` (API keys + theme).
- Entry point `app_main.py` with full DI.

#### Packaging
- PyInstaller spec `--onedir` with strict validation of ffmpeg
  presence.
- `packaging/fetch-ffmpeg.ps1` automatically downloads portable ffmpeg
  (official essentials build) with SHA256 verification.
- `packaging/build.ps1` full orchestration (fetch → clean → build).
- `packaging/make-portable-zip.ps1` distribution archive generation.
- Runtime resolution of the bundled ffmpeg path (`sys.frozen` +
  `_MEIPASS`).

#### Documentation
- Complete design spec:
  `docs/superpowers/specs/2026-05-19-fahmi2-design.md`.
- 12 implementation plans tagged `milestone-01` to `milestone-12`.
- User documentation suite: functional presentation, technical
  presentation, README, installation, parameters, operations, technical
  procedures, end-user guide.

### Metrics

- 405+ passing tests.
- Overall coverage ≥ 87 %.
- `mypy --strict` and `ruff` clean on 177+ source files.

### Known limitations

- 2 languages only (FR/EN).
- Markdown-only output format.
- 1 LLM provider (DeepSeek).
- No auto-update.
- No code signing (SmartScreen warning at first launch).
- Multi-user not supported.
