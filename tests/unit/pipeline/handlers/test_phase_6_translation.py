"""Tests du handler Phase 6 — translation."""

import json
from pathlib import Path
from typing import Any

import pytest

from fahmi2.core.errors.exceptions import StorageError
from fahmi2.domain.enums import Language, PhaseStatus
from fahmi2.domain.ids import VideoId
from fahmi2.domain.video import VideoExecution
from fahmi2.infra.llm.interface import LLMResponse
from fahmi2.pipeline.handlers.phase_6_translation import Phase6TranslationHandler
from tests.unit.pipeline.handlers._helpers import build_phase_context


def _llm(content: str = "Translated.") -> LLMResponse:
    return LLMResponse(
        content=content,
        thinking_content=None,
        prompt_tokens=400,
        completion_tokens=400,
        cached_prompt_tokens=0,
        cost_usd=0.01,
    )


def _seed_workspace(
    workspace: Path,
    *,
    videos: tuple[VideoExecution, ...],
    consolidated_md: str = "# Master\n\n## Intro\n\nTexte source.",
    glossary_terms: list[dict[str, Any]] | None = None,
) -> None:
    structured_dir = workspace / "structured"
    structured_dir.mkdir(parents=True, exist_ok=True)
    for v in videos:
        (structured_dir / f"{v.video_id.value}.md").write_text(
            f"# Vidéo {v.video_id.value}\n\nContenu.", encoding="utf-8"
        )
    (workspace / "consolidated_master.md").write_text(consolidated_md, encoding="utf-8")
    payload = {"terms": glossary_terms or [{"term": "PIB", "definition": "..."}]}
    (workspace / "glossary_master.json").write_text(
        json.dumps(payload), encoding="utf-8"
    )


def test_handler_metadata() -> None:
    handler = Phase6TranslationHandler()
    assert handler.phase_id.value == "phase_6_translation"
    assert handler.is_per_video is False


def test_execute_copies_artifacts_for_source_language(
    tmp_path: Path, make_settings: Any
) -> None:
    video = VideoExecution(video_id=VideoId.new(), source_path=tmp_path / "v.mp4")
    ctx, _ = build_phase_context(
        tmp_path,
        make_settings,
        videos=(video,),
        settings_overrides={
            "source_language": Language.FR,
            "output_languages": (Language.FR,),
        },
    )
    _seed_workspace(ctx.workspace, videos=(video,))
    handler = Phase6TranslationHandler()
    result = handler.execute(ctx, video=None)
    assert result.status is PhaseStatus.SUCCEEDED
    assert (
        ctx.output_dir / "per-video" / "fr" / f"{video.video_id.value}.md"
    ).exists()
    assert (ctx.output_dir / "consolidated.fr.md").exists()
    assert (ctx.output_dir / "glossary.fr.md").exists()
    # Pour la langue source on n'appelle pas le LLM
    assert result.cost_usd == 0.0


def test_execute_translates_for_target_language(
    tmp_path: Path, make_settings: Any
) -> None:
    video = VideoExecution(video_id=VideoId.new(), source_path=tmp_path / "v.mp4")
    ctx, _ = build_phase_context(
        tmp_path,
        make_settings,
        llm_response=_llm("Translated content."),
        videos=(video,),
        settings_overrides={
            "source_language": Language.FR,
            "output_languages": (Language.FR, Language.EN),
        },
    )
    _seed_workspace(ctx.workspace, videos=(video,))
    handler = Phase6TranslationHandler()
    result = handler.execute(ctx, video=None)
    assert result.status is PhaseStatus.SUCCEEDED
    # FR : copies
    assert (
        ctx.output_dir / "per-video" / "fr" / f"{video.video_id.value}.md"
    ).exists()
    # EN : traductions
    assert (
        ctx.output_dir / "per-video" / "en" / f"{video.video_id.value}.md"
    ).exists()
    assert (ctx.output_dir / "consolidated.en.md").exists()
    assert (ctx.output_dir / "glossary.en.md").exists()


def test_execute_raises_when_consolidated_master_missing(
    tmp_path: Path, make_settings: Any
) -> None:
    ctx, _ = build_phase_context(tmp_path, make_settings)
    handler = Phase6TranslationHandler()
    with pytest.raises(StorageError) as exc_info:
        handler.execute(ctx, video=None)
    assert exc_info.value.code == "STORAGE.CONSOLIDATED_MISSING"


def test_execute_raises_when_video_provided(
    tmp_path: Path, make_settings: Any
) -> None:
    video = VideoExecution(video_id=VideoId.new(), source_path=tmp_path / "v.mp4")
    ctx, _ = build_phase_context(tmp_path, make_settings, videos=(video,))
    handler = Phase6TranslationHandler()
    with pytest.raises(ValueError, match="batch"):
        handler.execute(ctx, video=video)


def test_execute_accumulates_per_video_translation_cost(
    tmp_path: Path, make_settings: Any
) -> None:
    video = VideoExecution(video_id=VideoId.new(), source_path=tmp_path / "v.mp4")
    ctx, _ = build_phase_context(
        tmp_path,
        make_settings,
        llm_response=_llm("Translated."),  # cost_usd=0.01 par appel
        videos=(video,),
        settings_overrides={
            "source_language": Language.FR,
            "output_languages": (Language.FR, Language.EN),
        },
    )
    _seed_workspace(ctx.workspace, videos=(video,))
    handler = Phase6TranslationHandler()
    result = handler.execute(ctx, video=None)
    # FR = source -> copies gratuites. EN -> 3 appels : 1 per-video + consolidated
    # + glossaire, chacun 0.01 = 0.03. Avant correctif : 0.02 (per-video ignoré).
    assert result.cost_usd == pytest.approx(0.03)
