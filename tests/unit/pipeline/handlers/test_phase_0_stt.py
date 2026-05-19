"""Tests du handler Phase 0 STT."""

import json
import subprocess
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from fahmi2.core.errors.exceptions import FFmpegError
from fahmi2.core.errors.severity import Severity
from fahmi2.core.retrieval.interface import PassthroughRetriever
from fahmi2.domain.enums import Language, PhaseStatus, RunStatus
from fahmi2.domain.ids import ProjectId, RunId, VideoId
from fahmi2.domain.run import Run
from fahmi2.domain.video import VideoExecution
from fahmi2.infra.audio.ffmpeg_extractor import AudioInfo, FFmpegExtractor
from fahmi2.infra.llm._fakes import FakeLLMProvider
from fahmi2.infra.storage.fs_artifacts import FsArtifactStore
from fahmi2.infra.storage.sqlite_state import SqliteState
from fahmi2.infra.stt._fakes import FakeSTTProvider
from fahmi2.infra.stt.interface import Transcription, TranscriptionSegment
from fahmi2.pipeline.event_bus import EventBus
from fahmi2.pipeline.handlers.phase_0_stt import Phase0SttHandler
from fahmi2.pipeline.pause_token import PauseToken
from fahmi2.pipeline.phase_handler import PhaseContext


@pytest.fixture(scope="session")
def short_mp4_with_audio(tmp_path_factory: pytest.TempPathFactory) -> Path:
    out = tmp_path_factory.mktemp("phase0_media") / "short.mp4"
    subprocess.run(
        [
            "ffmpeg",
            "-y",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440:duration=1",
            "-f",
            "lavfi",
            "-i",
            "testsrc=duration=1:size=64x48:rate=10",
            "-c:a",
            "aac",
            "-c:v",
            "libx264",
            "-shortest",
            "-loglevel",
            "error",
            str(out),
        ],
        check=True,
        capture_output=True,
    )
    return out


def _make_context(
    tmp_path: Path,
    make_settings: Any,
    stt: FakeSTTProvider,
    video_source: Path,
    *,
    delete_audio_after_stt: bool = True,
) -> tuple[PhaseContext, VideoExecution]:
    settings = make_settings(
        workspace_folder=tmp_path / "workspace",
        delete_audio_after_stt=delete_audio_after_stt,
    )
    project_id = ProjectId.new()
    run = Run(
        id=RunId.new(),
        project_id=project_id,
        started_at=datetime.now(tz=UTC),
        status=RunStatus.RUNNING,
        settings_snapshot=settings,
    )
    video = VideoExecution(video_id=VideoId.new(), source_path=video_source)
    state = SqliteState(tmp_path / "state.db")
    ctx = PhaseContext(
        run=run,
        settings=settings,
        workspace=tmp_path / "workspace",
        output_dir=tmp_path / "output",
        state=state,
        artifacts=FsArtifactStore(),
        stt_provider=stt,
        llm_provider=FakeLLMProvider(),
        ffmpeg=FFmpegExtractor(),
        retriever=PassthroughRetriever(),
        pause_token=PauseToken(),
        event_bus=EventBus(),
    )
    return ctx, video


def _scripted_transcription() -> Transcription:
    return Transcription(
        segments=(
            TranscriptionSegment(start_seconds=0.0, end_seconds=1.0, text="hello world"),
        ),
        detected_language=Language.FR,
        duration_seconds=1.0,
    )


def test_handler_metadata() -> None:
    handler = Phase0SttHandler()
    assert handler.phase_id.value == "phase_0_stt"
    assert handler.is_per_video is True


def test_execute_writes_transcription_json(
    tmp_path: Path, make_settings: Any, short_mp4_with_audio: Path
) -> None:
    stt = FakeSTTProvider(scenarios={
        short_mp4_with_audio.stem + ".wav": _scripted_transcription(),
    })
    ctx, video = _make_context(tmp_path, make_settings, stt, short_mp4_with_audio)
    # On force le video_id à mapper sur le nom de fichier WAV pour le scénario
    # — en réalité on utilise le fake générique qui sert toutes les requêtes.
    handler = Phase0SttHandler()
    result = handler.execute(ctx, video=video)

    assert result.status is PhaseStatus.SUCCEEDED
    assert result.artifact_path is not None
    assert result.artifact_path.exists()
    payload = json.loads(result.artifact_path.read_text(encoding="utf-8"))
    assert payload["detected_language"] == "fr"
    assert payload["segments"]


def test_execute_deletes_audio_when_enabled(
    tmp_path: Path, make_settings: Any, short_mp4_with_audio: Path
) -> None:
    stt = FakeSTTProvider()
    ctx, video = _make_context(
        tmp_path, make_settings, stt, short_mp4_with_audio, delete_audio_after_stt=True
    )
    handler = Phase0SttHandler()
    handler.execute(ctx, video=video)
    audio_files = list((tmp_path / "workspace" / "audio").glob("*.wav"))
    assert audio_files == []


def test_execute_keeps_audio_when_disabled(
    tmp_path: Path, make_settings: Any, short_mp4_with_audio: Path
) -> None:
    stt = FakeSTTProvider()
    ctx, video = _make_context(
        tmp_path,
        make_settings,
        stt,
        short_mp4_with_audio,
        delete_audio_after_stt=False,
    )
    handler = Phase0SttHandler()
    handler.execute(ctx, video=video)
    audio_files = list((tmp_path / "workspace" / "audio").glob("*.wav"))
    assert len(audio_files) == 1


def test_execute_raises_when_video_is_none(
    tmp_path: Path, make_settings: Any, short_mp4_with_audio: Path
) -> None:
    stt = FakeSTTProvider()
    ctx, _ = _make_context(tmp_path, make_settings, stt, short_mp4_with_audio)
    handler = Phase0SttHandler()
    with pytest.raises(ValueError, match="VideoExecution"):
        handler.execute(ctx, video=None)


def test_execute_propagates_ffmpeg_errors(
    tmp_path: Path, make_settings: Any
) -> None:
    # On utilise un FFmpegExtractor avec un binaire inexistant.
    settings = make_settings(workspace_folder=tmp_path / "workspace")
    run = Run(
        id=RunId.new(),
        project_id=ProjectId.new(),
        started_at=datetime.now(tz=UTC),
        status=RunStatus.RUNNING,
        settings_snapshot=settings,
    )
    bad_extractor = FFmpegExtractor(ffmpeg_binary="ffmpeg-does-not-exist")
    state = SqliteState(tmp_path / "state.db")
    video = VideoExecution(video_id=VideoId.new(), source_path=tmp_path / "missing.mp4")
    ctx = PhaseContext(
        run=run,
        settings=settings,
        workspace=tmp_path / "workspace",
        output_dir=tmp_path / "output",
        state=state,
        artifacts=FsArtifactStore(),
        stt_provider=FakeSTTProvider(),
        llm_provider=FakeLLMProvider(),
        ffmpeg=bad_extractor,
        retriever=PassthroughRetriever(),
        pause_token=PauseToken(),
        event_bus=EventBus(),
    )
    handler = Phase0SttHandler()
    with pytest.raises(FFmpegError):
        handler.execute(ctx, video=video)


def test_execute_reports_severity_on_failure(
    tmp_path: Path, make_settings: Any
) -> None:
    settings = make_settings(workspace_folder=tmp_path / "workspace")
    state = SqliteState(tmp_path / "state.db")
    run = Run(
        id=RunId.new(),
        project_id=ProjectId.new(),
        started_at=datetime.now(tz=UTC),
        status=RunStatus.RUNNING,
        settings_snapshot=settings,
    )
    video = VideoExecution(video_id=VideoId.new(), source_path=tmp_path / "missing.mp4")
    ctx = PhaseContext(
        run=run,
        settings=settings,
        workspace=tmp_path / "workspace",
        output_dir=tmp_path / "output",
        state=state,
        artifacts=FsArtifactStore(),
        stt_provider=FakeSTTProvider(),
        llm_provider=FakeLLMProvider(),
        ffmpeg=FFmpegExtractor(),
        retriever=PassthroughRetriever(),
        pause_token=PauseToken(),
        event_bus=EventBus(),
    )
    handler = Phase0SttHandler()
    with pytest.raises(FFmpegError) as exc_info:
        handler.execute(ctx, video=video)
    assert exc_info.value.severity is Severity.ERROR


def test_mocked_full_path(tmp_path: Path, make_settings: Any) -> None:
    # Test sans dépendre réellement de ffmpeg : on mock le FFmpegExtractor
    # pour vérifier que la chaîne d'écriture fonctionne avec un STT scripté.
    settings = make_settings(workspace_folder=tmp_path / "workspace")
    run = Run(
        id=RunId.new(),
        project_id=ProjectId.new(),
        started_at=datetime.now(tz=UTC),
        status=RunStatus.RUNNING,
        settings_snapshot=settings,
    )
    state = SqliteState(tmp_path / "state.db")
    video = VideoExecution(video_id=VideoId.new(), source_path=tmp_path / "v.mp4")

    fake_ffmpeg = MagicMock()
    fake_ffmpeg.extract.return_value = AudioInfo(
        sample_rate_hz=16_000, channels=1, duration_seconds=10.0
    )
    fake_stt = FakeSTTProvider(default_transcription=_scripted_transcription())

    ctx = PhaseContext(
        run=run,
        settings=settings,
        workspace=tmp_path / "workspace",
        output_dir=tmp_path / "output",
        state=state,
        artifacts=FsArtifactStore(),
        stt_provider=fake_stt,
        llm_provider=FakeLLMProvider(),
        ffmpeg=fake_ffmpeg,
        retriever=PassthroughRetriever(),
        pause_token=PauseToken(),
        event_bus=EventBus(),
    )
    handler = Phase0SttHandler()
    result = handler.execute(ctx, video=video)
    assert result.status is PhaseStatus.SUCCEEDED
    assert result.artifact_path is not None
    assert result.cost_usd == 0.0
