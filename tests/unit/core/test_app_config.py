"""Tests de AppConfig (configuration globale immutable)."""

from pathlib import Path

from fahmi2.core.config.app_config import AppConfig
from fahmi2.core.config.paths import AppPaths


def test_app_config_defaults(tmp_path: Path) -> None:
    paths = AppPaths(appdata=tmp_path / "app", localappdata=tmp_path / "local")
    cfg = AppConfig(paths=paths)
    assert cfg.paths is paths
    assert cfg.ui_log_level_default == "INFO"
    assert cfg.theme == "system"
    assert cfg.last_project_id is None


def test_app_config_can_set_optional_fields(tmp_path: Path) -> None:
    paths = AppPaths(appdata=tmp_path / "app", localappdata=tmp_path / "local")
    cfg = AppConfig(
        paths=paths,
        ui_log_level_default="WARNING",
        theme="dark",
        last_project_id="01HABC",
    )
    assert cfg.ui_log_level_default == "WARNING"
    assert cfg.theme == "dark"
    assert cfg.last_project_id == "01HABC"
