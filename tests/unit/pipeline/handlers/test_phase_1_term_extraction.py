"""Tests du handler Phase 1 — term extraction."""

import json
from pathlib import Path
from typing import Any

import pytest

from fahmi2.core.errors.exceptions import LLMError, StorageError
from fahmi2.domain.enums import PhaseStatus, SourceKind
from fahmi2.domain.generation import ParallelismConfig
from fahmi2.domain.ids import SourceId
from fahmi2.domain.source import InputSource, SourceExecution
from fahmi2.infra.llm.interface import LLMResponse
from fahmi2.pipeline.handlers.phase_1_term_extraction import (
    Phase1TermExtractionHandler,
)
from tests.unit.pipeline.handlers._helpers import (
    build_phase_context,
    write_transcription_fixture,
)


def _scripted_terms_response(content: str) -> LLMResponse:
    return LLMResponse(
        content=content,
        thinking_content=None,
        prompt_tokens=100,
        completion_tokens=50,
        cached_prompt_tokens=0,
        cost_usd=0.0005,
    )


def test_handler_metadata() -> None:
    handler = Phase1TermExtractionHandler()
    assert handler.phase_id.value == "phase_1_term_extraction"
    assert handler.is_per_source is True


def test_execute_writes_candidates_json(tmp_path: Path, make_generation_settings: Any) -> None:
    video = SourceExecution(
        source_id=SourceId.new(),
        source=InputSource(kind=SourceKind.VIDEO, location=str(tmp_path / "v.mp4")),
    )
    expected_payload = {
        "terms": [
            {
                "term": "PIB",
                "definition": "produit intérieur brut",
                "aliases": ["Produit Intérieur Brut"],
            }
        ]
    }
    ctx, _ = build_phase_context(
        tmp_path,
        make_generation_settings,
        llm_response=_scripted_terms_response(json.dumps(expected_payload)),
        sources=(video,),
    )
    write_transcription_fixture(ctx.workspace, video.source_id.value)
    handler = Phase1TermExtractionHandler()
    result = handler.execute(ctx, source=video)
    assert result.status is PhaseStatus.SUCCEEDED
    assert result.artifact_path is not None
    written = json.loads(result.artifact_path.read_text(encoding="utf-8"))
    assert written == expected_payload
    assert result.cost_usd == pytest.approx(0.0005)


def test_execute_raises_on_invalid_json(tmp_path: Path, make_generation_settings: Any) -> None:
    video = SourceExecution(
        source_id=SourceId.new(),
        source=InputSource(kind=SourceKind.VIDEO, location=str(tmp_path / "v.mp4")),
    )
    ctx, _ = build_phase_context(
        tmp_path,
        make_generation_settings,
        llm_response=_scripted_terms_response("ce n'est pas du JSON"),
        sources=(video,),
    )
    write_transcription_fixture(ctx.workspace, video.source_id.value)
    handler = Phase1TermExtractionHandler()
    with pytest.raises(LLMError) as exc_info:
        handler.execute(ctx, source=video)
    assert exc_info.value.code == "LLM.INVALID_JSON"


def test_execute_handles_json_fenced_response(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    video = SourceExecution(
        source_id=SourceId.new(),
        source=InputSource(kind=SourceKind.VIDEO, location=str(tmp_path / "v.mp4")),
    )
    fenced = "```json\n{\"terms\": []}\n```"
    ctx, _ = build_phase_context(
        tmp_path,
        make_generation_settings,
        llm_response=_scripted_terms_response(fenced),
        sources=(video,),
    )
    write_transcription_fixture(ctx.workspace, video.source_id.value)
    handler = Phase1TermExtractionHandler()
    result = handler.execute(ctx, source=video)
    assert result.status is PhaseStatus.SUCCEEDED
    assert result.artifact_path is not None
    written = json.loads(result.artifact_path.read_text(encoding="utf-8"))
    assert written == {"terms": []}


def test_execute_raises_when_transcription_missing(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    video = SourceExecution(
        source_id=SourceId.new(),
        source=InputSource(kind=SourceKind.VIDEO, location=str(tmp_path / "v.mp4")),
    )
    ctx, _ = build_phase_context(tmp_path, make_generation_settings, sources=(video,))
    handler = Phase1TermExtractionHandler()
    with pytest.raises(StorageError) as exc_info:
        handler.execute(ctx, source=video)
    assert exc_info.value.code == "STORAGE.TRANSCRIPT_MISSING"


def test_execute_raises_when_video_is_none(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    ctx, _ = build_phase_context(tmp_path, make_generation_settings)
    handler = Phase1TermExtractionHandler()
    with pytest.raises(ValueError, match="SourceExecution"):
        handler.execute(ctx, source=None)


def test_phase_workers_is_llm_pool(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    handler = Phase1TermExtractionHandler()
    ctx, _ = build_phase_context(
        tmp_path,
        make_generation_settings,
        settings_overrides={"parallelism": ParallelismConfig(llm_workers=7)},
    )
    assert handler.max_parallel_workers(ctx) == 7
