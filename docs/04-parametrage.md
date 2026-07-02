# Fahmi2 — Configuration guide

This documentation details every parameter available in Fahmi2 and their
implications.

## 1. Global settings (application-wide)

Access: menu **Edit → Global settings**.

### 1.1 API keys

| Key | Purpose | Where to get it |
|-----|---------|-----------------|
| **OpenAI key** | Cloud STT provider (Whisper) **and** embeddings for the Dialogue's semantic retrieval | <https://platform.openai.com/api-keys> |
| **DeepSeek key** | All LLM phases | <https://platform.deepseek.com/api-keys> |

Keys are **encrypted via Windows DPAPI** and stored under
`%APPDATA%\Fahmi2\secrets.dat`. They are never visible in plain text on
disk or in the logs. Only the Windows user who entered them can decrypt
them (the `secrets.dat` file does not work on another machine or under
another account).

### 1.2 Appearance (theme)

- `system` (recommended): follows the current Windows theme.
- `light`: forced light theme.
- `dark`: forced dark theme.

### 1.3 Interface language

- **Français** (source language).
- **English**.

Selected from **Edit → Global settings → Language**. The choice is
persisted in `%APPDATA%\Fahmi2\ui_prefs.json` and **takes effect at the
next launch** (Qt does not propagate `LanguageChange` to strings already
rendered through `tr()` at widget construction time).

### 1.4 UI log level

Floor level shown in the Logs panel. Default `INFO`. Lower events are
silently filtered out of the display (but still written to the
`events.jsonl` file).

## 2. Project settings

The project's **identity** (name + location) is set through **File → New
project** (renaming via *Edit* in the sidebar; the location is immutable
after creation). All the other settings below are **generation settings**,
edited from the **Generation → ⚙ Settings** tab (master-detail view);
they include the **sources folder**.

### 2.1 Identification

| Parameter | Description |
|-----------|-------------|
| **Name** | Free, used as a label in the sidebar. E.g. "3rd-year macroeconomics". |
| **Location** | Project working folder (artefacts + deliverables). Immutable after creation. |

> The **input folder** (sources) is a generation setting: it is chosen
> from the **Generation → ⚙ Settings → Sources** tab. It can contain
> **videos**, **audio files**, and **text documents** (PDF, Word,
> Markdown, txt); you can also add **YouTube links** (one per line). A
> **dual-list** component lets you **order** the sources (the order
> drives the chapter order) and **exclude** some of them; the **"Rephrase
> documents"** checkbox (on by default) inserts text documents as-is when
> unchecked.

### 2.2 Languages

A **single control** "Document languages": a row of **Produced** checkboxes
(generated languages) and a **Primary** dropdown that only offers the
produced languages. **7 languages** are available, on input and output:
**French, English, German, Spanish, Italian, Chinese, Arabic**.

| Element | Description |
|---------|-------------|
| **Produced** | Each ticked language produces a `consolidated.{lang}.md`. At least one language must always be produced. |
| **Primary** | The **original** version, drafted **directly** from the inputs (any input language is unified into it); it is also the language hint given to STT for media, and the **pivot** for translations. Chosen from the produced languages (hence always produced); the other produced languages are **translations** from it. |

> Example: EN + FR inputs, **primary = FR**, **produced = {FR, EN}** → one
> `consolidated.fr.md` (drafted directly, EN passages unified into FR)
> **and** one `consolidated.en.md` (translated from FR).

### 2.3 Style

| Parameter | Description |
|-----------|-------------|
| **Style** | `casual`, `standard`, `professional`, or `academic`. Affects tone, vocabulary, and formality. |
| **Consolidation mode** | `Ordered` (default: 1 source = 1 chapter, content copied in the chosen order) or `Thematic rewrite` (the LLM aggregates and restructures cross-cuttingly the contents of all sources by theme — factual rigour, formal flexibility). In thematic mode, source order has **no effect** (note shown on the "Sources" page) and phase 5 costs noticeably more. Artefacts are kept under `<workspace>/generation/consolidation/` (including `facts.md`, a readable factual ledger). |
| **Style directives** | Free text that will be concatenated to the prompts. E.g. "warm but rigorous lecturer voice, avoid jargon". |

### 2.4 Providers

| Parameter | Description | Indicative cost |
|-----------|-------------|------------------|
| **STT provider** | `faster_whisper_local` (NVIDIA GPU required) or `openai_cloud`. In cloud mode, audio is **compressed to Opus** (and split on silences if > ~2 h) to fit OpenAI Whisper's **25 MB** limit — transparent, any duration, and the upload is much faster. | Local: free / Cloud: ~$0.003–0.006/min |
| **Local model** | faster-whisper model (active in local mode): `large-v3-turbo` (default, balanced), `large-v3` (max precision), `medium` or `small` (faster, lower VRAM). **Downloaded on first use** (cached under `%LOCALAPPDATA%/Fahmi2/models/`) — no weights are packaged. | free |
| **Cloud model** | OpenAI transcription model (active in cloud mode): `whisper-1` (default, fine-grained timestamps), `gpt-4o-transcribe` (higher precision) or `gpt-4o-mini-transcribe` (2× cheaper). The `gpt-4o-*` models do not return segment timestamps (the transcribed content is identical). | whisper-1 / gpt-4o: $0.006/min; gpt-4o-mini: $0.003/min |
| **Vision model (slides)** | OpenAI vision model used by the per-source **slide analysis** option: `gpt-5-mini` (default, best quality/price ratio), `gpt-5-nano` (budget, simple slides) or `gpt-5.4-mini` (higher quality, dense slides). Requires the OpenAI key. | ≈ $0.003 per analysed slide (gpt-5-mini) — one call per detected slide |
| **LLM model** | `deepseek-v4-flash` (fast/economical) or `deepseek-v4-pro` (higher capacity). | Flash: ~$0.14–0.28/Mt / Pro: ~$0.435–0.87/Mt |

The non-relevant model combo (local in cloud mode, or the other way
around) is **greyed out**.

**Automatic block**: if you select `faster_whisper_local` with no
detected CUDA GPU, the application shows a warning and automatically
switches to `openai_cloud`. This is deliberate: CPU-only local
transcription would take tens of hours for a normal batch.

### 2.5 Per-phase configuration

For each LLM phase (phases 1 to 7) you can configure:

| Parameter | Description | Range | Recommendation |
|-----------|-------------|-------|----------------|
| **Thinking enabled** | DeepSeek reasoning mode (sends `{"thinking": {"type": "enabled"}}`). The model produces reasoning tokens before the final answer. | bool | Off by default, on for critical phases (structuring, consolidation, coherence) |
| **Reasoning effort** | Effort level sent to DeepSeek (sends `{"reasoning_effort": "high"}` or `"max"`). Only honoured if Thinking is ticked. | `(server default)` / `HIGH` / `MAX` | `HIGH` for most cases, `MAX` for the hardest phases or when quality is still insufficient |
| **Temperature** | LLM output variability | 0.0 — 2.0 | 0.2–0.4 for structuring; 0.0–0.2 for translation; 0.3–0.6 for rephrasing |
| **Max retries** | Retries on transient errors | 0 — ∞ | 5 by default |

**⚠ Thinking cost impact.** Enabling thinking can multiply a phase's cost
by 2 to 6 depending on the effort level, because reasoning tokens are
billed at the standard `output` rate. The pre-run estimate accounts for
this (see § 2.6 below).

### 2.6 Budget cap and pre-run estimate

| Parameter | Description |
|-----------|-------------|
| **USD cap** | Maximum allowed cost for the run. Set to 0 or unset: no cap. Otherwise, the run cleanly pauses as soon as the cumulative cost approaches the cap. |

The stop is always **clean**: never a brutal interruption in the middle of
an in-flight LLM call. The pause happens at the next safe boundary.

**Pre-run estimate is accessible at any time** from the header bar (the
**💵 Estimate cost** button). The dialog presents a **per-phase
breakdown** and a **total as a ±33 % range** ("indicative estimate"), with
a warning if the upper end of the range may exceed the cap. The
calculation accounts for:

- The total audio duration of detected videos (`ffprobe` probe).
- The STT provider (`faster_whisper_local` = free, `openai_cloud` = chosen
  model's tariff: $0.006/min for `whisper-1`/`gpt-4o-transcribe`,
  $0.003/min for `gpt-4o-mini-transcribe`).
- The LLM model (Flash vs Pro pricing grid).
- The number of output languages + required translations.
- **The per-phase configuration**: `thinking_enabled` and
  `reasoning_effort` are translated into a multiplier applied to estimated
  completion tokens:

| `thinking_enabled` | `reasoning_effort` | Output multiplier |
|---|---|---|
| `false` | (n/a) | ×1.0 |
| `true` | (server default) | ×2.5 |
| `true` | `HIGH` | ×3.5 |
| `true` | `MAX` | ×6.0 |

The residual spread is around ±20 % depending on the video content.

### 2.7 Advanced parameters

| Parameter | Description | Default |
|-----------|-------------|---------|
| **Location (workspace)** | Working folder picked at creation. Generation artefacts live under `<location>/generation/` (deliverables under `<location>/generation/output/`). | chosen at creation |
| **Delete audio after STT** | Deletes the extracted WAVs after transcription | `True` (saves disk) |
| **Slide analysis, per source** (`slides_sources`) | On the source list (Sources page), every **video/YouTube** row carries an « Analyser les slides » checkbox: the slides are detected (fullscreen, half-page or windowed; progressive reveals captured at their final state; re-displayed slides not re-analysed), read by the vision model, and **interleaved timestamped into the transcript** — the whole pipeline then aligns the speech with the matching slide. Requires the OpenAI key (checked before the run, only when at least one ticked source is actually included). | none ticked |
| **Keep slide images** (`delete_frames_after_analysis`) | When ticked, one representative image per detected slide is kept as `frames/<source>/slide_001.jpg`… (viewing / troubleshooting); otherwise every frame is removed after the analysis. | off (frames deleted) |
| **Simultaneous transcriptions** (`stt_cloud_workers`) | Concurrent cloud STT transcriptions (effective; no effect in local STT: single GPU). Range 1–8 (Transcription page). | 3 |
| **Simultaneous LLM calls** (`llm_workers`) | Concurrent pipeline LLM calls (per-source phases + translation/coherence/summaries). Effective; DeepSeek's limit being per-concurrency, a high value stays safe. Range 1–64 (Model & cost page). | 16 |
| **Export formats** (`export_formats`) | Formats offered by the **Export** button of the Generation tab (page **Export**): **Markdown / PDF / HTML / Word (`.docx`)**. On export, the **consolidated document** and the **glossary** are written, one file per language, in the chosen format (`consolidated.{lang}.<ext>`, `glossary.{lang}.<ext>`). PDF handles Chinese (YaHei font, automatic line breaks) and Arabic (RTL); the glossary is laid out in **landscape** (PDF and Word). | none (opt-in) |

## 3. Prompt overrides (advanced)

The default LLM prompts can be customised without touching the source
code. Two ways: the **built-in editor** (recommended) or manually dropping
a `.j2` file.

### 3.1 Through the built-in editor (recommended)

**Edit → Edit prompts…** opens a dedicated dialog:

- **Left sidebar**: list of **every** editable LLM template — the
  **slide-analysis vision prompt** (phase 0), generation phases (1–7,
  including the consolidation sub-prompts, the **thematic rewrite**
  variants and the **glossary localisation**), revision materials, and
  Dialogue. An asterisk ` *` is appended next to a template that has an
  active override.
- **Short description** of each phase and its role in the pipeline.
- **Status banner**: *"📦 Default prompt"* or *"✏️ Custom override
  active"*.
- **Monospace editor** with QSS colouring, resizable.
- **"💾 Save" button**: validates the Jinja2 syntax before writing to
  `%APPDATA%\Fahmi2\prompts\`. Immediate refusal if the template contains
  a syntax error, with the raw Jinja2 error message displayed.
- **"↩ Reset to default" button**: removes the override (after
  confirmation) and restores the bundled template.
- Confirmation on phase change if changes are not saved (prevents
  unintended loss).

Overrides become active **at the next phase launch**.

### 3.2 Through manual drop (alternative)

For scripted workflows you can drop the files directly:

1. The `%APPDATA%\Fahmi2\prompts\` folder is created automatically at
   first launch.
2. Drop a `.j2` (Jinja2) file with the **same name** as the default
   template. Available templates:
   - `phase_1_term_extraction.j2`
   - `phase_2_glossary_reconciliation.j2`
   - `phase_3_reformulation.j2`
   - `phase_4_structuration.j2`
   - `phase_5_consolidation.j2`
   - `phase_5_video_summary.j2` (ordered mode)
   - `phase_5_fact_ledger.j2`, `phase_5_thematic_plan.j2`,
     `phase_5_thematic_chapter.j2` (**thematic rewrite** mode)
   - `phase_6_translation.j2`
   - `phase_6_glossary_localization.j2` (per-language localisation of
     glossary terms)
   - `phase_7_coherence.j2`
   - the 8 `pedagogy_*.j2` templates (revision materials)
   - `chat_strict.j2`, `chat_augmented.j2`, `chat_query_expansion.j2`
     (Dialogue)
3. The prompt will be used automatically on the next run (or the next
   Dialogue answer).

### 3.3 Variables available in each template

| Template | Key variables |
|----------|----------------|
| `phase_1_term_extraction` | `source_language_label`, `style_label`, `style_directives`, `transcription_text` |
| `phase_2_glossary_reconciliation` | `source_language_label`, `style_label`, `style_directives`, `candidates_json` |
| `phase_3_reformulation` | `output_language_label`, `style_label`, `style_directives`, `glossary_terms`, `transcription_text` |
| `phase_4_structuration` | `output_language_label`, `style_label`, `style_directives`, `glossary_terms`, `reformulated_text` |
| `phase_5_video_summary` | `output_language_label`, `structured_markdown` |
| `phase_5_consolidation` | `output_language_label`, `style_label`, `style_directives`, `summaries_json` |
| `phase_5_fact_ledger` | `output_language_label`, `structured_markdown` |
| `phase_5_thematic_plan` | `output_language_label`, `elements_listing` |
| `phase_5_thematic_chapter` | `output_language_label`, `style_label`, `style_directives`, `chapter_title`, `elements_json` |
| `phase_6_translation` | `source_language_label`, `target_language_label`, `style_label`, `style_directives`, `glossary_terms`, `source_markdown` |
| `phase_6_glossary_localization` | `source_language_label`, `target_language_label`, `style_label`, `style_directives`, `terms` (`term`, `definition`) |
| `phase_7_coherence` | `output_language_label`, `style_label`, `style_directives`, `glossary_terms`, `consolidated_markdown` |
| `pedagogy_flashcards_concepts` | `output_language_label`, `audience_label`, `bloom_label`, `density_label`, `pedagogy_directives`, `glossary_terms`, `chapter_title`, `chapter_markdown` |
| `pedagogy_qcm` | *(same as flashcards concepts)* |
| `pedagogy_true_false` | *(same as flashcards concepts)* |
| `pedagogy_cloze` | *(same as flashcards concepts)* |
| `pedagogy_open_questions` | *(same as flashcards concepts)* |
| `pedagogy_revision_sheet` | *(same as flashcards concepts)* |
| `pedagogy_key_points` | *(same as flashcards concepts)* |
| `pedagogy_mock_exam` | `output_language_label`, `audience_label`, `bloom_label`, `density_label`, `pedagogy_directives`, `glossary_terms`, `consolidated_markdown` |
| `chat_strict` | `output_language_label`, `glossary_terms`, `passages` |
| `chat_augmented` | `output_language_label`, `glossary_terms`, `passages` |
| `chat_query_expansion` | `question` |

> The 8 `pedagogy_*` templates (revision materials) **and** the 3 `chat_*`
> templates (Dialogue) are edited from the **same editor** (Edit → Edit
> prompts) as the generation phases.
>
> The prompts deliberately stay in **French** (Fahmi2's source language)
> regardless of the UI language: the prompt design has been tuned for
> French and the LLM-rendered output is requested directly in the target
> language via `output_language_label`. Changing the UI language does
> **not** rewrite the prompts.

### 3.4 Validation and restoration

- The built-in editor refuses to save invalid syntax.
- If a manually-dropped override is invalid, the `PromptLoader`
  automatically falls back to the default template and logs
  `PROMPT.INVALID_OVERRIDE` (visible in the Logs panel).
- **Reset to default**: through the *"↩ Reset to default"* button in
  the editor, or by manually deleting the `.j2` file in
  `%APPDATA%\Fahmi2\prompts\`. Important: "default" = the template
  bundled with the installed application version; there is no notion of
  a historical "factory version".

## 3bis. Revision materials settings

**Revision materials → ⚙ Settings** (master-detail view):

| Category | Settings |
|----------|----------|
| **Materials** | Pick among the 8 types; "separate answer key" checkbox on evaluative materials (MCQs, true/false, cloze, open questions, mock exam). |
| **Difficulty** | Target audience (discovery / high school / undergraduate / master–expert), Bloom objective (auto / restitute / understand & apply / analyse & beyond), density (light / standard / dense), free directives. |
| **Languages** | All supported languages: the materials are written in the chosen language even when the source document is in another language (the orchestrator resolves a content language from an existing `consolidated.{lang}.md`). |
| **Model & cost** | LLM model, reasoning mode + effort level, temperature, **budget cap** (clean interruption; in parallel generation, a slight overshoot is tolerated by in-flight requests), **parallel tasks** (default 16, range 1–64: number of concurrent LLM calls to generate materials — DeepSeek's limit being per-concurrency, a high value stays safe; effective parallelism is bounded by the number of materials × languages). |
| **Export** | Formats offered by the **Export** button: Anki (`.apkg`), Markdown, PDF, HTML, Word (`.docx`). The Markdown of fields is converted to HTML on Anki export; Markdown/PDF/HTML/DOCX produce **one file per material and per answer key**. |

The **Estimate cost** button gives an order of magnitude (per material ×
language × chapter, depending on density and thinking); **Generate**
launches the generation (progress per material × language, *coarse*
resume of materials already up to date); **Open folder** opens
`<location>/pedagogy/`; **Export** offers 5 formats:
- **Anki `.apkg`** (flashcards → Basic, cloze → Cloze, MCQs → custom
  note; stable GUIDs, sub-decks per material, support/language/level/
  chapter tags);
- **Markdown**, **PDF**, **HTML** and **Word (`.docx`)**: **one file per
  material and per answer key**, named `<material>.<lang>.<ext>` and
  `<material>.<lang>.corrige.<ext>` (HTML is a self-contained document
  with embedded stylesheet).

## 3ter. Dialogue (chat) settings

**Dialogue → ⚙ Settings**:

| Setting | Description |
|---------|-------------|
| **Fidelity** | `strict` (default: answers only from the course, cites its sources via numbered clickable `[N]` markers, politely refuses out-of-corpus) or `augmented` (can supplement with its general knowledge in a flagged "Beyond the course" section). |
| **Retrieval** | `auto` (default: semantic if an OpenAI key is present, otherwise lexical), `lexical` (TF-IDF, 100 % offline) or `semantic` (OpenAI embeddings). |
| **Embedding model** | OpenAI model for the **cloud** retrieval (auto/semantic): `text-embedding-3-small` (default, economical), `text-embedding-3-large` (higher precision) or `text-embedding-ada-002` (previous generation). No effect in lexical (combo greyed out). **Changing the model forces a corpus reindex** at the next question (the index fingerprint includes the model). |
| **Query expansion** | On by default: rephrases the question into keywords via the LLM when lexical retrieval is weak (improves recall). |
| **Model & reasoning** | LLM model (`deepseek-v4-flash`/`pro`), reasoning mode + effort, temperature. |
| **Passages (top-K)** | Number of course excerpts injected as context (default 6). |

The queried corpus = the **consolidated** document + **glossary** of the
generation (chunked by section). **Semantic** retrieval builds a local
index (`<location>/chat/index.{lang}.npz`) reused as long as the course
hasn't changed (fingerprint: embedding model + consolidated **and
glossary** mtime + language). The Dialogue **automatically reloads** its
corpus as soon as the consolidated document or the glossary is
regenerated (before each answer and at the end of a generation): no need
to reload the project to start over with the up-to-date document.
**Conversations** are persisted under `<location>/chat/conversations/`.

> **Corpus language (per conversation).** On the left of the Dialogue
> panel, a **language** selector (visible as soon as the generation has
> produced **≥ 2 languages**) fixes the language of a **new** conversation:
> the Dialogue then reads the corresponding `consolidated.{lang}.md`,
> **cites** and **answers** in that language, and the cited glossary is
> **fully localised** there (term **and** definition). One conversation
> = one language (to switch language, create a new one). The semantic
> index is built **on demand**, once per language used (no embedding of
> unused languages).

> **Exhaustive cost.** The cost shown per exchange (and the conversation
> total) includes **all** spend: answer generation (DeepSeek), semantic
> retrieval embeddings (**initial indexing** of the corpus on the first
> question, then embedding of **each question**) and any query-expansion
> rephrasing. Embedding cost follows a **per-model** pricing grid (generic:
> changing or adding an embedding model only touches a price table). In
> **lexical** mode, retrieval is free (local): only DeepSeek's cost is
> counted.

> **Privacy**: **semantic** retrieval sends the corpus and the questions
> to **OpenAI** (embedding computation). In **lexical** mode, retrieval
> stays **100 % local** (only answer generation calls DeepSeek, as does
> the whole LLM tier of the application).

## 4. Environment variables (debug)

The application honours the standard Windows variables:

| Variable | Effect |
|----------|--------|
| `APPDATA` | Root folder of user data. Default: `%USERPROFILE%\AppData\Roaming`. |
| `LOCALAPPDATA` | Root cache folder. Default: `%USERPROFILE%\AppData\Local`. |
| `USERPROFILE` | User profile. Used as a fallback when `APPDATA`/`LOCALAPPDATA` are missing. |

These variables let you **redirect user data** to another location (useful
for tests or atypical installs).

## 5. Recommendations by usage

### 5.1 Small test project (1–5 short videos)

- STT provider: `openai_cloud` (fast and negligible in cost)
- LLM model: `deepseek-v4-flash`
- Thinking: off everywhere
- Temperature: 0.3 everywhere
- Budget cap: $1

### 5.2 Academic production (30–50 videos)

- STT provider: `faster_whisper_local` if a GPU is available (free),
  otherwise `openai_cloud`
- LLM model: `deepseek-v4-pro` (higher quality)
- Thinking on + `HIGH` for phases 4 (structuring), 5 (consolidation), 7
  (coherence). `MAX` reserved if quality is still insufficient (×6 on
  output).
- Temperature: 0.2 for translation, 0.4 elsewhere
- Style: `academic`
- Budget cap: $20–30 (check first with **💵 Estimate cost**)

### 5.3 Rapid iteration on a course in progress

- STT provider: `openai_cloud`
- LLM model: `deepseek-v4-flash`
- Style: `standard` or customised through directives
- Budget cap: $5
- Use the **resume**: edit prompts via the built-in editor (Edit → Edit
  prompts…), relaunch only the impacted phases by manually deleting the
  matching artefacts in `workspace/`.
