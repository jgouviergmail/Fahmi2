# Fahmi2 packaging (portable Windows `.zip`)

> Fully automated build: ffmpeg is downloaded and bundled by the scripts.
> The end user has no external dependency to install.

## Developer prerequisites

1. **Python 3.11 or 3.12** installed (see
   [docs/03-installation.md](../docs/03-installation.md)).
2. **venv activated** with the dependencies:
   ```powershell
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   pip install -e ".[dev]"
   pip install pyinstaller>=6.10
   ```
3. **Internet access**: the build script downloads portable ffmpeg unless it
   is already present under `vendor/ffmpeg/bin/`.

## One-command build

```powershell
.\packaging\build.ps1
```

The script orchestrates the following automatically:

1. **fetch-ffmpeg.ps1** — downloads `ffmpeg-release-essentials.zip` from
   <https://www.gyan.dev/ffmpeg/>, verifies the SHA-256, **verifies the
   presence of the `libopus` encoder** (required for the cloud-STT audio
   preparation — the build fails otherwise), extracts `ffmpeg.exe` and
   `ffprobe.exe` to `vendor/ffmpeg/bin/`. Idempotent: skips if the binaries
   are already present.
2. Cleans the previous `build/` and `dist/`.
3. Verifies `pyinstaller` is available.
4. **PyInstaller `--onedir`**: produces `dist/Fahmi2/` containing
   `Fahmi2.exe`, every Python dependency, bundled ffmpeg + ffprobe, the
   prompt templates, the SQLite schema, and the localised message files.

## Distribution archive

```powershell
.\packaging\make-portable-zip.ps1
```

Produces `dist/Fahmi2-<version>-win64.zip` from `dist/Fahmi2/`.

## Testing the built EXE

```powershell
.\dist\Fahmi2\Fahmi2.exe
```

The application must start in under 5 seconds and display the main
window.

## Checking the size

```powershell
Get-ChildItem dist/Fahmi2 -Recurse | Measure-Object -Property Length -Sum |
    Select-Object @{n='SizeMB';e={[math]::Round($_.Sum / 1MB, 1)}}
```

Order of magnitude (v1.0.0): **≈ 670 MB deployed** (`dist/Fahmi2/`),
**≈ 270 MB zipped** — embedded Python + PySide6 + faster-whisper/CTranslate2 +
ffmpeg (≈ 200 MB) + sklearn + reportlab/xhtml2pdf.

## Distribution

Distribute the `.zip`. The end user:

1. Downloads `Fahmi2-<version>-win64.zip`.
2. Unzips it to any folder (e.g. `C:\Apps\Fahmi2\`).
3. Double-clicks `Fahmi2.exe`.
4. On first launch, **SmartScreen** shows an *"Unknown publisher"*
   warning — click *"More info"* → *"Run anyway"* (once).

**No further manual action**: ffmpeg is bundled, user data (projects,
encrypted API keys, etc.) is created automatically under `%APPDATA%\Fahmi2\`
and `%LOCALAPPDATA%\Fahmi2\`.

## User-side upgrade

1. Download the new `.zip` version.
2. Close Fahmi2 if open.
3. Unzip the new `.zip` (may overwrite the previous folder).
4. Relaunch `Fahmi2.exe`.

User data is **automatically preserved** and migrated where needed by the
internal `MigrationRunner`.

## Technical details

### Layout of `dist/Fahmi2/`

```
dist/Fahmi2/
├── Fahmi2.exe                       ← Entry point
├── ffmpeg.exe                       ← Bundled (from vendor/)
├── ffprobe.exe                      ← Bundled (from vendor/)
├── yt-dlp.exe                       ← Bundled (from vendor/)
├── *.dll, *.pyd                     ← Python runtime + PySide6
├── _internal/
│   ├── fahmi2/
│   │   ├── core/errors/messages.fr.json
│   │   ├── infra/prompts/defaults/*.j2   ← 8 phases + 3 phase_5_* thematic + phase_6_glossary_localization + 8 pedagogy_* + 3 chat_*
│   │   ├── infra/storage/_schema.sql
│   │   └── i18n/compiled/*.qm            ← UI translations (FR source + EN)
│   └── genanki/                          ← collected data (apkg_schema.sql, apkg_col.anki2)
└── …
```

### Export dependencies (genanki / markdown / xhtml2pdf / htmldocx)

Exports (Anki / Markdown / PDF / HTML / Word) bring in extra dependencies.
They are **already wired up** in `packaging/fahmi2.spec` (gitignored;
validated against the v1.0.0 build):

- **`xhtml2pdf`** (**PDF** export, HTML rendering) relies on **`reportlab`**
  and pulls in `html5lib`, `pypdf`, `Pillow`, `svglib`, `arabic-reshaper`,
  `python-bidi`, `pyHanko` — **all pure Python** (no native binary), so they
  are *bundleable* but they **inflate** the archive (≈ 270 MB zipped,
  ≈ 670 MB deployed). The `.spec` applies `collect_all('xhtml2pdf')` +
  `collect_all('reportlab')` (data and ReportLab's **internal fonts**) +
  `collect_all('arabic_reshaper')` (config file). The **HTML** export adds
  nothing extra (pure Python).
- **`markdown`** (Markdown→HTML rendering, shared by HTML/PDF) loads its
  extensions (`tables`, `toc`…) **by name** → `collect_submodules('markdown')`
  in the `.spec`.
- **`genanki` 0.13.1** (`.apkg` export) **inlines the schema as Python
  modules** (`apkg_col.py` / `apkg_schema.py`): **no data file to collect** —
  its modules are bundled by import analysis. (`collect_data_files('genanki')`
  returns `[]`; kept in the `.spec` as a safety net in case a future version
  re-externalises that data.)
- **`htmldocx`** (**Word `.docx`** export, HTML→docx rendering) relies on
  **`beautifulsoup4`** (`bs4`) — both **pure Python**; `lxml` (native) is
  **already** pulled in by `python-docx` (see ingestion). Lazy imports in
  `markdown_docx` → `hiddenimports += ['htmldocx']` +
  `collect_submodules('bs4')` in the `.spec`.
- **PDF fonts**: PDF rendering uses **Windows system fonts**, registered with
  ReportLab — **no font to bundle**, but the EXE depends on them at runtime
  (always present on a standard Windows target): **Arial**
  (`%SystemRoot%\Fonts\arial*.ttf`) for Latin **and Arabic** (Arabic glyphs +
  contextual shaping via `arabic-reshaper`/`python-bidi`); **Microsoft YaHei**
  (`%SystemRoot%\Fonts\msyh.ttc`, TrueType Collection loaded via
  `subfontIndex`) for **Chinese**. If YaHei is missing, the Chinese PDF
  export raises `EXPORT.NO_CJK_FONT` (MD/HTML/Word remain available). A few
  rare Unicode dashes (U+2010/2011/2012/2015) not rendered by ReportLab+Arial
  are normalised at PDF render time (`markdown_pdf._normalize_for_pdf`). Two
  more **purely-runtime** treatments (nothing to bundle): characters
  **without a glyph** in the active font (decorative emojis) are **stripped**
  from the PDF (`_strip_unrenderable_for_pdf`), and **Chinese prose is
  pre-broken** with `<br/>` (ReportLab only breaks on spaces, absent in CJK;
  `_prewrap_cjk_runs`).

### i18n translations (`.qm`)

The UI is translatable through the native Qt stack (`QTranslator` + `.ts` /
`.qm`; see `src/fahmi2/i18n/`). The source language is **French** — strings
in code are in FR. Other languages are loaded at startup from binary `.qm`
files (compiled from the editable `.ts` sources) bundled with the
application.

- **At build time**: regenerate the `.qm` files (before or after
  `pyinstaller`):
  ```powershell
  .\.venv\Scripts\python.exe scripts\i18n_compile.py
  ```
  The `src/fahmi2/i18n/compiled/` folder is **`.gitignore`** (a derived
  binary artefact) — it **must** be recompiled at each build (the `build.ps1`
  script can be extended to do it automatically).
- **In `packaging/fahmi2.spec` (gitignored)** — add to `datas`:
  ```python
  ("src/fahmi2/i18n/compiled/*.qm", "fahmi2/i18n/compiled"),
  ```
  Without this line, **the packaged app will not ship the translations** and
  will stay in French regardless of the user preference (silent:
  `install_translator` falls back to the source language when the `.qm` is
  missing).
- **At runtime**: `fahmi2.i18n.bundled_translations_dir()` detects packaged
  mode (`sys.frozen` + `sys._MEIPASS`) and resolves
  `<bundle_root>/fahmi2/i18n/compiled/`. In dev, it is resolved via
  `__file__` next to the package.

**Adding a language**:
1. Add the value to `AppLanguage` (`src/fahmi2/i18n/languages.py`) plus its
   native label in `LANGUAGE_LABELS`.
2. `.\.venv\Scripts\python.exe scripts\i18n_extract.py` — generates
   `fahmi2_<code>.ts` (target language) or completes the existing one.
3. Translate the `<translation type="unfinished"></translation>` entries in
   the `.ts` (any text editor or Qt Linguist).
4. `.\.venv\Scripts\python.exe scripts\i18n_compile.py` — produces the `.qm`.
5. Rebuild with PyInstaller: the `.qm` is bundled via `datas`.

### Document ingestion dependencies (pypdf / python-docx)

Text-document ingestion (`infra/ingestion/text_extractor.py`) adds:

- **`pypdf`** (PDF text extraction) is **already** pulled in by `xhtml2pdf`
  (see above) → bundled already, nothing extra to wire.
- **`python-docx`** (the `docx` module, `.docx` extraction) **bundles a
  template** (`docx/templates/default.docx`) loaded at `Document()`
  instantiation → add `collect_data_files('docx')` (or `collect_all('docx')`)
  in the `.spec`, otherwise `.docx` extraction fails in packaged mode.
- `pypdf` and `docx` are imported **lazily** (inside `DefaultTextExtractor`
  functions): if PyInstaller's static analysis misses them, add them to
  `hiddenimports`.

### yt-dlp binary (YouTube ingestion)

YouTube link ingestion (`infra/ingestion/youtube_downloader.py`) calls the
`yt-dlp` **binary** (not an imported pip dependency):

- **At build time**: download `yt-dlp.exe` from the official GitHub release
  (`yt-dlp/yt-dlp`) and copy it **to the bundle root** (same folder as
  `ffmpeg.exe`). See `packaging/fetch-ytdlp.ps1` (dedicated script).
- **At runtime**: `resolve_ytdlp_binary_or_none()` looks, in order, at the
  environment variable **`FAHMI2_YTDLP`** (override), then the bundled
  binary, then the binary installed **next to the Python interpreter**
  (venv), then the system `PATH`.
- **In development**: `pip install yt-dlp` (already in the `dev`
  dependencies) is enough — `yt-dlp.exe` lands in `.venv/Scripts/` and is
  resolved automatically, no env var required.
- **Fragility (important)**: yt-dlp **breaks regularly** when YouTube changes
  its protections. The binary is therefore **replaceable without a rebuild**
  (`FAHMI2_YTDLP` override or replacement of the bundled `yt-dlp.exe`).
  Recommend periodic rebuilds to refresh the bundled version. On failure,
  the `INGESTION.YOUTUBE_DOWNLOAD_FAILED` message asks the user to update
  yt-dlp.
- **Network required**; downloading YouTube content is the **user's
  responsibility** (YouTube ToS).
- yt-dlp downloads the **best audio track** (`-f bestaudio/best`,
  `--no-playlist`); WAV conversion is then performed by the bundled ffmpeg
  via the `MediaIngestor` (yt-dlp therefore does not need a dedicated
  `--ffmpeg-location`).

### Runtime resolution of the bundled ffmpeg

At application startup, `core/config/paths.py` detects `sys.frozen=True` +
`sys._MEIPASS` (PyInstaller signatures) and resolves the bundled binaries
through `resolve_ffmpeg_binary_or_none()` /
`resolve_ffprobe_binary_or_none()`. In development mode, these functions
return `None` and the system PATH is used.

### Pinning ffmpeg

To pin a specific ffmpeg release (instead of the current "essentials"):

1. Change `$downloadUrl` in `packaging/fetch-ffmpeg.ps1` to point to the
   desired version.
2. Delete `vendor/ffmpeg/bin/` locally.
3. Re-run `.\packaging\fetch-ffmpeg.ps1`.
4. Commit (do not commit the binaries, already in `.gitignore`).

### Why no code signing in v1?

Code signing requires a commercial certificate (~€200–500/year). For the
targeted single-user usage, the cost/benefit is not relevant in v1.
SmartScreen displays a warning on the first launch only (click
*"More info"* → *"Run anyway"*).

If distribution broadens to a wider audience, adding a SignTool signature is
trivial to integrate (extra step in `build.ps1`).
