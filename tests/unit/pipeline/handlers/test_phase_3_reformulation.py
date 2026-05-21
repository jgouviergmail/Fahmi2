"""Tests du handler Phase 3 — reformulation."""

import json
from pathlib import Path
from typing import Any

import pytest

from fahmi2.core.errors.exceptions import StorageError
from fahmi2.domain.enums import PhaseStatus
from fahmi2.domain.generation import ParallelismConfig
from fahmi2.domain.ids import VideoId
from fahmi2.domain.video import VideoExecution
from fahmi2.infra.llm.interface import LLMResponse
from fahmi2.pipeline.handlers.phase_3_reformulation import Phase3ReformulationHandler
from tests.unit.pipeline.handlers._helpers import (
    build_phase_context,
    write_transcription_fixture,
)


def _llm(content: str) -> LLMResponse:
    return LLMResponse(
        content=content,
        thinking_content=None,
        prompt_tokens=200,
        completion_tokens=300,
        cached_prompt_tokens=0,
        cost_usd=0.005,
    )


def test_handler_metadata() -> None:
    handler = Phase3ReformulationHandler()
    assert handler.phase_id.value == "phase_3_reformulation"
    assert handler.is_per_video is True


def test_execute_writes_reformulated_markdown(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    video = VideoExecution(video_id=VideoId.new(), source_path=tmp_path / "v.mp4")
    ctx, _ = build_phase_context(
        tmp_path,
        make_generation_settings,
        llm_response=_llm("Texte reformulé."),
        videos=(video,),
    )
    write_transcription_fixture(ctx.workspace, video.video_id.value)
    handler = Phase3ReformulationHandler()
    result = handler.execute(ctx, video=video)
    assert result.status is PhaseStatus.SUCCEEDED
    assert result.artifact_path is not None
    assert result.artifact_path.read_text(encoding="utf-8") == "Texte reformulé."


def test_execute_includes_top_k_glossary_terms_in_prompt(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    video = VideoExecution(video_id=VideoId.new(), source_path=tmp_path / "v.mp4")
    ctx, _ = build_phase_context(
        tmp_path,
        make_generation_settings,
        llm_response=_llm("ok"),
        videos=(video,),
    )
    write_transcription_fixture(
        ctx.workspace, video.video_id.value, text="PIB inflation"
    )
    # Glossary master présent
    master_path = ctx.workspace / "glossary_master.json"
    master_path.parent.mkdir(parents=True, exist_ok=True)
    master_path.write_text(
        json.dumps(
            {"terms": [{"term": "PIB", "definition": "produit intérieur brut"}]}
        ),
        encoding="utf-8",
    )

    handler = Phase3ReformulationHandler()
    handler.execute(ctx, video=video)
    # On vérifie que le LLM a été appelé avec un user prompt qui mentionne PIB
    fake_llm = ctx.llm_provider
    assert hasattr(fake_llm, "calls")
    last_messages = fake_llm.calls[-1]["messages"]
    user_content = next(m.content for m in last_messages if m.role == "user")
    assert "PIB" in user_content


def test_execute_raises_when_transcription_missing(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    video = VideoExecution(video_id=VideoId.new(), source_path=tmp_path / "v.mp4")
    ctx, _ = build_phase_context(tmp_path, make_generation_settings, videos=(video,))
    handler = Phase3ReformulationHandler()
    with pytest.raises(StorageError) as exc_info:
        handler.execute(ctx, video=video)
    assert exc_info.value.code == "STORAGE.TRANSCRIPT_MISSING"


def test_execute_raises_when_video_is_none(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    ctx, _ = build_phase_context(tmp_path, make_generation_settings)
    handler = Phase3ReformulationHandler()
    with pytest.raises(ValueError, match="VideoExecution"):
        handler.execute(ctx, video=None)


def test_execute_works_when_glossary_master_absent(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    video = VideoExecution(video_id=VideoId.new(), source_path=tmp_path / "v.mp4")
    ctx, _ = build_phase_context(
        tmp_path,
        make_generation_settings,
        llm_response=_llm("ok"),
        videos=(video,),
    )
    write_transcription_fixture(ctx.workspace, video.video_id.value)
    handler = Phase3ReformulationHandler()
    result = handler.execute(ctx, video=video)
    assert result.status is PhaseStatus.SUCCEEDED


def test_phase_workers_is_llm_pool(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    handler = Phase3ReformulationHandler()
    ctx, _ = build_phase_context(
        tmp_path,
        make_generation_settings,
        settings_overrides={"parallelism": ParallelismConfig(llm_workers=7)},
    )
    assert handler.max_parallel_workers(ctx) == 7
