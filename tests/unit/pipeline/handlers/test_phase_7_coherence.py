"""Tests du handler Phase 7 — coherence."""

import json
from pathlib import Path
from typing import Any

import pytest

from fahmi2.core.errors.exceptions import StorageError
from fahmi2.domain.enums import Language, PhaseStatus
from fahmi2.domain.ids import VideoId
from fahmi2.domain.video import VideoExecution
from fahmi2.infra.llm.interface import LLMResponse
from fahmi2.pipeline.handlers.phase_7_coherence import Phase7CoherenceHandler
from tests.unit.pipeline.handlers._helpers import build_phase_context


def _llm(content: str) -> LLMResponse:
    return LLMResponse(
        content=content,
        thinking_content=None,
        prompt_tokens=500,
        completion_tokens=500,
        cached_prompt_tokens=0,
        cost_usd=0.02,
    )


def test_handler_metadata() -> None:
    handler = Phase7CoherenceHandler()
    assert handler.phase_id.value == "phase_7_coherence"
    assert handler.is_per_video is False


def test_execute_rewrites_consolidated_for_each_language(
    tmp_path: Path, make_settings: Any
) -> None:
    ctx, _ = build_phase_context(
        tmp_path,
        make_settings,
        llm_response=_llm("# Polished document"),
        settings_overrides={
            "source_language": Language.FR,
            "output_languages": (Language.FR, Language.EN),
        },
    )
    # Seed des fichiers consolidés et du glossaire master
    (ctx.output_dir).mkdir(parents=True, exist_ok=True)
    (ctx.output_dir / "consolidated.fr.md").write_text("# Old fr", encoding="utf-8")
    (ctx.output_dir / "consolidated.en.md").write_text("# Old en", encoding="utf-8")
    (ctx.workspace).mkdir(parents=True, exist_ok=True)
    (ctx.workspace / "glossary_master.json").write_text(
        json.dumps({"terms": [{"term": "PIB", "definition": "..."}]}),
        encoding="utf-8",
    )

    handler = Phase7CoherenceHandler()
    result = handler.execute(ctx, video=None)
    assert result.status is PhaseStatus.SUCCEEDED
    fr = (ctx.output_dir / "consolidated.fr.md").read_text(encoding="utf-8")
    en = (ctx.output_dir / "consolidated.en.md").read_text(encoding="utf-8")
    assert fr == "# Polished document"
    assert en == "# Polished document"
    assert result.cost_usd == pytest.approx(0.04)  # 2 langues × 0.02


def test_execute_raises_when_consolidated_lang_missing(
    tmp_path: Path, make_settings: Any
) -> None:
    ctx, _ = build_phase_context(
        tmp_path,
        make_settings,
        settings_overrides={
            "source_language": Language.FR,
            "output_languages": (Language.FR,),
        },
    )
    handler = Phase7CoherenceHandler()
    with pytest.raises(StorageError) as exc_info:
        handler.execute(ctx, video=None)
    assert exc_info.value.code == "STORAGE.CONSOLIDATED_LANG_MISSING"


def test_execute_raises_when_video_provided(
    tmp_path: Path, make_settings: Any
) -> None:
    video = VideoExecution(video_id=VideoId.new(), source_path=tmp_path / "v.mp4")
    ctx, _ = build_phase_context(tmp_path, make_settings, videos=(video,))
    handler = Phase7CoherenceHandler()
    with pytest.raises(ValueError, match="batch"):
        handler.execute(ctx, video=video)
