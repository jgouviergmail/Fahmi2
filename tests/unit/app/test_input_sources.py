"""Tests de ``build_input_sources`` (scan vidéo + audio, tri naturel)."""

from pathlib import Path
from typing import Any

import pytest

from fahmi2.app.input_sources import build_input_sources
from fahmi2.core.errors.exceptions import ConfigError, StorageError
from fahmi2.domain.enums import SourceKind


def test_scans_video_and_audio_sorted_naturally(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    (tmp_path / "cours - 02 - suite.mp3").write_bytes(b"x")
    (tmp_path / "cours - 01 - intro.mp4").write_bytes(b"x")
    (tmp_path / "notes.zip").write_bytes(b"x")  # ignoré (non supporté)
    settings = make_generation_settings(input_folder=tmp_path)

    sources = build_input_sources(settings)

    assert [s.source.order_key() for s in sources] == [
        "cours - 01 - intro.mp4",
        "cours - 02 - suite.mp3",
    ]
    assert sources[0].source.kind is SourceKind.VIDEO
    assert sources[1].source.kind is SourceKind.AUDIO


def test_empty_folder_raises_no_input_source(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    (tmp_path / "ignore.zip").write_bytes(b"x")
    settings = make_generation_settings(input_folder=tmp_path)
    with pytest.raises(ConfigError) as exc:
        build_input_sources(settings)
    assert exc.value.code == "CONFIG.NO_INPUT_SOURCE"


def test_missing_folder_raises_storage_error(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    settings = make_generation_settings(input_folder=tmp_path / "missing")
    with pytest.raises(StorageError) as exc:
        build_input_sources(settings)
    assert exc.value.code == "STORAGE.READ_DENIED"
