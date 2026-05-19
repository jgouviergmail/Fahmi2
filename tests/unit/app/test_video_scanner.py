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


# --- Tri naturel ----------------------------------------------------------


def test_scan_natural_sort_numeric_prefix(tmp_path: Path) -> None:
    """Reg : 10 doit suivre 2, pas le contraire."""
    for name in ("1.mp4", "2.mp4", "10.mp4", "11.mp4"):
        (tmp_path / name).write_bytes(b"x")
    result = scan_input_folder(tmp_path)
    assert [v.source_path.name for v in result] == [
        "1.mp4",
        "2.mp4",
        "10.mp4",
        "11.mp4",
    ]


def test_scan_natural_sort_complex_prefix(tmp_path: Path) -> None:
    """Reg : 'V.1 - 1 - X' vs 'V.1 - 10 - X' doivent etre tries par 1 < 10."""
    files = [
        "V.1 - 1 - A quoi peut servir.mp4",
        "V.1 - 10 - Retour sur le compte de Resultat.mp4",
        "V.1 - 11 - Le Resultat Net.mp4",
        "V.1 - 12 - Le tableau de Flux.mp4",
        "V.1 - 2 - La fiabilite.mp4",
        "V.1 - 3 - Il n_y a pas.mp4",
        "V.1 - 9 - Retour sur le Bilan.mp4",
    ]
    for name in files:
        (tmp_path / name).write_bytes(b"x")
    result = scan_input_folder(tmp_path)
    extracted_numbers = []
    for v in result:
        # Recupere le numero de chaque fichier en se basant sur le pattern V.1 - N
        token = v.source_path.stem.split(" - ")[1]
        extracted_numbers.append(int(token))
    assert extracted_numbers == [1, 2, 3, 9, 10, 11, 12]


def test_scan_natural_sort_roman_prefix(tmp_path: Path) -> None:
    """Reg : 'V.i - 01' / 'V.i - 02' doivent etre tries dans l'ordre."""
    (tmp_path / "V.i - 02 - Second.mp4").write_bytes(b"x")
    (tmp_path / "V.i - 01 - Premier.mp4").write_bytes(b"x")
    (tmp_path / "V.i - 10 - Dixieme.mp4").write_bytes(b"x")
    result = scan_input_folder(tmp_path)
    assert [v.source_path.name for v in result] == [
        "V.i - 01 - Premier.mp4",
        "V.i - 02 - Second.mp4",
        "V.i - 10 - Dixieme.mp4",
    ]


def test_scan_natural_sort_simple_doc_prefix(tmp_path: Path) -> None:
    """Reg : 'doc 1 XXX', 'doc 10 XXX', 'doc 2 XXX' -> 1, 2, 10."""
    (tmp_path / "doc 1 intro.mp4").write_bytes(b"x")
    (tmp_path / "doc 10 conclusion.mp4").write_bytes(b"x")
    (tmp_path / "doc 2 partie A.mp4").write_bytes(b"x")
    result = scan_input_folder(tmp_path)
    assert [v.source_path.name for v in result] == [
        "doc 1 intro.mp4",
        "doc 2 partie A.mp4",
        "doc 10 conclusion.mp4",
    ]


def test_scan_natural_sort_fallback_alphabetical(tmp_path: Path) -> None:
    """Sans prefixe numerique, les fichiers tombent en fin d'ordre,
    tries alphabetiquement entre eux."""
    (tmp_path / "intro.mp4").write_bytes(b"x")
    (tmp_path / "1 - debut.mp4").write_bytes(b"x")
    (tmp_path / "annexe.mp4").write_bytes(b"x")
    (tmp_path / "2 - milieu.mp4").write_bytes(b"x")
    result = scan_input_folder(tmp_path)
    assert [v.source_path.name for v in result] == [
        "1 - debut.mp4",
        "2 - milieu.mp4",
        "annexe.mp4",
        "intro.mp4",
    ]
