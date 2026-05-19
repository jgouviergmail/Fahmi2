"""Tests du handler Phase 2 — glossary reconciliation."""

import json
from pathlib import Path
from typing import Any

import pytest

from fahmi2.core.errors.exceptions import StorageError
from fahmi2.domain.enums import PhaseStatus
from fahmi2.domain.ids import VideoId
from fahmi2.domain.video import VideoExecution
from fahmi2.infra.llm.interface import LLMResponse
from fahmi2.pipeline.handlers.phase_2_glossary_reconciliation import (
    Phase2GlossaryReconciliationHandler,
)
from tests.unit.pipeline.handlers._helpers import build_phase_context


def _write_candidates(workspace: Path, video_id: str, payload: dict[str, Any]) -> Path:
    path = workspace / "candidates" / f"{video_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _llm_response(content: str) -> LLMResponse:
    return LLMResponse(
        content=content,
        thinking_content=None,
        prompt_tokens=500,
        completion_tokens=200,
        cached_prompt_tokens=0,
        cost_usd=0.0025,
    )


def test_handler_metadata() -> None:
    handler = Phase2GlossaryReconciliationHandler()
    assert handler.phase_id.value == "phase_2_glossary_reconciliation"
    assert handler.is_per_video is False


def test_execute_aggregates_and_writes_master(tmp_path: Path, make_settings: Any) -> None:
    videos = tuple(
        VideoExecution(video_id=VideoId.new(), source_path=tmp_path / f"v{i}.mp4")
        for i in range(2)
    )
    master_payload = {
        "terms": [
            {
                "term": "PIB",
                "definition": "produit intérieur brut",
                "aliases": [],
                "sources": [v.video_id.value for v in videos],
            }
        ]
    }
    ctx, _ = build_phase_context(
        tmp_path,
        make_settings,
        llm_response=_llm_response(json.dumps(master_payload)),
        videos=videos,
    )
    for v in videos:
        _write_candidates(
            ctx.workspace,
            v.video_id.value,
            {"terms": [{"term": "PIB", "definition": "d"}]},
        )

    handler = Phase2GlossaryReconciliationHandler()
    result = handler.execute(ctx, video=None)
    assert result.status is PhaseStatus.SUCCEEDED
    assert result.artifact_path is not None
    written = json.loads(result.artifact_path.read_text(encoding="utf-8"))
    assert written == master_payload


def test_execute_raises_when_video_provided(
    tmp_path: Path, make_settings: Any
) -> None:
    video = VideoExecution(video_id=VideoId.new(), source_path=tmp_path / "v.mp4")
    ctx, _ = build_phase_context(tmp_path, make_settings, videos=(video,))
    handler = Phase2GlossaryReconciliationHandler()
    with pytest.raises(ValueError, match="batch"):
        handler.execute(ctx, video=video)


def test_execute_raises_when_no_candidates(
    tmp_path: Path, make_settings: Any
) -> None:
    video = VideoExecution(video_id=VideoId.new(), source_path=tmp_path / "v.mp4")
    ctx, _ = build_phase_context(tmp_path, make_settings, videos=(video,))
    handler = Phase2GlossaryReconciliationHandler()
    with pytest.raises(StorageError) as exc_info:
        handler.execute(ctx, video=None)
    assert exc_info.value.code == "STORAGE.NO_CANDIDATES"
