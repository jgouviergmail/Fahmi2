# Fahmi2

Local desktop application that transforms pedagogical video lectures (MP4, FR/EN)
into structured Markdown documents with a glossary and a consolidated output.

See [docs/superpowers/specs/](docs/superpowers/specs/) for the design documentation
and [docs/superpowers/plans/](docs/superpowers/plans/) for the implementation plans.

## Development setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e ".[dev]"
pre-commit install
pytest
```

## Status

In development. Targeted v1 features:

- Pipeline of 7 LLM phases + STT, with checkpointing and resume.
- Two STT providers: `faster-whisper-large-v3-turbo` (local, GPU NVIDIA required) and OpenAI cloud.
- DeepSeek v4 (flash and pro) for LLM phases.
- FR and EN outputs, four style presets, per-phase configuration.
- Cost estimation, budget ceiling, project history, prompt overrides.
- Portable Windows `.zip` distribution (no installer, no code signing required).
