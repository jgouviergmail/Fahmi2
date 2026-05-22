"""Tests de ``DocumentIngestor`` (segment unique, texte préservé)."""

from pathlib import Path

import pytest

from fahmi2.core.errors.exceptions import IngestionError
from fahmi2.domain.enums import Language, SourceKind
from fahmi2.domain.source import InputSource
from fahmi2.infra.audio.ffmpeg_extractor import FFmpegExtractor
from fahmi2.infra.ingestion._fakes import FakeTextExtractor
from fahmi2.infra.ingestion.document_ingestor import DocumentIngestor
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


def test_ingest_document_single_segment_preserves_text(tmp_path: Path) -> None:
    text = "# Titre\n\nParagraphe 1.\n\nParagraphe 2."
    ingestor = DocumentIngestor(FakeTextExtractor(default_text=text))
    transcription = ingestor.ingest(
        InputSource(kind=SourceKind.DOCUMENT, location=str(tmp_path / "c.md")),
        _SOURCE_ID,
        _deps(tmp_path),
        language_hint=Language.FR,
        delete_audio_after=True,
    )
    assert len(transcription.segments) == 1
    assert transcription.segments[0].text == text
    assert transcription.full_text() == text  # structure préservée (pas d'aplatissement)
    assert transcription.detected_language is Language.FR
    assert transcription.duration_seconds == 0.0


def test_ingest_empty_document_raises(tmp_path: Path) -> None:
    ingestor = DocumentIngestor(FakeTextExtractor(default_text="   \n  "))
    with pytest.raises(IngestionError) as exc:
        ingestor.ingest(
            InputSource(kind=SourceKind.DOCUMENT, location=str(tmp_path / "v.txt")),
            _SOURCE_ID,
            _deps(tmp_path),
            language_hint=Language.FR,
            delete_audio_after=True,
        )
    assert exc.value.code == "INGESTION.EMPTY_DOCUMENT"
