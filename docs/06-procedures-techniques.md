# Fahmi2 — Technical procedures (developer)

Cookbook of commands for maintaining, developing, and distributing
Fahmi2.

## 1. Environment setup

### 1.1 Creating the venv and installing

```powershell
# Python 3.12 explicit (recommended)
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1

# Upgrade pip then editable install
python -m pip install --upgrade pip
pip install -e ".[dev]"
pip install pyinstaller>=6.10

# Activate the pre-commit hooks (lint + types + quick tests)
pre-commit install
```

### 1.2 Updating dependencies

```powershell
# Check what is outdated
pip list --outdated

# Update a specific dependency
pip install --upgrade <package>

# Reinstall the project in editable mode
pip install --upgrade -e ".[dev]"
```

## 2. Tests

### 2.1 Run the whole suite

```powershell
pytest
```

### 2.2 Run a subset

```powershell
# A layer
pytest tests/unit/domain
pytest tests/unit/core
pytest tests/unit/infra
pytest tests/unit/app
pytest tests/unit/ui
pytest tests/unit/pipeline
pytest tests/unit/i18n
pytest tests/e2e

# A single file
pytest tests/unit/core/test_paths.py

# A single test
pytest tests/unit/core/test_paths.py::test_paths_uses_env_appdata -v
```

### 2.3 Coverage

```powershell
# Console output
pytest --cov=src/fahmi2 --cov-report=term-missing

# HTML report
pytest --cov=src/fahmi2 --cov-report=html
# Open htmlcov/index.html
```

### 2.4 Verbose run with first-failure stop

```powershell
pytest -v -x
```

### 2.5 Re-run only failed tests

```powershell
pytest --lf
```

### 2.6 Markers and exclusions

```powershell
# Skip the E2E tests (fast subset only)
pytest --ignore=tests/e2e

# Tests matching a pattern
pytest -k "test_engine"
```

## 3. Linting and formatting

### 3.1 Ruff (linter + formatter)

```powershell
# Linter (check only)
ruff check .

# Linter with auto-fix of fixable issues
ruff check --fix .

# Formatter (equivalent of black)
ruff format .

# Format check without modifying
ruff format --check .
```

### 3.2 mypy (type checker)

```powershell
# Strict (config in pyproject.toml)
mypy src tests

# On a single file
mypy src/fahmi2/pipeline/engine.py

# Incremental mode (cache)
mypy --incremental src tests
```

### 3.3 Pre-commit (before each commit)

```powershell
# Run every hook on modified files
pre-commit run

# Run every hook on the whole codebase
pre-commit run --all-files

# Specific hook
pre-commit run ruff
pre-commit run mypy
```

## 4. Running the application in dev mode

```powershell
# Compile the UI translations first (.qm regenerated)
.\.venv\Scripts\python.exe scripts\i18n_compile.py

# Launch the main window
python -m fahmi2.ui.app_main

# With an isolated APPDATA directory (useful for manual tests)
$env:APPDATA = "C:\Temp\Fahmi2-test"
python -m fahmi2.ui.app_main
```

## 5. UI translations (i18n)

The application's UI is internationalised through the native Qt stack
(`QTranslator` + `.ts` / `.qm`). Source language: French. Available
languages: French (source), English. Adding a language only requires
adding a value to the `AppLanguage` enum + creating/translating a `.ts`.

### 5.1 Extract translatable strings (regenerate `.ts`)

```powershell
.\.venv\Scripts\python.exe scripts\i18n_extract.py
```

Wraps `pyside6-lupdate -extensions py`. Updates each
`src/fahmi2/i18n/translations/fahmi2_<code>.ts` while preserving existing
translations. Versioned in git.

### 5.2 Compile to `.qm`

```powershell
.\.venv\Scripts\python.exe scripts\i18n_compile.py
```

Wraps `pyside6-lrelease`. Generates
`src/fahmi2/i18n/compiled/fahmi2_<code>.qm`. **Not versioned** (artefact
derived from `.ts`), regenerated at each build. The `.spec` ships them
through `("src/fahmi2/i18n/compiled/*.qm", "fahmi2/i18n/compiled")` in
`datas`.

### 5.3 Inventory of UI strings

```powershell
.\.venv\Scripts\python.exe scripts\i18n_inventory.py
```

Counts the literal strings under `src/fahmi2/ui/` per file. Useful to
estimate the effort of a wave of new translations and to flag files where
strings have grown.

### 5.4 Adding a new UI language

1. Add the value to `AppLanguage` in `src/fahmi2/i18n/languages.py` (e.g.
   `DE = "de"`) and its native label to `LANGUAGE_LABELS` (e.g.
   `AppLanguage.DE: "Deutsch"`).
2. `python scripts/i18n_extract.py` — generates
   `fahmi2_de.ts` (target language).
3. Translate the `<translation type="unfinished"></translation>` entries
   (in a text editor or Qt Linguist).
4. `python scripts/i18n_compile.py` — produces `.qm`.
5. Rebuild the PyInstaller bundle: the `.qm` is shipped via `datas`.
6. Update the test `tests/unit/i18n/test_i18n.py` with a few smoke
   assertions for the new language (recommended to keep the
   anti-regression net).

### 5.5 Translation patterns (i18n source rules)

- `QObject` methods → `self.tr("French source")`.
- Free functions / module constants → `QCoreApplication.translate("Context",
  "French source")` with **literal context AND literal source**
  (`pyside6-lupdate` does not follow a wrapper function nor a variable
  argument).
- Module-level constants with deferred resolution → `QT_TRANSLATE_NOOP(
  "Context", "source")` for extraction marking + later resolution via
  `QCoreApplication.translate`. Wrap with `typing.cast(str, ...)` if mypy
  complains (PySide6 stubs type `QT_TRANSLATE_NOOP → object`).
- The standard button localiser is `ui._components.localize_button_box`
  (replaces `frenchify_button_box`, kept as a backwards-compatible alias).

## 6. Packaging and distribution

### 6.1 Full build in one command

```powershell
.\packaging\build.ps1
.\packaging\make-portable-zip.ps1
```

The final `.zip` appears at `dist/Fahmi2-<version>-win64.zip`.

### 6.2 Individual steps

```powershell
# Download portable ffmpeg (idempotent)
.\packaging\fetch-ffmpeg.ps1

# Compile UI translations before PyInstaller (otherwise the EN UI stays in FR)
.\.venv\Scripts\python.exe scripts\i18n_compile.py

# PyInstaller build only
pyinstaller packaging/fahmi2.spec --noconfirm --clean

# Zip only (after a build)
.\packaging\make-portable-zip.ps1
```

### 6.3 Test the built EXE

```powershell
.\dist\Fahmi2\Fahmi2.exe
```

### 6.4 Check the bundle size

```powershell
Get-ChildItem dist/Fahmi2 -Recurse | Measure-Object -Property Length -Sum |
    Select-Object @{n='SizeMB';e={[math]::Round($_.Sum / 1MB, 1)}}
```

### 6.5 Verify the SHA-256 of the distributed `.zip`

```powershell
Get-FileHash dist/Fahmi2-*.zip -Algorithm SHA256
```

## 7. Git management

### 7.1 Standard workflow

```powershell
git status
git diff
git add <files>
git commit -m "type(scope): message"
git push
```

### 7.2 Commit conventions

- `feat(scope):` new feature
- `fix(scope):` bug fix
- `refactor(scope):` refactor without behaviour change
- `docs(scope):` documentation
- `test(scope):` tests
- `chore:` maintenance task (dependencies, config)

Examples:

```
feat(pipeline/handlers): Phase 5 consolidation
fix(infra/llm): correct mapping of DeepSeek 5xx errors
docs(installation): clarify the SmartScreen procedure
chore(deps): bump scikit-learn to 1.8
```

### 7.3 Milestone tags

```powershell
# List
git tag

# Create an annotated tag
git tag -a milestone-XX-<name> -m "Milestone description"

# Push tags
git push --tags
```

## 8. SQLite schema migrations

### 8.1 Creating a new migration

1. Create `src/fahmi2/core/migrations/vNN_to_vMM.py`:

```python
from fahmi2.core.migrations.runner import Migration

def _apply(state):
    # ALTER TABLE or migration logic
    state.schema_version = MM

def vNN_to_vMM_migration():
    return Migration(from_version=NN, to_version=MM, apply=_apply)
```

2. Register the migration in the `MigrationRunner` at startup (see
   `app_main.py`, to be extended in a future version).

3. Bump `SCHEMA_VERSION` in `src/fahmi2/infra/storage/sqlite_state.py`.

4. Update `_schema.sql` to reflect the target schema.

5. Add tests under `tests/unit/core/`.

## 9. Debugging

### 9.1 App logs

```powershell
# In dev mode, logs go to stderr in addition to the file by default
python -m fahmi2.ui.app_main 2>&1 | Tee-Object -FilePath "debug.log"
```

### 9.2 Inspecting a SQLite database

```powershell
# With sqlite3 CLI (install separately if missing)
sqlite3 "$env:APPDATA\Fahmi2\projects.db"

# A few useful queries
.tables
.schema phase_executions
SELECT * FROM projects;
SELECT run_id, phase_id, source_id, status FROM phase_executions
  WHERE run_id = '...' ORDER BY id;
```

### 9.3 Inspecting an `events.jsonl` file

```powershell
# Count by severity
Get-Content events.jsonl | ConvertFrom-Json |
    Group-Object severity | Format-Table Name, Count

# List errors
Get-Content events.jsonl | ConvertFrom-Json |
    Where-Object severity -in @("error","fatal") |
    Select-Object timestamp, code, message
```

### 9.4 Interactive debugger (pdb)

```python
import pdb
pdb.set_trace()  # to insert in the code
```

Then run `python -m fahmi2.ui.app_main`. The debugger will trigger at the
insertion point.

### 9.5 Reproducing a bug with an isolated SQLite state

```powershell
# Copy a prod DB into a test space
Copy-Item "$env:APPDATA\Fahmi2\projects.db" "C:\Temp\bug-repro.db"

# Launch with a redirected APPDATA
$env:APPDATA = "C:\Temp\bug-repro"
mkdir "C:\Temp\bug-repro\Fahmi2"
Copy-Item "C:\Temp\bug-repro.db" "C:\Temp\bug-repro\Fahmi2\projects.db"
python -m fahmi2.ui.app_main
```

## 10. Performance

### 10.1 Profiling

```powershell
# cProfile snapshot
python -m cProfile -o profile.out -m fahmi2.ui.app_main

# Analyse with snakeviz
pip install snakeviz
snakeviz profile.out
```

### 10.2 Memory

```powershell
pip install memory-profiler
python -m memory_profiler script.py
```

## 11. Bumping the version

1. Edit `version = "..."` in `pyproject.toml`.
2. Add an entry to `CHANGELOG.md`.
3. Commit `chore: bump version to X.Y.Z`.
4. Tag `git tag -a vX.Y.Z -m "..."`.
5. Push: `git push && git push --tags`.
6. Build and distribute the matching `.zip`.

## 12. Adding a new pipeline phase

1. Create `src/fahmi2/pipeline/handlers/phase_N_xxx.py` inheriting from
   `PhaseHandler`. If the phase is **per-source and parallelisable**
   (independent units, I/O-bound), override `max_parallel_workers(ctx)` to
   return the desired pool (inherited default: `1` = sequential). For a
   batch phase, parallelise its internal loops via
   `core/concurrency/map_bounded`.
2. Create the default Jinja2 template at
   `src/fahmi2/infra/prompts/defaults/phase_N_xxx.j2`.
3. Add `PhaseId.XXX` to `src/fahmi2/domain/enums.py`.
4. Update `_PIPELINE_ORDER` in
   `src/fahmi2/pipeline/phase_registry.py`.
5. Register the handler in the `PhaseRegistry` construction (see E2E
   tests and `app_main.py`).
6. Add the cost-multiplier binding in `_LOAD_FACTORS` in
   `src/fahmi2/app/cost_estimator.py`.
7. Write tests: `tests/unit/pipeline/handlers/test_phase_N_xxx.py`.
8. Run the full suite + lint + types.

## 13. Adding an LLM provider

1. Implement the `LLMProvider` (Protocol) in
   `src/fahmi2/infra/llm/<provider>_adapter.py`.
2. Add a pricing grid in `src/fahmi2/infra/llm/_pricing.py`.
3. Extend the `LLMModel` enum in `src/fahmi2/domain/enums.py`.
4. Add a **label** in `src/fahmi2/ui/_model_labels.py` (in
   `_LLM_MODEL_SOURCES`, returned by `llm_model_labels()`) — **mandatory**:
   the settings combos are populated by these label dictionaries (via
   `labeled_enum_combo`), not by the enum itself. A member without a
   label **will not appear** in the combo (a completeness test detects
   it; see `tests/unit/ui/test_model_labels.py`).
5. Write tests (with SDK mocking or `responses`).

## 14. Adding an embedding model (Dialogue) or a transcription model (STT)

Same recipe as for LLM models — the app follows the **enum + pricing
grid + label** triptych everywhere:

- **Embedding** (Dialogue's semantic retrieval): `EmbeddingModel` enum
  (`domain/enums.py`) + pricing in `infra/embeddings/_pricing.py`
  (USD/Mtok) + label in `_EMBEDDING_MODEL_SOURCES` (returned by
  `embedding_model_labels()`). The model is part of the index fingerprint
  → changing it **forces a reindex**.
- **STT**: `LocalSttModel` / `CloudSttModel` enums + cloud pricing in
  `infra/stt/_pricing.py` (USD/min) + labels in `_LOCAL_STT_MODEL_SOURCES`
  / `_CLOUD_STT_MODEL_SOURCES`. A cloud model without timestamps
  (`gpt-4o-*`) switches the adapter to `json` (single segment per chunk)
  — see `OpenAIWhisperAdapter._VERBOSE_JSON_MODELS`.

## 15. Adding a content language

The `Language` enum covers 7 languages (fr/en/de/es/it/zh/ar). To add
one:

1. Add the value to `Language` (`src/fahmi2/domain/enums.py`).
2. Add its **label** in `domain/languages._LANGUAGE_NAMES` (**single
   source** reused by prompts, UI, and renderers).
3. Add its **headers** and **glossary title** in
   `domain/glossary._HEADERS_BY_LANGUAGE` / `_TITLE_BY_LANGUAGE` (English
   fallback otherwise).
4. Add its **STT detection aliases** (full Whisper name → ISO code) in
   `infra/stt/openai_whisper_adapter._WHISPER_LANGUAGE_ALIASES`.
5. **PDF rendering**: if the script requires a dedicated font (CJK),
   register it in `markdown_pdf._CJK_LANGUAGES` and wire its system font
   (cf. the YaHei resolution); if the script is **right-to-left**,
   register it in `domain/languages._RTL_LANGUAGES` (**single RTL
   source** for PDF/HTML/DOCX) **and** in
   `markdown_pdf._PDF_LANG_RENDERING` (font family + `pdf:language` tag
   for reshaping/bidi). DOCX (RTL via `is_rtl`) and HTML (`dir`) are
   inferred from `_RTL_LANGUAGES`, no dedicated code.
6. Write/complete tests (glossary, STT detection, PDF/DOCX rendering
   according to the script), then run the full suite + lint + types.

## 16. Adding an export format

Document formats (Markdown / PDF / HTML / DOCX) all go through the shared
core `app/document_export.write_documents`; Anki (`.apkg`) is separate.
To add a document format:

1. Extend the `ExportFormat` enum (`src/fahmi2/domain/enums.py`).
2. Declare its **extension** in `markdown_pdf.EXTENSION_BY_FORMAT`.
3. Wire the rendering in `app/document_export.write_documents` (+ a
   *renderer* in `infra/export/` if the format does not derive from the
   existing HTML/Markdown).
4. Add a **label** in `ui/pedagogy_labels._EXPORT_SOURCES` (returned by
   `export_labels()`, shared by both tabs' export pickers).
5. To also offer it in **generation**, add it to
   `domain/generation.GENERATION_EXPORT_FORMATS`.
6. Write tests (rendering + collection) then run the full suite + lint
   + types.

## 17. The Dialogue (chat) — artefacts and index

Per-project artefacts (under `<location>/chat/`):

- `conversations/<conversation_id>.json` — persisted conversations
  (readable off-session; deletable from the UI or by erasing the file).
- `index.{lang}.npz` — **semantic index** (corpus embeddings + validity
  fingerprint: model + language + consolidated **and glossary** mtimes —
  editing the glossary, even with the same number of terms, therefore
  triggers a reindex). To force a reindex, delete this file (or use
  `infra.retrieval.semantic.purge_index`); it is rebuilt the moment the
  fingerprint changes anyway.

The queried corpus is the **consolidated document**
(`generation/output/`) + the glossary (`generation/glossary_master.json`),
chunked on the fly at each session (no regeneration required after
changing the chunking).

## 18. Quality audit

Before each release, run through:

```powershell
# 1. Full tests
pytest --cov=src/fahmi2 --cov-report=term-missing

# 2. Lint clean
ruff check .

# 3. Strict types
mypy src tests

# 4. Coverage thresholds
# (should be >= 85 % overall)

# 5. UI translations compiled
.\.venv\Scripts\python.exe scripts\i18n_compile.py

# 6. Packaging build
.\packaging\build.ps1

# 7. Manual test of the built EXE (verify EN UI switches correctly)
.\dist\Fahmi2\Fahmi2.exe

# 8. Zip generation
.\packaging\make-portable-zip.ps1

# 9. Verify the .zip on a target machine
```
