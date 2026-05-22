"""Tests de la classification des sources fichier par extension."""

from pathlib import Path

import pytest

from fahmi2.domain.enums import SourceKind
from fahmi2.infra.ingestion.classify import classify_file, supported_file_extensions


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("a.mp4", SourceKind.VIDEO),
        ("a.MKV", SourceKind.VIDEO),
        ("a.wav", SourceKind.AUDIO),
        ("a.mp3", SourceKind.AUDIO),
        ("a.m4a", SourceKind.AUDIO),
        ("a.txt", None),  # document : pas encore supporté au Lot 1B
        ("a.pdf", None),
        ("a.zip", None),
    ],
)
def test_classify_file(name: str, expected: SourceKind | None) -> None:
    assert classify_file(Path(name)) == expected


def test_supported_extensions_contains_audio_and_video() -> None:
    exts = supported_file_extensions()
    assert ".mp4" in exts
    assert ".mp3" in exts
    assert ".txt" not in exts  # ajouté au Lot 2 (documents)
