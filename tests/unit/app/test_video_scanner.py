"""Tests du video scanner."""

from pathlib import Path

import pytest

from fahmi2.app.video_scanner import (
    scan_input_folder,
    supported_extensions,
)
from fahmi2.core.errors.exceptions import ConfigError, StorageError


def test_supported_extensions_set() -> None:
    exts = supported_extensions()
    assert ".mp4" in exts
    assert ".mkv" in exts


def test_scan_returns_videos_sorted_by_name(tmp_path: Path) -> None:
    (tmp_path / "b_second.mp4").write_bytes(b"x")
    (tmp_path / "a_first.mp4").write_bytes(b"x")
    (tmp_path / "c_third.mkv").write_bytes(b"x")
    result = scan_input_folder(tmp_path)
    names = [v.source_path.name for v in result]
    assert names == ["a_first.mp4", "b_second.mp4", "c_third.mkv"]


def test_scan_ignores_unsupported_extensions(tmp_path: Path) -> None:
    (tmp_path / "video.mp4").write_bytes(b"x")
    (tmp_path / "notes.txt").write_bytes(b"x")
    (tmp_path / "image.png").write_bytes(b"x")
    result = scan_input_folder(tmp_path)
    assert len(result) == 1
    assert result[0].source_path.name == "video.mp4"


def test_scan_raises_when_folder_missing(tmp_path: Path) -> None:
    with pytest.raises(StorageError) as exc_info:
        scan_input_folder(tmp_path / "missing")
    assert exc_info.value.code == "STORAGE.READ_DENIED"


def test_scan_raises_when_no_video(tmp_path: Path) -> None:
    (tmp_path / "notes.txt").write_bytes(b"x")
    with pytest.raises(ConfigError) as exc_info:
        scan_input_folder(tmp_path)
    assert exc_info.value.code == "CONFIG.INPUT_FOLDER_EMPTY"
