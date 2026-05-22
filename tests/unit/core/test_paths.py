"""Tests de la résolution des chemins standards Windows."""

import sys
from pathlib import Path

import pytest

from fahmi2.core.config.paths import (
    AppPaths,
    resolve_bundled_ffmpeg_dir,
    resolve_ffmpeg_binary_or_none,
    resolve_ffprobe_binary_or_none,
    resolve_ytdlp_binary_or_none,
)


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


def test_resolve_bundled_ffmpeg_dir_returns_none_in_dev(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    assert resolve_bundled_ffmpeg_dir() is None
    assert resolve_ffmpeg_binary_or_none() is None
    assert resolve_ffprobe_binary_or_none() is None


def test_resolve_bundled_ffmpeg_dir_returns_path_when_bundled(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    (tmp_path / "ffmpeg.exe").write_bytes(b"x")
    (tmp_path / "ffprobe.exe").write_bytes(b"x")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert resolve_bundled_ffmpeg_dir() == tmp_path
    assert resolve_ffmpeg_binary_or_none() == str(tmp_path / "ffmpeg.exe")
    assert resolve_ffprobe_binary_or_none() == str(tmp_path / "ffprobe.exe")


def test_ytdlp_override_env_takes_precedence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("FAHMI2_YTDLP", "C:/tools/yt-dlp.exe")
    assert resolve_ytdlp_binary_or_none() == "C:/tools/yt-dlp.exe"


def test_ytdlp_none_in_dev(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("FAHMI2_YTDLP", raising=False)
    monkeypatch.setattr(sys, "frozen", False, raising=False)
    assert resolve_ytdlp_binary_or_none() is None


def test_ytdlp_bundled_when_present(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.delenv("FAHMI2_YTDLP", raising=False)
    (tmp_path / "ffmpeg.exe").write_bytes(b"x")
    (tmp_path / "yt-dlp.exe").write_bytes(b"x")
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "_MEIPASS", str(tmp_path), raising=False)
    assert resolve_ytdlp_binary_or_none() == str(tmp_path / "yt-dlp.exe")
