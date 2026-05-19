"""Tests de l'entité VideoExecution."""

from pathlib import Path

from fahmi2.domain.enums import Language, PhaseId, PhaseStatus
from fahmi2.domain.ids import VideoId
from fahmi2.domain.phase import PhaseExecution
from fahmi2.domain.video import VideoExecution


def test_video_execution_minimal() -> None:
    vid = VideoId.new()
    ve = VideoExecution(video_id=vid, source_path=Path("video.mp4"))
    assert ve.video_id is vid
    assert ve.source_path == Path("video.mp4")
    assert ve.detected_language is None
    assert ve.phase_executions == {}


def test_video_execution_with_phases() -> None:
    vid = VideoId.new()
    pe = PhaseExecution(phase_id=PhaseId.STT, status=PhaseStatus.SUCCEEDED)
    ve = VideoExecution(
        video_id=vid,
        source_path=Path("video.mp4"),
        detected_language=Language.FR,
        phase_executions={PhaseId.STT: pe},
    )
    assert ve.detected_language is Language.FR
    assert ve.phase_executions[PhaseId.STT] is pe


def test_video_execution_phase_status_helper() -> None:
    vid = VideoId.new()
    pe = PhaseExecution(phase_id=PhaseId.STT, status=PhaseStatus.SUCCEEDED)
    ve = VideoExecution(
        video_id=vid,
        source_path=Path("video.mp4"),
        phase_executions={PhaseId.STT: pe},
    )
    assert ve.phase_status(PhaseId.STT) is PhaseStatus.SUCCEEDED
    assert ve.phase_status(PhaseId.REFORMULATION) is PhaseStatus.PENDING
