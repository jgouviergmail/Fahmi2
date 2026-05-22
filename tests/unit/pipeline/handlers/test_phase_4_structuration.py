"""Tests du handler Phase 4 — structuration."""

from pathlib import Path
from typing import Any

import pytest

from fahmi2.core.errors.exceptions import StorageError
from fahmi2.domain.enums import PhaseStatus, SourceKind
from fahmi2.domain.generation import ParallelismConfig
from fahmi2.domain.ids import SourceId
from fahmi2.domain.source import InputSource, SourceExecution
from fahmi2.infra.llm.interface import LLMResponse
from fahmi2.pipeline.handlers.phase_4_structuration import Phase4StructurationHandler
from tests.unit.pipeline.handlers._helpers import build_phase_context


def _llm(content: str) -> LLMResponse:
    return LLMResponse(
        content=content,
        thinking_content=None,
        prompt_tokens=300,
        completion_tokens=400,
        cached_prompt_tokens=0,
        cost_usd=0.008,
    )


def _write_reformulated(workspace: Path, source_id: str, content: str) -> Path:
    path = workspace / "reformulated" / f"{source_id}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def test_handler_metadata() -> None:
    handler = Phase4StructurationHandler()
    assert handler.phase_id.value == "phase_4_structuration"
    assert handler.is_per_source is True


def test_execute_writes_structured_markdown(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    video = SourceExecution(
        source_id=SourceId.new(),
        source=InputSource(kind=SourceKind.VIDEO, location=str(tmp_path / "v.mp4")),
    )
    ctx, _ = build_phase_context(
        tmp_path,
        make_generation_settings,
        llm_response=_llm("# Titre\n\n## Intro\n\n…"),
        sources=(video,),
    )
    _write_reformulated(ctx.workspace, video.source_id.value, "Texte source.")
    handler = Phase4StructurationHandler()
    result = handler.execute(ctx, source=video)
    assert result.status is PhaseStatus.SUCCEEDED
    assert result.artifact_path is not None
    content = result.artifact_path.read_text(encoding="utf-8")
    assert "# Titre" in content


def test_execute_raises_when_reformulated_missing(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    video = SourceExecution(
        source_id=SourceId.new(),
        source=InputSource(kind=SourceKind.VIDEO, location=str(tmp_path / "v.mp4")),
    )
    ctx, _ = build_phase_context(tmp_path, make_generation_settings, sources=(video,))
    handler = Phase4StructurationHandler()
    with pytest.raises(StorageError) as exc_info:
        handler.execute(ctx, source=video)
    assert exc_info.value.code == "STORAGE.REFORMULATED_MISSING"


def test_execute_raises_when_video_is_none(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    ctx, _ = build_phase_context(tmp_path, make_generation_settings)
    handler = Phase4StructurationHandler()
    with pytest.raises(ValueError, match="SourceExecution"):
        handler.execute(ctx, source=None)


def test_phase_workers_is_llm_pool(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    handler = Phase4StructurationHandler()
    ctx, _ = build_phase_context(
        tmp_path,
        make_generation_settings,
        settings_overrides={"parallelism": ParallelismConfig(llm_workers=7)},
    )
    assert handler.max_parallel_workers(ctx) == 7
