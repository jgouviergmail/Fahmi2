"""Tests de la stratégie ORDERED (1 source = 1 chapitre, ordre préservé)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fahmi2.domain.enums import SourceKind
from fahmi2.domain.generation import ParallelismConfig
from fahmi2.domain.ids import SourceId
from fahmi2.domain.source import InputSource, SourceExecution
from fahmi2.infra.llm._fakes import FakeLLMProvider
from fahmi2.infra.llm.interface import LLMResponse
from fahmi2.pipeline.handlers._consolidation._base import load_all_structured
from fahmi2.pipeline.handlers._consolidation.ordered import OrderedConsolidationStrategy
from tests.unit.pipeline.handlers._helpers import build_phase_context


def _write_structured(workspace: Path, source_id: str, content: str) -> None:
    path = workspace / "structured" / f"{source_id}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _sequential(responses: list[LLMResponse]) -> FakeLLMProvider:
    fake = FakeLLMProvider()
    idx = [0]
    original_chat = fake.chat

    def _chat(**kwargs: Any) -> LLMResponse:
        original_chat(**kwargs)
        i = idx[0]
        idx[0] += 1
        return responses[i]

    fake.chat = _chat  # type: ignore[method-assign]
    return fake


def _resp(content: str, cost: float) -> LLMResponse:
    return LLMResponse(
        content=content,
        thinking_content=None,
        prompt_tokens=100,
        completion_tokens=50,
        cached_prompt_tokens=0,
        cost_usd=cost,
    )


def _with_llm(ctx: Any, llm: FakeLLMProvider) -> Any:
    return ctx.__class__(
        run=ctx.run,
        settings=ctx.settings,
        workspace=ctx.workspace,
        output_dir=ctx.output_dir,
        state=ctx.state,
        artifacts=ctx.artifacts,
        stt_provider=ctx.stt_provider,
        llm_provider=llm,
        ffmpeg=ctx.ffmpeg,
        ingestion=ctx.ingestion,
        retriever=ctx.retriever,
        prompts=ctx.prompts,
        pause_token=ctx.pause_token,
        event_bus=ctx.event_bus,
    )


def test_ordered_strategy_assembles_in_order(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    sources = tuple(
        SourceExecution(
            source_id=SourceId.new(),
            source=InputSource(
                kind=SourceKind.VIDEO, location=str(tmp_path / f"v{i}.mp4")
            ),
        )
        for i in range(2)
    )
    responses = [
        _resp(json.dumps({"title": "Chapitre Un", "outline": ["a"], "key_ideas": ["k1"]}), 0.001),
        _resp(json.dumps({"title": "Chapitre Deux", "outline": ["c"], "key_ideas": ["k2"]}), 0.001),
        _resp(
            json.dumps(
                {
                    "global_title": "Mon Cours",
                    "summary_markdown": "Vue d'ensemble.",
                    "introduction_markdown": "Intro.",
                    "conclusion_markdown": "Conclusion.",
                }
            ),
            0.005,
        ),
    ]
    ctx, _ = build_phase_context(
        tmp_path,
        make_generation_settings,
        sources=sources,
        settings_overrides={"parallelism": ParallelismConfig(llm_workers=1)},
    )
    ctx = _with_llm(ctx, _sequential(responses))
    _write_structured(ctx.workspace, sources[0].source_id.value, "Contenu chap 1")
    _write_structured(ctx.workspace, sources[1].source_id.value, "Contenu chap 2")

    structured = load_all_structured(ctx.workspace, ctx.run.sources)
    result = OrderedConsolidationStrategy().consolidate(ctx, structured)

    assert "# Mon Cours" in result.consolidated_markdown
    assert "# 1. Chapitre Un" in result.consolidated_markdown
    assert "# 2. Chapitre Deux" in result.consolidated_markdown
    assert "Contenu chap 1" in result.consolidated_markdown
    assert "Contenu chap 2" in result.consolidated_markdown
    assert result.cost_usd == 0.007
