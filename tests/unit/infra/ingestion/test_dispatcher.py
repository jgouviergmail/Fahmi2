"""Tests de ``IngestionDispatcher`` (routage par type + erreur si non géré)."""

from pathlib import Path

import pytest

from fahmi2.core.errors.exceptions import IngestionError
from fahmi2.domain.enums import Language, SourceKind
from fahmi2.domain.source import InputSource
from fahmi2.infra.audio.ffmpeg_extractor import FFmpegExtractor
from fahmi2.infra.ingestion.dispatcher import build_default_ingestion_dispatcher
from fahmi2.infra.ingestion.interface import IngestionDeps
from fahmi2.infra.storage.fs_artifacts import FsArtifactStore
from fahmi2.infra.stt._fakes import FakeSTTProvider

_SOURCE_ID = "01HZX9KQ7N8YV3JD4M2C6B5A0E"


def _deps(tmp_path: Path) -> IngestionDeps:
    return IngestionDeps(
        workspace=tmp_path,
        artifacts=FsArtifactStore(),
        stt_provider=FakeSTTProvider(),
        ffmpeg=FFmpegExtractor(),
    )


def test_default_dispatcher_handles_video_and_audio() -> None:
    dispatcher = build_default_ingestion_dispatcher()
    assert dispatcher.has_ingestor(SourceKind.VIDEO)
    assert dispatcher.has_ingestor(SourceKind.AUDIO)
    assert not dispatcher.has_ingestor(SourceKind.DOCUMENT)
    assert not dispatcher.has_ingestor(SourceKind.YOUTUBE)


def test_unsupported_kind_raises(tmp_path: Path) -> None:
    dispatcher = build_default_ingestion_dispatcher()
    with pytest.raises(IngestionError) as exc:
        dispatcher.ingest(
            InputSource(kind=SourceKind.DOCUMENT, location="a.pdf"),
            _SOURCE_ID,
            _deps(tmp_path),
            language_hint=Language.FR,
            delete_audio_after=True,
        )
    assert exc.value.code == "INGESTION.UNSUPPORTED_SOURCE"
