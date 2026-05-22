"""Tests de ``YtDlpDownloader`` (mapping d'erreur ; pas de réseau)."""

import subprocess
from pathlib import Path

import pytest

from fahmi2.core.errors.exceptions import IngestionError
from fahmi2.infra.ingestion.youtube_downloader import YtDlpDownloader

_MISSING_BINARY = "ytdlp-inexistant-xyz"


def test_download_missing_binary_raises_not_found(tmp_path: Path) -> None:
    downloader = YtDlpDownloader(ytdlp_binary=_MISSING_BINARY)
    with pytest.raises(IngestionError) as exc:
        downloader.download_audio("https://youtu.be/x", tmp_path, "01H")
    assert exc.value.code == "INGESTION.YTDLP_NOT_FOUND"


def test_probe_duration_missing_binary_returns_zero(tmp_path: Path) -> None:
    downloader = YtDlpDownloader(ytdlp_binary=_MISSING_BINARY)
    assert downloader.probe_duration("https://youtu.be/x") == 0.0


def test_download_timeout_raises_download_failed(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    def _raise_timeout(*_args: object, **_kwargs: object) -> None:
        raise subprocess.TimeoutExpired(cmd="yt-dlp", timeout=1.0)

    monkeypatch.setattr(subprocess, "run", _raise_timeout)
    downloader = YtDlpDownloader(ytdlp_binary="yt-dlp")
    with pytest.raises(IngestionError) as exc:
        downloader.download_audio("https://youtu.be/x", tmp_path, "01H")
    assert exc.value.code == "INGESTION.YOUTUBE_DOWNLOAD_FAILED"


def test_probe_duration_timeout_returns_zero(monkeypatch: pytest.MonkeyPatch) -> None:
    def _raise_timeout(*_args: object, **_kwargs: object) -> None:
        raise subprocess.TimeoutExpired(cmd="yt-dlp", timeout=1.0)

    monkeypatch.setattr(subprocess, "run", _raise_timeout)
    downloader = YtDlpDownloader(ytdlp_binary="yt-dlp")
    assert downloader.probe_duration("https://youtu.be/x") == 0.0


def test_download_ignores_partial_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Un résidu de téléchargement partiel (``.part``) est ignoré au profit du WAV/m4a."""

    def _fake_run(
        cmd: list[str], **_kwargs: object
    ) -> subprocess.CompletedProcess[bytes]:
        # Simule yt-dlp : laisse un .part résiduel + produit le fichier final.
        (tmp_path / "01H.part").write_bytes(b"partial")
        (tmp_path / "01H.m4a").write_bytes(b"audio")
        return subprocess.CompletedProcess(cmd, 0, b"", b"")

    monkeypatch.setattr(subprocess, "run", _fake_run)
    downloader = YtDlpDownloader(ytdlp_binary="yt-dlp")
    out = downloader.download_audio("https://youtu.be/x", tmp_path, "01H")
    assert out == tmp_path / "01H.m4a"
