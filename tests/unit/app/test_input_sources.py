"""Tests de ``build_input_sources`` (scan vidéo + audio, tri naturel)."""

from pathlib import Path
from typing import Any

import pytest

from fahmi2.app.input_sources import build_input_sources, reconcile_source_order
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


def test_youtube_urls_appended_after_files(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    (tmp_path / "01-a.mp4").write_bytes(b"x")
    settings = make_generation_settings(
        input_folder=tmp_path, youtube_urls=("https://youtu.be/abc",)
    )
    sources = build_input_sources(settings)
    assert sources[0].source.kind is SourceKind.VIDEO
    assert sources[-1].source.kind is SourceKind.YOUTUBE
    assert sources[-1].source.location == "https://youtu.be/abc"


def test_youtube_only_with_missing_folder_is_valid(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    settings = make_generation_settings(
        input_folder=tmp_path / "missing", youtube_urls=("https://youtu.be/abc",)
    )
    sources = build_input_sources(settings)
    assert len(sources) == 1
    assert sources[0].source.kind is SourceKind.YOUTUBE


def test_no_files_no_urls_raises_no_input_source(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    settings = make_generation_settings(input_folder=tmp_path)
    with pytest.raises(ConfigError) as exc:
        build_input_sources(settings)
    assert exc.value.code == "CONFIG.NO_INPUT_SOURCE"


def test_reconcile_orders_and_appends_new() -> None:
    included, excluded = reconcile_source_order(
        ["a.mp4", "b.mp4", "c.mp4"], source_order=("c.mp4", "a.mp4"), excluded=()
    )
    assert included == ["c.mp4", "a.mp4", "b.mp4"]  # nouvelles (b) en fin
    assert excluded == []


def test_reconcile_filters_excluded_and_ignores_stale() -> None:
    included, excluded = reconcile_source_order(
        ["a.mp4", "b.mp4"],
        source_order=("a.mp4",),
        excluded=("b.mp4", "obsolete.mp4"),
    )
    assert included == ["a.mp4"]
    assert excluded == ["b.mp4"]  # obsolete.mp4 (absente) ignorée


def test_reconcile_empty_order_keeps_available_order() -> None:
    included, excluded = reconcile_source_order(
        ["a.mp4", "b.mp4"], source_order=(), excluded=()
    )
    assert included == ["a.mp4", "b.mp4"]
    assert excluded == []


def test_build_respects_source_order_and_exclusion(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    (tmp_path / "a.mp4").write_bytes(b"x")
    (tmp_path / "b.mp4").write_bytes(b"x")
    (tmp_path / "c.mp4").write_bytes(b"x")
    settings = make_generation_settings(
        input_folder=tmp_path,
        source_order=("c.mp4", "a.mp4"),
        excluded_sources=("b.mp4",),
    )
    sources = build_input_sources(settings)
    assert [s.source.order_key() for s in sources] == ["c.mp4", "a.mp4"]


def test_build_raises_when_all_excluded(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    (tmp_path / "a.mp4").write_bytes(b"x")
    settings = make_generation_settings(
        input_folder=tmp_path, excluded_sources=("a.mp4",)
    )
    with pytest.raises(ConfigError) as exc:
        build_input_sources(settings)
    assert exc.value.code == "CONFIG.NO_INPUT_SOURCE"
