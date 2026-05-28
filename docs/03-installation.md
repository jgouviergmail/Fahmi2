# Fahmi2 — Installation guide

## 1. End-user installation

### 1.1 Hardware requirements

- **Windows 11** (Windows 10 minimum, 64-bit).
- **8 GB of RAM** minimum recommended.
- **3 GB of free disk space** (application + Whisper model cache if used
  locally).
- **NVIDIA CUDA-compatible GPU** **only** if you want to use local
  transcription (faster-whisper). **Optional** otherwise: OpenAI cloud
  transcription works on any machine.

### 1.2 Installation procedure

1. **Download** the supplied `Fahmi2-<version>-win64.zip` file.
2. **Unzip** to a folder of your choice (e.g. `C:\Apps\Fahmi2\`, or directly
   on the desktop).
   - Windows: right-click the `.zip` → *"Extract all…"* → choose the
     destination folder → *"Extract"*.
3. **Open** the extracted folder and **double-click `Fahmi2.exe`**.
4. **First launch**:
   - Windows shows a blue **SmartScreen** screen saying *"Windows protected
     your PC"* ("Unknown publisher").
   - Click **"More info"** then **"Run anyway"**.
   - This warning will not appear on subsequent launches.

That's it. No system install, no dependency to install, no admin rights
required. ffmpeg is included in the archive.

### 1.3 Create a desktop shortcut (optional)

Right-click `Fahmi2.exe` → *"Send to"* → *"Desktop (create shortcut)"*.

### 1.4 User data

On first launch, the application automatically creates:

| Path | Content |
|------|---------|
| `%APPDATA%\Fahmi2\` | Projects, encrypted API keys, prompt overrides, SQLite database, logs, UI preferences (`ui_prefs.json`) including theme + language |
| `%LOCALAPPDATA%\Fahmi2\` | Downloaded model cache (local Whisper only) |

This data **survives application upgrades**.

### 1.5 Upgrading

1. Download the new `.zip` version.
2. **Close Fahmi2** if the application is open.
3. **Replace the application folder** with the unzipped contents of the new
   `.zip`. You can delete the previous folder entirely first and then unzip
   — no data lives there.
4. Relaunch `Fahmi2.exe`.

Projects, settings, and API keys are **automatically preserved** in
`%APPDATA%\Fahmi2\`. If a schema migration is required, it is applied
automatically with a prior backup.

### 1.6 Uninstall

1. Delete the folder where you unzipped Fahmi2.
2. **If you also want to wipe your data** (projects, API keys, …):
   - Delete `%APPDATA%\Fahmi2\` (paste it into the Windows Explorer address
     bar).
   - Delete `%LOCALAPPDATA%\Fahmi2\`.

No trace is left elsewhere on the system.

## 2. Developer installation (build from source)

### 2.1 Software prerequisites

- **Python 3.11 or 3.12** (not 3.13 — see
  [pyproject.toml](../pyproject.toml)).
  - Download: <https://www.python.org/downloads/>
  - Tick *"Add Python to PATH"* during the install.
- **Git**: <https://git-scm.com/downloads>
- **PowerShell 7+** recommended (PowerShell 5.1 also works).
- **ffmpeg** in the PATH **for tests only** (packaging downloads its own
  copy). On Windows: `winget install --id=Gyan.FFmpeg -e` or
  `choco install ffmpeg`.

### 2.2 Clone and prepare the venv

```powershell
git clone <repo-url> Fahmi2
cd Fahmi2

# Create a venv with Python 3.12 explicitly (recommended)
py -3.12 -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install the project in editable mode with the dev dependencies
python -m pip install --upgrade pip
pip install -e ".[dev]"
pip install pyinstaller>=6.10

# Install pre-commit hooks
pre-commit install
```

### 2.3 Compile UI translations

The English `.qm` is gitignored and must be regenerated before running the
app or running the i18n smoke tests:

```powershell
.\.venv\Scripts\python.exe scripts\i18n_compile.py
```

### 2.4 Verify the install

```powershell
pytest -q
ruff check .
mypy src tests
```

All three must pass without error. See
[06-procedures-techniques.md](06-procedures-techniques.md) for each
command's details.

### 2.5 Run the application in dev mode

```powershell
python -m fahmi2.ui.app_main
```

## 3. Building the distribution archive

See [packaging/README.md](../packaging/README.md) for the details.

Quick procedure from the activated venv:

```powershell
# One-shot: downloads ffmpeg + builds + zips
.\packaging\build.ps1
.\packaging\make-portable-zip.ps1
```

The final `.zip` appears at `dist/Fahmi2-<version>-win64.zip`.

## 4. Install troubleshooting

### 4.1 "This app cannot run on your PC"

- Check that you are on **Windows 10/11 64-bit** (32-bit is not supported).
- Try **running as administrator** (right-click `Fahmi2.exe` → *"Run as
  administrator"*). Note: no app function actually requires admin rights,
  this is a diagnostic test.

### 4.2 SmartScreen comes back on every launch

This usually happens when the extraction folder is on a network location or
a removable volume with a persistent "Mark-of-the-Web" attribute. Fix: move
the folder to a local location (e.g. `C:\Apps\Fahmi2\`).

### 4.3 "Windows protected your PC: Editor unknown"

Normal behaviour on the first launch. Click *"More info"* then *"Run
anyway"*. This happens because the application is not signed with a
commercial certificate.

### 4.4 "The program stopped working"

Open the log file `%APPDATA%\Fahmi2\projects\<id>\events.jsonl` for the
details. If the issue persists, attach this file to the incident report.

### 4.5 Antivirus blocks `Fahmi2.exe` or its dependencies

Rare with PyInstaller `--onedir` (unlike `--onefile`, which often triggers
false positives). If it happens:

- Add an exception for the install folder in your antivirus.
- Verify the downloaded `.zip`'s SHA-256 hash against the published one to
  rule out any corruption.
