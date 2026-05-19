"""Tests du store d'artefacts FS avec writes atomiques."""

import json
import threading
from pathlib import Path

import pytest

from fahmi2.infra.storage.fs_artifacts import FsArtifactStore


def test_write_text_atomic_creates_file(tmp_path: Path) -> None:
    store = FsArtifactStore()
    path = tmp_path / "out.txt"
    store.write_text_atomic(path, "hello")
    assert path.read_text(encoding="utf-8") == "hello"


def test_write_text_atomic_creates_parent_dir(tmp_path: Path) -> None:
    store = FsArtifactStore()
    path = tmp_path / "sub" / "deep" / "out.txt"
    store.write_text_atomic(path, "hello")
    assert path.read_text(encoding="utf-8") == "hello"


def test_write_text_atomic_overwrites_existing(tmp_path: Path) -> None:
    store = FsArtifactStore()
    path = tmp_path / "out.txt"
    path.write_text("old", encoding="utf-8")
    store.write_text_atomic(path, "new")
    assert path.read_text(encoding="utf-8") == "new"


def test_write_text_atomic_handles_utf8(tmp_path: Path) -> None:
    store = FsArtifactStore()
    path = tmp_path / "out.txt"
    store.write_text_atomic(path, "café — éàù")
    assert path.read_text(encoding="utf-8") == "café — éàù"


def test_write_bytes_atomic_creates_file(tmp_path: Path) -> None:
    store = FsArtifactStore()
    path = tmp_path / "out.bin"
    store.write_bytes_atomic(path, b"\x00\x01\x02hello")
    assert path.read_bytes() == b"\x00\x01\x02hello"


def test_write_json_atomic_writes_utf8_indented(tmp_path: Path) -> None:
    store = FsArtifactStore()
    path = tmp_path / "out.json"
    store.write_json_atomic(path, {"name": "café", "n": 42})
    content = path.read_text(encoding="utf-8")
    assert "café" in content
    parsed = json.loads(content)
    assert parsed == {"name": "café", "n": 42}
    # Indentation présente
    assert "\n" in content


def test_write_creates_no_residual_tmp_files(tmp_path: Path) -> None:
    store = FsArtifactStore()
    path = tmp_path / "out.txt"
    store.write_text_atomic(path, "hello")
    tmp_files = [p for p in tmp_path.iterdir() if p.suffix == ".tmp"]
    assert tmp_files == []


def test_write_text_failure_keeps_original(tmp_path: Path) -> None:
    store = FsArtifactStore()
    path = tmp_path / "out.txt"
    path.write_text("original", encoding="utf-8")

    # Provoquer une erreur en passant un dossier comme cible (déjà existant en file)
    sub = tmp_path / "blocking"
    sub.mkdir()
    target = sub  # rename vers un dossier non vide va lever
    with pytest.raises(OSError):
        store.write_text_atomic(target, "new")

    # Le fichier original reste intact
    assert path.read_text(encoding="utf-8") == "original"


def test_concurrent_writes_to_different_files(tmp_path: Path) -> None:
    store = FsArtifactStore()
    n_threads = 8

    def _worker(i: int) -> None:
        store.write_text_atomic(tmp_path / f"file_{i}.txt", f"content_{i}")

    threads = [threading.Thread(target=_worker, args=(i,)) for i in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    for i in range(n_threads):
        assert (tmp_path / f"file_{i}.txt").read_text(encoding="utf-8") == f"content_{i}"
