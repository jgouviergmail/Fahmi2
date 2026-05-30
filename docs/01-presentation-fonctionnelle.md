# Fahmi2 — Functional overview

## 1. Context and problem addressed

A lecturer in economics and finance produces a substantial body of **MP4
video lectures** (in French or English). The knowledge is high-quality but
remains **trapped** in the video format: it is neither searchable, nor
reusable to produce written materials, nor formalised.

Fahmi2 solves this problem by turning these videos into **structured
Markdown documents** that can serve as a written reference, a
distributable handout, or input for other formatting tools (DOCX, PDF…).

## 2. Product vision

A **local desktop application** that:

- accepts as input a **folder of heterogeneous sources** — **videos** (MP4,
  MKV, MOV, WebM…), **audio files** (WAV, MP3, M4A, FLAC…), **text
  documents** (PDF, Word, Markdown, txt) — and/or **YouTube links** (single
  videos), with **control over the processing order** and the ability to
  **exclude** specific sources;
- produces as output **one consolidated document** per requested output
  language, accompanied by **per-source documents** and a **glossary**;
- guarantees **fidelity to the spoken content** (no hallucination, pure
  rephrasing) while respecting the **written-language norms** of the target
  language;
- installs **with a double-click** and is driven **entirely through the
  graphical interface** (no file editing required);
- is **fully internationalised** (French / English UI) via the native Qt
  translation stack — the language is chosen from **Edit → Global
  settings → Language** and takes effect at the next launch.

## 3. Target user profile

- **Lecturer** or **trainer** in a field where terminological precision
  matters (economics, finance, science, engineering).
- No technical expertise required: basic Windows knowledge, ability to
  paste an API key into a form.
- Works on their **personal machine** (single user), with or without an
  NVIDIA GPU.

## 4. Main functions

### 4.1 Project management

A **Project** in Fahmi2 = a **minimal identity** (name + location) with
attached **per-feature settings** + a run history.
The application is organised around **feature tabs**: **Generation** (videos
→ documents), **Revision materials** (consolidated document + glossary
→ flashcards, MCQs, summary sheets, mock exam…) and **Dialogue**
(conversational chat anchored on the corpus: natural-language questions,
**cited** answers **streamed** live, configurable strict/augmented
fidelity, lexical or semantic retrieval, persisted conversations) and
**Visualizations** (two **fully self-contained** interactive HTML pages —
a **knowledge map** and a **diagram gallery** — for **Latin-script
languages** only). The
Revision materials tab exposes **settings** (⚙: materials, difficulty,
languages, model & cost), a **Generate** button + **Estimate cost**, a
**progress table** (material × language) and a **status banner** ("generation
required" / "ready" / "up to date" / "stale"). Materials are written to
`<location>/pedagogy/`. An **Export** button offers 5 formats: **Anki
`.apkg`** (flashcards, cloze, MCQs; re-import without duplicates),
**Markdown**, **PDF**, **HTML** and **Word (`.docx`)** — these last four
produce **one file per material and per answer key**
(`<material>.<lang>.<ext>` / `<material>.<lang>.corrige.<ext>`), each
self-contained.

- Project creation through a **minimal dialog** (name + location); the
  generation settings are then configured from the **Generation → ⚙
  Settings** tab;
- Full **history** of runs visible in the sidebar;
- Ability to **reopen** an older project, see its report, or re-run it.

### 4.2 Processing pipeline

For each project, the **8-phase pipeline** turns sources into documents:

| Phase | Description |
|-------|-------------|
| 0. STT | Audio → text transcription (local or cloud Whisper; text documents are extracted without STT) |
| 1. Terms | Per-source extraction of candidate technical terms |
| 2. Glossary | Cross-source reconciliation producing a master glossary |
| 3. Rephrasing | Faithful written rephrasing, per source, in the source language |
| 4. Structuring | Markdown formatting with headings, intro, conclusion, semantic admonitions (notes, examples, definitions, exercises) |
| 5. Consolidation | Assembly of the consolidated document according to the **chosen mode** (cf. §4.3): **ordered** (1 source = 1 chapter, content copied) or **thematic rewrite** (the LLM aggregates/restructures cross-cuttingly by theme) |
| 6. Translation | Production of artefacts in every requested output language |
| 7. Coherence | Final review pass on the meta elements |

### 4.3 Configuration

The user configures **through the interface** (and **only** through the
interface):

- **API keys**: OpenAI (for cloud Whisper), DeepSeek (for the LLM phases).
- **STT provider**: local Whisper (NVIDIA GPU required) or OpenAI cloud
  (handles long videos via automatic Opus compression + chunking,
  transparent).
- **LLM model**: DeepSeek v4 Flash or Pro.
- **Reasoning mode** (`thinking` on / off), **reasoning effort**
  (`HIGH` / `MAX`) and **temperature**, configurable
  **per LLM phase** independently.
- **Document languages** (French, English, German, Spanish, Italian,
  Chinese, Arabic): produced languages + **primary language** (the original,
  drafted directly; the others are translated from it).
- **Rendering style**: casual / standard / professional / academic.
- **Consolidation mode**: **ordered** (1 source = 1 chapter, content copied
  in the chosen order) or **thematic rewrite** (the LLM aggregates and
  restructures cross-cuttingly the contents of all sources by theme —
  investigative-style synthesis, factual rigour / formal flexibility; in
  this mode source order has no effect).
- **Free-text style directives**.
- **Optional budget cap** with clean automatic stop.
- **User override of prompts** through the built-in editor
  (menu **Edit → Edit prompts…**): every template of the 7 LLM phases
  (including the **3 thematic-mode prompts**), the **8 revision materials**,
  and the **3 Dialogue prompts** can be customised without touching the
  code, with Jinja2 validation and one-click reset-to-default.
- **Interface language**: French (source) or English, chosen under
  **Edit → Global settings → Language** (applies at the next launch).

### 4.4 Driving a run

- Start, **pause**, **resume**, **cancel** a run via the header bar
  buttons.
- **Fine-grained per-phase resume** after pause, cancellation, or crash: no
  work lost, the pipeline picks up exactly where it stopped.
- **Pre-run cost estimate**: **💵 Estimate cost** button in the header
  bar. The calculation accounts for the model, the number of target
  languages, and the **empirical surcharge of thinking mode per phase**
  according to the chosen reasoning level.
- **Cumulative cost** and **live duration** displayed in real time during
  the Run.
- **Open output folder** in one click from the header bar at the end of
  the Run.
- **Export** generation deliverables (the **consolidated document** and
  **glossary**, one file per language) to **Markdown**, **PDF**, **HTML**
  or **Word (`.docx`)** to a chosen folder. The offered formats are ticked
  under **⚙ Settings → Export** (none by default — opt-in).
- **Parallel processing**: per-source phases (cloud transcription, term
  extraction, rephrasing, structuring) process several sources in parallel,
  and the final phases parallelise translation and coherence; the number of
  concurrent calls is configurable. **Local** transcription stays sequential
  (a single GPU).

### 4.5 Progress display

The main interface (dense cockpit, **Light Fluent** theme — with a
mirror **Dark** mode) displays in real time:

- **A 2D matrix**: one row per source, one column per phase. Each cell
  shows the status (pending, running, succeeded, failed, skipped) with a
  symbol **and a colour** (green for success, blue for running, grey for
  pending, red for failed, indigo for skipped). On hover: details
  (timestamps, cost, retries, possible error). Short, readable headers
  (STT, Terms, Glossary, Rephras., Structur., Consolid., Translation,
  Coherence).
- **Six indicator cards**: Status, Sources, Phases, Languages,
  **Duration**, Cost. Each card = icon + title + large value + sub-info.
  The Duration card is refreshed every second while the Run is running.
- **A log panel** filterable by severity, with colouring (INFO grey, WARN
  amber, ERROR red, FATAL bold red), compact `HH:MM:SS` timestamp and
  monospace font.

### 4.6 Deliverables produced

After a run, the `output/` folder contains, for each language:

- `consolidated.{lang}.md` — navigable consolidated document:
  - Global title, **executive summary** (synthetic abstract), then a
    general introduction.
  - Full **automatic table of contents** with clickable GFM anchors to
    every section.
  - Chapters and sections **hierarchically numbered** (1, 1.1, 1.1.1).
  - Source contents copied as-is (no rewriting by the LLM).
  - **Elegant admonitions**: 📝 Note, 💡 Example, 📖 Definition, 🎯
    Exercise (Markdown blockquotes with an emoji, more readable than the
    raw GFM `[!NOTE]` syntax). Emojis are displayed in Markdown, HTML, and
    Word; they are **omitted on PDF export** (the rendering engine cannot
    draw colour emojis — the admonition text remains intact).
  - General conclusion.
- `glossary.{lang}.md` — glossary as a **4-column Markdown table**
  sorted alphabetically:
  - **Term** (long form), **Acronym** (`PIB`, `ROI`, `IFRS`…),
    **Meaning** (literal expansion of the acronym in its original
    language — *Return On Investment* for ROI, even in a French
    glossary), **Definition** (contextual).
- `per-video/{lang}/<source_id>.md` — a self-contained Markdown document
  per source, with its own title, intro, conclusion, and semantic
  admonitions.

All files are **UTF-8 Markdown**, openable in any editor, in VS Code or
Obsidian. The **built-in export** additionally produces, on demand, **PDF**,
**HTML**, and **Word (`.docx`)** versions (cf. § 4.4).

### 4.7 Dialogue (chat anchored on the corpus)

A third tab, **Dialogue**, lets you **query the course** in natural
language once the generation has been produced. Answers are **anchored** on
the consolidated document and the glossary, **cited** (chapter › section,
clickable) and **streamed** live.

- **Configurable fidelity**: *strict* (answer only from the course, polite
  refusal off-corpus) or *augmented* (general-knowledge supplement,
  clearly flagged).
- **Passage search**: lexical (offline) or semantic (OpenAI embeddings,
  **configurable model**), with an **automatic** mode and on-demand query
  rephrasing.
- **Language per conversation**: if the generation has produced several
  languages, a selector fixes the language of a new conversation — the
  Dialogue **reads, cites, and answers** in that language, with the cited
  glossary fully localised (term + definition).
- **Multiple conversations** persisted per project, **deletable**;
  **per-message and cumulative cost** are **exhaustive** (answer +
  embeddings + rephrasing).
- Settings (fidelity, retrieval, LLM/embedding models) and **editable
  prompts** like the rest.

### 4.8 Visualizations (standalone interactive HTML)

A fourth tab, **Visualizations**, turns a generated course into two
**fully self-contained** interactive HTML pages (no internet connection, no
external dependency — everything is inlined). Like the Revision materials,
it is **on-demand** and configurable.

- **Knowledge map**: an interactive graph of the course's **concepts**,
  **glossary terms**, **ideas** and **examples**, with their **typed
  relations** (leads to, prerequisite, illustrates, contrasts with, part of,
  related). The graph reorganises from a **network** view to a **tree** when
  you click a node (and back), groups nodes into **themes**, and shows, for
  each node, its definition and an **excerpt of the source** it comes from.
- **Diagram gallery**: **generated** diagrams (not AI images) — flowcharts,
  timelines, comparisons, hierarchies, cycles, decision trees — chosen by the
  AI to fit each part of the course. Each diagram card has an **« Enlarge »
  (fullscreen)** button that opens the diagram in a full-window overlay (fit to
  the viewport, wheel-zoom + drag-pan) so even a dense diagram stays legible; the
  graph cards also size their canvas to the number of nodes, and **nodes can be
  dragged** to rearrange the layout (with a *Reset layout* button).
- **Latin-script languages only**: a page is produced for each generated
  language among **French, English, German, Spanish, Italian**. Chinese and
  Arabic are **not** supported for this feature (to keep the interactive
  rendering uncompromised).
- **Settings**: which deliverables to produce, content **density** (now noticeably
  drives the **knowledge-map size** — *light* keeps only the strong, structuring
  concepts; *dense* shows the full connected graph), allowed
  **diagram types**, model / reasoning, **budget cap** and parallelism.
  A **pre-run cost estimate** is available, and the **prompts are editable**
  like the rest.

## 5. Quality promises

### 5.1 Fidelity to the spoken content

- In the **ordered** consolidation mode (default), the pipeline **never
  rewrites** the detailed content: chapters are the structured outputs of
  individual sources, copied as-is (1 source = 1 chapter).
- In **thematic rewrite** mode, the LLM **reorganises and rephrases** the
  contents by theme, but under a strict **factual-rigour** rule: ban on
  inventing or adding facts, preservation of figures/data/reasoning
  (guaranteed by a traced factual ledger + double coverage check), and
  **conflicts between sources surfaced** to the reader without arbitration.
  The flexibility only touches the **form** (fusion, deduplication,
  transitions, structure).
- In both modes, the LLM is explicitly instructed **not to invent** content
  absent from the sources.

### 5.2 Terminological consistency

- A **master glossary** is built in two passes (extraction then
  reconciliation) from terms extracted independently from each source.
- The relevant terms are re-injected into the LLM context during
  rephrasing, structuring, and translation to guarantee consistent
  spelling and meaning across the whole batch.
- **Per-language term localisation**: for each produced language, the
  glossary terms are translated to their **established domain equivalent**
  ("Bilan" → "Balance sheet", "Bilanz"…), **except** international terms,
  proper nouns, brands, or standards (IFRS, WACC, ROI, Big Four…), which
  are kept as-is — the decision is made term by term. The **same localised
  term** is used in the glossary, the consolidated document, the revision
  materials, and the Dialogue.
- The **acronym expansion** (`acronym_expansion` field) is kept in its
  original language and is never translated: a French glossary exposes
  `ROI = Return On Investment`, an English glossary exposes
  `PIB = Produit Intérieur Brut`. The translation prompt is explicitly
  instructed to preserve the contents of the *Meaning* column of a glossary
  table.

### 5.3 Robustness

- **Fine-grained checkpointing**: each phase produces a persistent
  artefact; resuming after interruption is instantaneous.
- **Retry policy** with exponential backoff on transient errors (rate
  limit, server error, network).
- **Structured JSONL logs**: usable post-mortem in case of incident.
- **Encrypted storage** of API keys (Windows DPAPI).

### 5.4 Controlled cost

- **Pre-run estimate** accessible at any time from the header bar, which
  accounts for:
  - The LLM model (Flash vs Pro).
  - The STT provider (free locally, ~0.006 $/min in the cloud).
  - The **phase-by-phase** configuration: thinking mode and reasoning
    level, translated into an empirical multiplier applied to output
    tokens (thinking mode typically generates 2 to 6× more completion
    tokens).
- **Configurable budget cap** with **clean stop** (never a brutal
  interruption in the middle of an in-flight LLM call).
- **Transparent DeepSeek pricing** (input cache hit / cache miss /
  output) in the source code, easy to update.

## 6. v1 scope — assumed limits

### Included

- 7 languages, in both directions: **French, English, German, Spanish,
  Italian, Chinese, Arabic**.
- 2 STT providers (local FasterWhisper + OpenAI cloud).
- 1 LLM provider (**DeepSeek v4**, two models).
- 4 rendering styles.
- Output formats: generation and revision materials exportable to
  **Markdown**, **PDF**, **HTML**, and **Word (`.docx`)**; revision
  materials add **Anki `.apkg`**. PDF rendering handles **Chinese**
  (Microsoft YaHei system font, automatic **line breaks**) and **Arabic**
  (right-to-left + contextual shaping); **Arabic** is also rendered
  **right-to-left in Word** (bidi + table column inversion). The
  **glossary** exports in **landscape** orientation (PDF and Word).
- **Dialogue**: chat anchored on the corpus (citations + streaming),
  lexical (offline) or semantic (OpenAI embeddings; recommended for
  Chinese) retrieval.
- **Visualizations**: two standalone interactive HTML pages (knowledge map +
  generated-diagram gallery), **Latin-script languages only**
  (fr/en/de/es/it).
- **UI internationalisation**: native Qt stack (FR source + EN), language
  selectable from Global settings, persisted in `ui_prefs.json`.
- Platform: **Windows 11** (10 minimum).

### Out of v1

- Multi-user, collaboration, cloud sync.
- Manual editing of transcripts in the UI.
- LLMs other than DeepSeek (architecture is ready but not implemented).
- Auto-update.
- Code signing (the EXE is not signed in v1).

## 7. Typical use cases

### Case A: 3rd-year macroeconomics lecturer

- 30 weekly lecture videos of 25 min each (~12 h of audio).
- Wants to produce a **complete PDF handout** consolidated in French for
  the students, plus an English version for the international programme.
- Configuration: cloud STT (~$4), DeepSeek v4 Flash, academic style, FR +
  EN output.
- Total duration: ~3 h. Cost: ~$10–15 all-in.

### Case B: corporate finance trainer

- 15 seminar videos of 45 min each.
- Wants only the FR version, professional style, with a rich glossary for
  self-learning.
- Configuration: local STT (GPU available, free), DeepSeek v4 Pro, no
  cap.
- Duration: ~1.5 h. Cost: ~$8–12 (LLM only).

## 8. Key benefits

1. **Time saved**: what would take tens of hours of manual transcription
  and rephrasing is done in a few hours, without intervention.
2. **Consistency**: homogeneous terminology across 50 videos, very hard to
  achieve manually.
3. **Reusability**: the Markdown outputs can feed a website, an LMS, a
  knowledge base, printed materials.
4. **Cost control**: automatic estimation and cap, no surprise on the
  bill.
5. **Discretion**: everything stays local, no telemetry; API keys are
  encrypted on disk; content leaves the machine only when the user has
  chosen a cloud provider.
