# Fahmi2

> Turn your inputs — **videos, audio files, YouTube links, or text documents**
> (PDF, Word, Markdown, txt) — into a **consolidated, structured document**
> (rephrased, chaptered, with a **glossary**, **multilingual**: French, English,
> German, Spanish, Italian, Chinese, Arabic), assembled either **in source
> order** or via a **cross-cutting thematic rewrite**. The consolidated document
> and the glossary **export** to **Markdown / PDF / HTML / Word (`.docx`)** —
> **Chinese** and **Arabic** (right-to-left) render correctly. Then make use of
> this corpus effortlessly: **revision aids** (flashcards, MCQs, summary sheets,
> mock exam…, **Anki / Markdown / PDF / HTML / Word** exports), **Dialogue**
> (chat anchored on the course, **cited** answers **streamed** live), and
> **Visualizations** (two self-contained interactive HTML pages — an interactive
> **knowledge map** and a **generated-diagram gallery**). All in **a few
> minutes** with **no manual intervention**.

Windows desktop application, single-user, **double-click install** (no system
dependency to install — **ffmpeg and yt-dlp are bundled**). The interface is
organised around **feature tabs** — **Generation** · **Revision materials** ·
**Dialogue** · **Visualizations**. Generation relies on an 8-phase pipeline (polymorphic ingestion —
Whisper transcription or text extraction — followed by 7 DeepSeek v4 LLM
phases), fully configurable from the graphical interface.

The user interface is **fully internationalised** (French / English) via the
native Qt translation stack (`QTranslator` + `.qm` files compiled from `.ts`
sources). The language is selected from **Edit → Global settings → Language**
and takes effect at the next launch.

## Capabilities

- **Polymorphic inputs**: videos (MP4, MKV, MOV, WebM…), audio files (WAV, MP3,
  M4A, FLAC, OGG…), **YouTube links** (single videos; audio is downloaded by
  yt-dlp) and **text documents** (PDF, Word, Markdown, txt — either rephrased
  like a spoken transcript or inserted as-is). Mixed sources are accepted in
  the same project.
- **Source ordering & exclusion**: the processing order (hence the chapter
  order of the final document) is configurable via drag and drop; any source
  can be excluded and re-included.
- **Consolidation mode**: **ordered** (1 source = 1 chapter, content copied
  in the chosen order) or **thematic rewrite** — the LLM aggregates and
  restructures the contents of all inputs cross-cuttingly by theme, like an
  investigative-style synthesis (factual rigour: no invented facts, conflicts
  between sources surfaced; formal flexibility: fusion, deduplication,
  transitions).
- 7 output languages: **French**, **English**, **German**, **Spanish**,
  **Italian**, **Chinese**, **Arabic** (STT, glossary, materials, and Dialogue
  included). Note: for Chinese, the Dialogue prefers **semantic** retrieval
  (lexical search is poorly suited to whitespace-less languages).
- 2 STT providers (**model configurable per provider**): **faster-whisper**
  local (NVIDIA GPU; `large-v3-turbo` by default, or
  `large-v3`/`medium`/`small`, downloaded on demand) or **OpenAI** cloud
  (`whisper-1` by default, or `gpt-4o-transcribe`/`gpt-4o-mini-transcribe`) —
  the latter handles **any course length** (automatic Opus compression +
  silence-based chunking to clear OpenAI's 25 MB limit, transparently).
- 2 LLM models: **DeepSeek v4 Flash** (economical) or **Pro** (higher
  capacity). Reasoning mode (`thinking` + `reasoning_effort` HIGH/MAX) and
  temperature are configurable **per phase**.
- **Dialogue (chat anchored on the corpus)**: ask questions in natural language
  about a generated course. **Cited** answers (chapter › section, clickable)
  and **streamed** live, in **strict** mode (corpus only, refuses out-of-corpus
  topics) or **augmented** mode. **Lexical** retrieval (TF-IDF, offline) or
  **semantic** retrieval (OpenAI embeddings, **model configurable**), with an
  **AUTO** strategy + query expansion. **Language per conversation**
  (chosen from the produced ones): the chat reads, **cites**, and **answers**
  in that language, with the cited glossary fully localised. Multiple
  conversations **persisted and deletable**; **exhaustive cumulative cost**
  (answer + embeddings + rephrasing).
- **Visualizations (standalone interactive HTML)**: two **fully self-contained**
  pages produced from a generated course — an interactive **knowledge map**
  (a typed graph of concepts, glossary terms, ideas and examples with their
  relations; reorganises from **network to tree on click**, with embedded
  source excerpts) and a **gallery of generated diagrams** (flowcharts,
  timelines, comparisons, hierarchies, cycles, decision trees). Rendered with
  **vendored Cytoscape.js** inlined offline — **no CDN, works without a network
  connection**. Produced for each generated **Latin-script** language
  (French, English, German, Spanish, Italian); Chinese and Arabic are not
  supported for this feature. Density slider, selectable diagram types, and a
  **pre-run cost estimate** + budget cap.
- 4 rendering styles: casual / standard / professional / academic + free
  directives.
- **Navigable consolidated document**: hierarchically numbered headings (1,
  1.1, 1.1.1), automatic table of contents with clickable anchors, elegant
  admonitions (blockquote + emoji).
- **Glossary as a table** — 4 columns Term / Acronym / Meaning / Definition,
  with the acronym expansion kept in its original language (ROI = *Return On
  Investment* even in a French glossary). **Terms** are **localised per
  target language** (a `glossary.{lang}.md` per language).
- **Document exports** (opt-in): the **consolidated document** and the
  **glossary** export to **Markdown / PDF / HTML / Word (`.docx`)**, one file
  per language; **materials** additionally export to **Anki `.apkg`**. The PDF
  renderer handles **Chinese** (Microsoft YaHei system font, automatic line
  breaks) and **Arabic** (right-to-left + contextual shaping, including in
  Word); the **glossary** exports in **landscape** orientation (PDF and Word).
- **Pre-run cost estimate** that takes phase-level thinking into account
  + **budget cap** with clean stop.
- **Prompt editing** from the UI (Edit → Edit prompts…) with Jinja2 validation
  and reset-to-default.
- **Fine-grained per-phase checkpointing**: no work lost on pause,
  cancellation, or crash.
- **Parallel processing**: sources (per-source phases) and revision materials
  are processed concurrently, with a configurable worker count, to cut the
  wall-clock on large batches.
- **Persistent Project** concept with run history and resume.
- **Encrypted storage** of API keys (Windows DPAPI).
- **Internationalised UI** (FR / EN) with `LanguageController` mirroring the
  theme controller; preferences persisted in `%APPDATA%/Fahmi2/ui_prefs.json`.

## Documentation

| Document | For whom? |
|----------|-----------|
| [Functional overview](docs/01-presentation-fonctionnelle.md) | Decision-maker / user who wants to understand the value |
| [Technical overview](docs/02-presentation-technique.md) | Architect / developer who wants to understand the implementation |
| [Installation](docs/03-installation.md) | End user + developer |
| [Configuration](docs/04-parametrage.md) | End user (full configuration) |
| [Operations](docs/05-exploitation.md) | Daily user (monitoring, incidents, deliverables) |
| [Technical procedures](docs/06-procedures-techniques.md) | Developer / maintainer |
| [User guide](docs/07-guide-utilisateur.md) | Non-technical end user (quick start) |
| [CHANGELOG](CHANGELOG.md) | Version history |
| [v1 design spec](docs/superpowers/specs/2026-05-19-fahmi2-design.md) | Detailed architecture (French — archive) |
| [Implementation plans](docs/superpowers/plans/) | Detailed implementation milestones (French — archive) |
| [Packaging](packaging/README.md) | Build and distribution |

> The design spec and implementation plans under `docs/superpowers/` remain in
> French — they are session-level planning archives, kept verbatim for
> auditability.

## Quick start (end user)

1. Download `Fahmi2-X.Y.Z-win64.zip`.
2. Unzip wherever you like (e.g. `C:\Apps\Fahmi2\`).
3. Double-click `Fahmi2.exe`.
4. On first launch, click *"More info"* → *"Run anyway"* when SmartScreen
   asks.
5. **Edit → Global settings**: enter your API keys (DeepSeek mandatory,
   OpenAI optional).
6. **File → New project**: give the project a name and pick its location,
   confirm.
7. **Generation tab → ⚙ Settings**: pick the input folder (videos, audio,
   and/or documents) and/or paste YouTube links, order or exclude the
   sources, then set the languages, style, and model; confirm.
8. (Optional) Click **💵 Estimate cost** to see the budget before launching.
9. Click **▶ Run**. Pick up the Markdown deliverables at the end via the
   **📂 Output folder** button (or in
   `<location>/generation/output/`). To obtain the consolidated document
   and the glossary in **PDF / HTML / Word**, first tick the formats under
   **⚙ Settings → Export**, then use the **📦 Export** button.

See [docs/07-guide-utilisateur.md](docs/07-guide-utilisateur.md) for the
detailed walkthrough.

## Quick start (developer)

```powershell
# Clone and set up
git clone <url> Fahmi2
cd Fahmi2
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pip install pyinstaller>=6.10
pre-commit install

# Compile UI translations (.ts → .qm) before launching the app
.\.venv\Scripts\python.exe scripts\i18n_compile.py

# Verify
pytest
ruff check .
mypy src tests

# Run in dev mode
python -m fahmi2.ui.app_main

# Build the portable .zip
.\packaging\build.ps1
.\packaging\make-portable-zip.ps1
```

See [docs/06-procedures-techniques.md](docs/06-procedures-techniques.md) for
the details.

## Architecture

Layered architecture inspired by hexagonal principles:

```
src/fahmi2/
├── core/         logging, errors, retry, config, migrations, retrieval, ids
├── domain/       pure entities (Project, Run, PhaseExecution, Glossary, …)
├── pipeline/     PipelineEngine + 8 phase handlers
├── infra/        adapters (STT, LLM, ffmpeg, SQLite WAL, DPAPI, prompts)
├── app/          use cases (ProjectService, RunOrchestrator, CostEstimator…)
├── i18n/         Qt translation stack (AppLanguage enum, install_translator,
│                 .ts sources + .qm compiled files)
└── ui/           PySide6 (tabbed MainWindow, features/, widgets, dialogs)
```

See [docs/02-presentation-technique.md](docs/02-presentation-technique.md) for
the full breakdown.

## Status

**v1.5.1** — **Quality round on cost tracking and reliability**:
phase 6 translation hardened against unescaped quotes from DeepSeek
(JSON mode strict at the provider level) + per-source cost attribution
for batch phases 5 and 6 in the Generation matrix (cross-cutting
refactor with new `PhaseExecution.per_source_costs` field, SQLite
soft migration, end-to-end propagation handler → engine → viewmodel) +
cumulative cost preserved across resumes on both Generation
(`SUCCEEDED` state preserved by the engine) and Pedagogy (cost
accumulator rebased on the historical total). Two DeepSeek-documented
failure modes hardened with typed retryable errors
(`LLM.EMPTY_CONTENT`, `LLM.UNEXPECTED_JSON_SHAPE`). Enriched diagnostic
logs on JSON parse failures.

**v1.5.0** — **UI/UX redesign** (Light Fluent design system + mirrored
**dark mode** + cards with soft shadows on the 6 settings screens +
plain-language glossary labels + redesigned project sidebar with status
pill / name / subtitle + aligned chat bubbles with citation chips) **and
native Qt internationalisation** (UI fully localised in **French** and
**English**, picked from Edit → Global settings → Language, persisted
in `ui_prefs.json`, applied at next launch). All user-facing
documentation translated to English.

**v1.4.3** — Dialogue: citations are shown as **numbered `[1]` clickable
markers** inline in the answer, linked to a **numbered** "Sources" list;
clicking either the marker or a source opens the cited excerpt preview.

**v1.4.2** — Dialogue: each conversation in the list is **prefixed by its
language code** (e.g. "EN · …"), a conversation keeping a fixed language.

**v1.4.1** — **Dialogue: corpus language selectable per conversation** (the
chat reads, **cites**, and **answers** in the chosen language among the
produced ones); **fully localised glossary** downstream (term **and**
definition) in Revision materials and the Dialogue.

**v1.4.0** — **5 additional languages** (German, Spanish, Italian, Chinese,
Arabic → **7 in total**, on input and output, for all 3 features); **Word
(`.docx`) export** for Generation and Revision materials; **Chinese PDF
rendering** (Microsoft YaHei font, automatic line breaks) **and Arabic**
(right-to-left + contextual shaping, including in Word); **terminological
localisation of the glossary** per target language (phase 6); **table
rendering normalisation** (Markdown/PDF/HTML/DOCX).

**v1.3.0** — **"thematic rewrite" consolidation mode** (the LLM aggregates
and restructures the contents cross-cuttingly by theme, alongside the
default ordered mode; factual rigour / formal flexibility); the **Dialogue
automatically reloads** its corpus after regeneration (no more stale
citations); **deleting a project** also wipes its workspace folder on disk.
v1.2.0: new **Dialogue** tab (chat anchored on the corpus: cited and
streamed answers, lexical/semantic retrieval, exhaustive cost, persisted
and deletable conversations); **configurable models** (LLM, embeddings,
STT); output cap raised to the model's maximum (anti-truncation) on **all**
DeepSeek calls. v1.1.0: broader inputs (**videos, audio, YouTube, text
documents**) with source ordering/exclusion. v1.0.0 baseline: full pipeline,
Light Fluent themed cockpit UI, portable Windows packaging, navigable
consolidated document, glossary table, prompt editing, usage-aligned cost
estimation. See [CHANGELOG.md](CHANGELOG.md).

The interface is organised as **feature tabs** (Generation + Revision
materials: 8 types of revision aids generated from the consolidated document
and the glossary + **Dialogue**: conversational chat anchored on the corpus,
cited and streamed answers, lexical or semantic retrieval); a project's
identity is reduced to name + location, with settings split per feature.

Revision materials export to **Anki `.apkg`** (flashcards / cloze / MCQs,
re-import without duplicates), **Markdown**, **PDF**, **HTML**, and **Word
(`.docx`)** (self-contained documents, question / answer key separated).
PDF rendering handles **Chinese** (system Microsoft YaHei font, automatic
line breaks) and **Arabic** (right-to-left + contextual shaping); the
**glossary** exports in landscape (PDF and Word).

**Internationalisation**: the UI is fully translated to English via the
native Qt stack (485 strings, ≥ 28 Linguist contexts). The migration is
covered by ~60 parametric end-to-end tests verifying that the bundled `.qm`
contains the expected translation for each migrated context — a rename in
the source without re-extraction fails the suite rather than silently
falling back to French at runtime.

1188 tests passing × 3 runs, `mypy --strict` and `ruff` clean on 405 source
files.

## Licence

Proprietary.
