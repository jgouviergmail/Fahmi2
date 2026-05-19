"""Tests de la résolution des chemins standards Windows."""

from pathlib import Path

import pytest

from fahmi2.core.config.paths import AppPaths


def test_paths_uses_env_appdata(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
    paths = AppPaths.default()
    assert paths.appdata == tmp_path / "Roaming" / "Fahmi2"
    assert paths.localappdata == tmp_path / "Local" / "Fahmi2"


def test_paths_secrets_file(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
    paths = AppPaths.default()
    assert paths.secrets_file == tmp_path / "Roaming" / "Fahmi2" / "secrets.dat"


def test_paths_models_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
    paths = AppPaths.default()
    assert paths.models_dir == tmp_path / "Local" / "Fahmi2" / "models"


def test_paths_projects_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
    paths = AppPaths.default()
    assert paths.projects_dir == tmp_path / "Roaming" / "Fahmi2" / "projects"


def test_paths_prompts_override_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
    paths = AppPaths.default()
    assert paths.prompts_override_dir == tmp_path / "Roaming" / "Fahmi2" / "prompts"


def test_paths_backups_dir(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
    paths = AppPaths.default()
    assert paths.backups_dir == tmp_path / "Roaming" / "Fahmi2" / "backups"


def test_paths_ensure_creates_directories(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
    paths = AppPaths.default()
    paths.ensure_dirs()
    assert paths.appdata.is_dir()
    assert paths.localappdata.is_dir()
    assert paths.projects_dir.is_dir()
    assert paths.prompts_override_dir.is_dir()
    assert paths.models_dir.is_dir()
    assert paths.backups_dir.is_dir()


def test_paths_missing_appdata_falls_back(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("APPDATA", raising=False)
    monkeypatch.setenv("USERPROFILE", str(tmp_path / "user"))
    paths = AppPaths.default()
    assert paths.appdata == tmp_path / "user" / "AppData" / "Roaming" / "Fahmi2"
