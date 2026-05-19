"""Tests du handler Phase 5 — consolidation."""

import json
from pathlib import Path
from typing import Any

import pytest

from fahmi2.core.errors.exceptions import StorageError
from fahmi2.domain.enums import PhaseStatus
from fahmi2.domain.ids import VideoId
from fahmi2.domain.video import VideoExecution
from fahmi2.infra.llm._fakes import FakeLLMProvider
from fahmi2.infra.llm.interface import LLMResponse
from fahmi2.pipeline.handlers.phase_5_consolidation import Phase5ConsolidationHandler
from tests.unit.pipeline.handlers._helpers import build_phase_context


def _write_structured(workspace: Path, video_id: str, content: str) -> None:
    path = workspace / "structured" / f"{video_id}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _sequential_responses(responses: list[LLMResponse]) -> FakeLLMProvider:
    """Construit un FakeLLMProvider qui renvoie les réponses dans l'ordre.

    Args:
        responses: Réponses à retourner séquentiellement.

    Returns:
        ``FakeLLMProvider`` configuré.
    """
    fake = FakeLLMProvider()
    idx = [0]
    original_chat = fake.chat

    def _chat_sequential(**kwargs: Any) -> LLMResponse:
        original_chat(**kwargs)  # enregistre l'appel
        i = idx[0]
        idx[0] += 1
        return responses[i]

    fake.chat = _chat_sequential  # type: ignore[method-assign]
    return fake


def test_handler_metadata() -> None:
    handler = Phase5ConsolidationHandler()
    assert handler.phase_id.value == "phase_5_consolidation"
    assert handler.is_per_video is False


def test_execute_assembles_consolidated_markdown(
    tmp_path: Path, make_settings: Any
) -> None:
    videos = tuple(
        VideoExecution(video_id=VideoId.new(), source_path=tmp_path / f"v{i}.mp4")
        for i in range(2)
    )

    summary_json_1 = json.dumps(
        {"title": "Chapitre Un", "outline": ["a", "b"], "key_ideas": ["k1"]}
    )
    summary_json_2 = json.dumps(
        {"title": "Chapitre Deux", "outline": ["c"], "key_ideas": ["k2"]}
    )
    meta_json = json.dumps(
        {
            "global_title": "Mon Cours",
            "introduction_markdown": "Texte d'intro.",
            "plan_markdown": "1. Un\n2. Deux",
            "conclusion_markdown": "Texte de conclusion.",
        }
    )

    def _r(content: str, cost: float) -> LLMResponse:
        return LLMResponse(
            content=content,
            thinking_content=None,
            prompt_tokens=100,
            completion_tokens=50,
            cached_prompt_tokens=0,
            cost_usd=cost,
        )

    responses = [
        _r(summary_json_1, 0.001),
        _r(summary_json_2, 0.001),
        _r(meta_json, 0.005),
    ]
    ctx, _ = build_phase_context(tmp_path, make_settings, videos=videos)
    # Remplacer le LLM par notre version séquentielle
    ctx2 = ctx.__class__(  # même type
        run=ctx.run,
        settings=ctx.settings,
        workspace=ctx.workspace,
        output_dir=ctx.output_dir,
        state=ctx.state,
        artifacts=ctx.artifacts,
        stt_provider=ctx.stt_provider,
        llm_provider=_sequential_responses(responses),
        ffmpeg=ctx.ffmpeg,
        retriever=ctx.retriever,
        prompts=ctx.prompts,
        pause_token=ctx.pause_token,
        event_bus=ctx.event_bus,
    )
    _write_structured(ctx2.workspace, videos[0].video_id.value, "Contenu chap 1")
    _write_structured(ctx2.workspace, videos[1].video_id.value, "Contenu chap 2")

    handler = Phase5ConsolidationHandler()
    result = handler.execute(ctx2, video=None)
    assert result.status is PhaseStatus.SUCCEEDED
    assert result.artifact_path is not None
    content = result.artifact_path.read_text(encoding="utf-8")
    # Le titre global doit apparaître
    assert "# Mon Cours" in content
    # Les contenus des deux vidéos doivent être présents (intacts)
    assert "Contenu chap 1" in content
    assert "Contenu chap 2" in content
    # Intro / sommaire / chapitres numérotés / conclusion doivent apparaître
    assert "Introduction générale" in content
    assert "## Sommaire" in content
    assert "# 1. Chapitre Un" in content
    assert "# 2. Chapitre Deux" in content
    # Les ancres du sommaire pointent vers les chapitres numérotés
    assert "[Chapitre Un](#1-chapitre-un)" in content
    assert "[Chapitre Deux](#2-chapitre-deux)" in content
    assert "Conclusion générale" in content
    # Cost cumulé = 0.001 + 0.001 + 0.005
    assert result.cost_usd == pytest.approx(0.007)


def test_execute_raises_when_video_provided(
    tmp_path: Path, make_settings: Any
) -> None:
    video = VideoExecution(video_id=VideoId.new(), source_path=tmp_path / "v.mp4")
    ctx, _ = build_phase_context(tmp_path, make_settings, videos=(video,))
    handler = Phase5ConsolidationHandler()
    with pytest.raises(ValueError, match="batch"):
        handler.execute(ctx, video=video)


def test_execute_raises_when_structured_missing(
    tmp_path: Path, make_settings: Any
) -> None:
    video = VideoExecution(video_id=VideoId.new(), source_path=tmp_path / "v.mp4")
    ctx, _ = build_phase_context(tmp_path, make_settings, videos=(video,))
    handler = Phase5ConsolidationHandler()
    with pytest.raises(StorageError) as exc_info:
        handler.execute(ctx, video=None)
    assert exc_info.value.code == "STORAGE.STRUCTURED_MISSING"
