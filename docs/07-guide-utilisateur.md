# Fahmi2 — User guide

Document aimed at the non-technical end user. Up and running in under 10
minutes.

## 1. What is Fahmi2?

Fahmi2 automatically turns your courses — **videos, audio files, YouTube
links, or text documents** (PDF, Word, Markdown, txt) — into structured
written Markdown documents, with a glossary and a consolidated document,
in the language of your choice (FR or EN; up to 7 languages on the
generation side).

The application runs **entirely on your machine**: no server, no cloud
unless you explicitly choose OpenAI cloud Whisper or DeepSeek (the
content sent to the cloud then goes exclusively through those two APIs,
under your keys).

The interface is available in **French and English**: pick it from **Edit
→ Global settings → Language** (the change applies at the next launch).

## 2. Installation

1. Download `Fahmi2-X.Y.Z-win64.zip`.
2. Unzip it to a folder (e.g. on your Desktop or in `C:\Apps\Fahmi2\`).
3. Double-click **`Fahmi2.exe`**.
4. On the very first launch, Windows may show *"Windows protected your
   PC"* (unknown publisher). Click **"More info"** then **"Run anyway"**.
   This warning will only appear once.

You're in. No system install, no admin rights.

## 3. First configuration: API keys

To work, the application needs one or two API keys you must obtain from
the providers:

- **DeepSeek key** (mandatory) — for rephrasing and structuring. Sign up
  at <https://platform.deepseek.com> and generate a key.
- **OpenAI key** (optional) — only if you use cloud Whisper for
  transcription. Sign up at <https://platform.openai.com>.

**To enter them**:

1. Menu **Edit → Global settings**.
2. Paste your keys into the matching fields.
3. Click **Save**.

Your keys are **encrypted on your disk** by Windows (DPAPI). They can
only be decrypted by your Windows account.

## 4. Creating a project

**File → New project**: give the project a **name** and pick a
**location** (the project's working folder), then click **OK**. The
project appears in the list on the left.

Select it, then in the **Generation** tab click **⚙ Settings** to
configure the generation (6-category view):

| Category | Fields |
|----------|--------|
| **Sources** | Input folder (videos/audio/documents) · YouTube links · Source ordering & exclusion |
| **Style** | Style (`casual`/`standard`/`professional`/`academic`) · **Consolidation mode** (Ordered: one chapter per source, in order; or Thematic rewrite: the AI reorganises and merges everything by themes, like a synthesis — source order then has no effect) · Free directives · Document languages (produced languages + which one is the **primary**/original) |
| **Transcription** | STT provider (`openai_cloud` without a GPU, otherwise `faster_whisper_local`) · *Simultaneous transcriptions* (cloud) |
| **AI generation** | LLM model (`deepseek-v4-flash` to start) · Budget cap · *Simultaneous AI calls* |
| **AI phases** | Thinking, effort, temperature, retries per LLM phase (advanced) |
| **Export** | Offered export formats: Markdown / PDF / HTML / Word (`.docx`) (none by default) |

Validate: the detected sources preview appears in the cockpit.

## 5. Launching the processing

1. Pick your project in the list on the left.
   The application shows three tabs: **Generation** (the cockpit below),
   **Revision materials** (flashcards, MCQs, summary sheets… generated
   once the Generation has finished — see §8), and **Dialogue** (chat
   anchored on the corpus — see §9).
2. (Optional but recommended) Click **💵 Estimate cost** to see the
   expected budget before launching. The dialog shows the detected
   sources, the total duration, a **per-phase breakdown** (accounting for
   reasoning mode if enabled) and a **total as an indicative range**
   (≈ X, ±33 % range), with a warning if the upper end of the range may
   exceed the cap.
3. Click **▶ Run** at the top.

The central grid starts filling:

- **One row per source** (video, audio, document, or YouTube link).
- **One column per phase** (8 columns: STT, Terms, Glossary, Rephras.,
  Structur., Consolid., Translation, Coherence).
- Each cell shows progress through **colour + symbol**:
  - `·` grey: pending
  - `▶` blue: running
  - `✓` green: completed
  - `✗` red: failed (rare, see [Troubleshooting](#10-troubleshooting))
  - `↷` indigo: skipped (already done in the previous run)

At the top, **6 cards** display:

- **Status** of the project (Running / Paused / Completed…)
- **Sources** completed (e.g. *"3 / 12"*)
- **Phases** completed (e.g. *"15 / 96"*)
- **Languages** of output (number of produced languages)
- **Duration** elapsed (refreshed every second)
- **Cost** cumulative in USD (with cap if set)

At the bottom, the **Logs** panel lists recent actions and messages,
coloured by level (grey/amber/red).

## 6. Pausing or cancelling

- **⏸ Pause**: interrupts the processing at the next safe step. You can
  close the application — the work is saved.
- **▶ Resume**: picks up exactly where you stopped. No work is redone.
- **✕ Cancel**: marks the run as cancelled. You can re-run later if you
  want.
- **↺ Reset**: deletes **everything that has been generated** for the
  current tab (deliverables and history for Generation; materials for
  Revision materials), after confirmation. Irreversible; unavailable
  during a run.

In the projects list (left), each project shows a coloured **status dot**
reflecting the worst-of-two status (Generation / Revision materials)
(created, running ▶, completed ✓, failed ✗, cancelled ⊘); hover for the
detail.

## 7. Retrieving the produced files

When the project is finished (status **Completed**), click the **📂
Output folder** button at the top right: Windows Explorer opens directly
on the right folder. You'll find:

```
<location>/generation/output/
├── consolidated.fr.md     ← Consolidated French document (navigable)
├── consolidated.en.md     ← Consolidated English document (if requested)
├── glossary.fr.md         ← French glossary (table)
├── glossary.en.md         ← English glossary
└── per-video/
    ├── fr/
    │   ├── XXX.md         ← One file per source (FR)
    │   └── …
    └── en/
        └── …
```

**Consolidated document**: global title, introduction, **clickable table
of contents** to every chapter and sub-section, chapters **hierarchically
numbered** (1, 1.1, 1.1.1…), conclusion. Elegant semantic insertions:
📝 Note, 💡 Example, 📖 Definition, 🎯 Exercise.

**Glossary**: **Term / Acronym / Meaning / Definition** table. The
*Meaning* column stays in the original language of the acronym (for
example ROI = *Return On Investment*, even in a French glossary).

All files are in **Markdown**, readable in any editor (Notepad, VS Code,
Typora, Obsidian…). The TOC with clickable links is displayed directly
in VS Code, Obsidian, GitHub, GitLab, etc.

**Exporting to PDF, HTML, or Word**: the **📦 Export** button (top
right) writes the consolidated document and the glossary — one file per
language (`consolidated.{lang}`, `glossary.{lang}`) — in the chosen
format (**Markdown**, **PDF**, **HTML**, or **Word `.docx`**), to a
folder of your choice. First tick the desired formats under **⚙ Settings
→ Export** (none is ticked by default). HTML is a self-contained
document, openable in a browser; PDF also handles **Chinese** and
**Arabic** (right-to-left).

## 8. Generating revision materials

Once the Generation has finished, the **Revision materials** tab turns
the consolidated document and the glossary into revision material:
flashcards, MCQs, true/false, cloze, open questions, summary sheets, key
points, and a mock exam.

> **Prerequisite**: having launched the **Generation** at least once on
> the project (a consolidated document and a glossary must exist). The
> materials are produced **from** that content.

### Configuring

Pick the project, open the **Revision materials** tab, then click
**⚙ Settings** (same category view as Generation):

| Category | Fields |
|----------|--------|
| **Materials** | Types to generate (flashcards, MCQs, summary sheets…) · separate answer key for evaluative materials |
| **Difficulty** | Target audience (required) · Bloom objective (`Auto` / `Restitute` / `Understand & Apply` / `Analyse & Beyond`) · free teaching directives · density (`light` / `standard` / `dense`) |
| **Languages** | Material languages (default: the ones actually produced by Generation) |
| **Model & cost** | LLM model · reasoning mode · cost cap · *Parallel tasks* |

### Estimating and generating

1. (Recommended) **💵 Estimate cost**: shows the expected budget (per
   material × language × chapter, depending on density and reasoning
   mode).
2. **▶ Run**: the progress table fills (one row per material × language).
   A coloured **status badge** at the top shows freshness at a glance:
   *⚙ To configure* → *⚠ Generation required* → *● Ready to generate* →
   *✓ Materials up to date* (green) → *⟳ Materials to regenerate*
   (amber).

If you relaunch Generation later, the existing materials are marked
**stale**: regenerate them to realign on the new content. Materials
already up to date are **skipped** (no unnecessary regeneration).

### Retrieving and exporting

Materials are written to `<location>/pedagogy/{material}/{lang}/`
(structured `.json` + readable `.md`, plus `.corrige.md` for evaluative
items with a separate answer key). You can edit them directly.

The **📦 Export** button offers the formats you ticked in the settings
("⚙ Settings → Export → Offered export formats"):

- **Anki (`.apkg`)**: importable into Anki — sub-decks per material,
  Basic / Cloze / MCQ cards, tags (material / language / level /
  chapter). Re-imports do not create duplicates (stable identifiers).
  The Markdown formatting of the cards (lists, bold) is rendered as
  HTML inside Anki.
- **Markdown**: one file per material and per answer key, per language.
- **PDF**: same documents, ready to print (Chinese and Arabic handled).
- **HTML**: self-contained document (openable in a browser, formatting
  included).
- **Word (`.docx`)**: same documents, editable in Word/LibreOffice.

## 9. Dialoguing with your course

Once the Generation has finished, the **Dialogue** tab lets you **ask
questions** about your course and obtain **cited** natural-language
answers.

> **Prerequisite**: having launched the **Generation** at least once (a
> consolidated document must exist). Otherwise the tab invites you to do
> so.

1. Pick the project, open the **Dialogue** tab.
2. Type your question at the bottom, click **Send** (or Enter).
3. The answer is written progressively, **formatted** (bold, lists,
   tables). By default, the assistant answers **only from your course**
   and indicates its **sources**; click a source to read the excerpt. If
   it cannot find the information, it answers "This point is not covered
   by the course."
4. The **cost** of the exchange is displayed under the answer (and the
   conversation **cumulative cost**). It is complete: it includes the
   answer **and** the semantic-retrieval embeddings (the **lexical**
   mode, on the other hand, is free).

You can open several **conversations** (the **＋ New conversation**
button); they are preserved even after closing the application. To
**delete** one, **right-click** it in the list → *"Delete conversation"*
(confirmation requested).

> **Dialoguing in another language.** If your course has been generated
> in **several** languages, a **language** selector appears above
> **＋ New conversation**: pick the language **before** creating the
> thread. The Dialogue will read, **cite**, and **answer** in that
> language (one conversation = one language; to switch, create a new
> one). In the list, each conversation is **prefixed by its language
> code** (e.g. *"EN · what is ebitda?"*) for quick recognition.

The **⚙ Settings** button lets you choose the answering mode (strict, or
"augmented" supplementing with general knowledge), the way the course is
searched, the LLM model **and** the embedding model (semantic search) —
see [04-parametrage.md](04-parametrage.md) §3ter.

## 10. Troubleshooting

### *"Windows protected your PC"*

Normal on the first launch. Click *"More info"* → *"Run anyway"*. It
will not come back.

### *"NVIDIA GPU not found"*

You selected local mode without having an NVIDIA GPU. Open the
**Generation → ⚙ Settings → Transcription** tab and switch to
`openai_cloud`.

### *"Invalid DeepSeek key"*

Check the key in **Edit → Global settings** (copy-paste recommended to
avoid stray spaces).

### *"DeepSeek rate limit reached"*

The application retries automatically. No action required.

### *"Budget cap reached"*

You set a cap and it is reached. To continue:

1. Menu **Edit → Global settings** (or re-edit the project).
2. Raise or remove the cap.
3. Come back to the project, click **▶ Resume**.

### A source failed (`✗` cell)

Double-click the red cell to see the error detail. To re-run just this
phase: click *"Replay this phase"* in the detail window.

### The application crashed

Relaunch `Fahmi2.exe`. The state is saved: your project is intact, click
**▶ Resume** to continue.

## 11. Application upgrades

When a new version is available:

1. Download the new `.zip`.
2. Close Fahmi2 if open.
3. Unzip the new `.zip` (you can overwrite the previous folder).
4. Relaunch `Fahmi2.exe`.

Your projects and keys are **automatically preserved**. If an internal
adaptation is needed (database upgrade), it is applied automatically
with a prior safety backup.

## 12. Uninstall

1. Delete the folder where you unzipped Fahmi2.
2. If you also want to wipe **all your projects and keys**:
   - In Windows Explorer, type `%APPDATA%\Fahmi2` in the address bar and
     press Enter → delete that folder.
   - Same with `%LOCALAPPDATA%\Fahmi2`.

Nothing else stays on your system.

## 13. Tips

### Switching the interface language

**Edit → Global settings → Language**: pick *Français* or *English*. The
change applies at the next launch (Qt does not relocalise widgets
already shown).

### Test before a large processing

Before launching a project on 50 videos, create a "test" project with
2–3 videos only, in `deepseek-v4-flash` without thinking. Check the
rendering quality before launching the definitive project (perhaps in
`deepseek-v4-pro` with thinking for maximum quality).

### Estimate cost before every launch

The **💵 Estimate cost** button shows the expected budget in a few
seconds. **Important**: if you turn on reasoning mode (*thinking*) for
the phases, the cost may be 2 to 6× higher. The estimation accounts for
it.

### Budget cap for safety

Always set a cost cap, even a generous one. If something goes wrong (an
LLM call looping for example), the cap limits the damage.

### Customising prompts

If you want to fine-tune the tone or format beyond the *Style
directives*, open **Edit → Edit prompts…** Pick a prompt on the left,
edit the text on the right, click **💾 Save**. To go back to the
original version shipped with the application, click **↩ Reset to
default**. No need to restart: the new prompt is used at the next
launch. The catalogue covers the **generation phases** **and** the
**revision materials** prompts (`pedagogy_*`): you customise the
flashcards / MCQs / sheet generation instructions the same way.

### Keeping intermediate artefacts

The `<location>/generation/` folder contains the working files. If you
only want the final deliverables, you can delete this folder after
retrieval. But keep it if you might re-edit or re-run specific phases.

### Rendering style

If you don't like the rendering (too dry, too verbose, etc.), edit the
**Style directives** field in **Generation → ⚙ Settings → Style** and
relaunch. No need to redo everything — resume skips already-done phases.

### Homogeneous glossary

The glossary is built in two passes (extraction then cross-source
reconciliation). The more sources on the same domain in your folder, the
richer and more consistent the glossary will be. Acronyms (ROI, PIB,
IFRS…) come with their **original meaning** alongside the definition —
which stays in the language where the acronym was coined (*Return On
Investment* for ROI, even in a French glossary).

## 14. Privacy

- **No telemetry** is sent by the application.
- **Your content never leaves your machine** except towards the APIs you
  have explicitly configured (DeepSeek + possibly OpenAI for cloud
  Whisper).
- **Your API keys are encrypted** on disk by Windows DPAPI: only your
  Windows account can read them.

## 15. Need help?

- For functional questions: see
  [01-presentation-fonctionnelle.md](01-presentation-fonctionnelle.md).
- For the detailed parameters: see
  [04-parametrage.md](04-parametrage.md).
- For advanced operation (logs, backups…): see
  [05-exploitation.md](05-exploitation.md).
