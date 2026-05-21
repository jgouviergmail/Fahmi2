"""Tests du handler Phase 5 — consolidation."""

import json
from pathlib import Path
from typing import Any

import pytest

from fahmi2.core.errors.exceptions import StorageError
from fahmi2.domain.enums import PhaseStatus
from fahmi2.domain.generation import ParallelismConfig
from fahmi2.domain.ids import VideoId
from fahmi2.domain.video import VideoExecution
from fahmi2.infra.llm._fakes import FakeLLMProvider
from fahmi2.infra.llm.interface import LLMResponse
from fahmi2.pipeline.handlers.phase_5_consolidation import (
    Phase5ConsolidationHandler,
    _assemble_consolidated,
    _renumber_subheadings,
    _strip_existing_numbering,
)
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
    tmp_path: Path, make_generation_settings: Any
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
            "summary_markdown": "Vue d'ensemble du cours en quelques phrases.",
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
    ctx, _ = build_phase_context(
        tmp_path,
        make_generation_settings,
        videos=videos,
        # Réponses couplées à l'ordre des appels → exécution séquentielle requise.
        settings_overrides={"parallelism": ParallelismConfig(llm_workers=1)},
    )
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
    # Le résumé exécutif apparaît sous le titre
    assert "## Résumé" in content
    assert "Vue d'ensemble du cours en quelques phrases." in content
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
    tmp_path: Path, make_generation_settings: Any
) -> None:
    video = VideoExecution(video_id=VideoId.new(), source_path=tmp_path / "v.mp4")
    ctx, _ = build_phase_context(tmp_path, make_generation_settings, videos=(video,))
    handler = Phase5ConsolidationHandler()
    with pytest.raises(ValueError, match="batch"):
        handler.execute(ctx, video=video)


def test_execute_raises_when_structured_missing(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    video = VideoExecution(video_id=VideoId.new(), source_path=tmp_path / "v.mp4")
    ctx, _ = build_phase_context(tmp_path, make_generation_settings, videos=(video,))
    handler = Phase5ConsolidationHandler()
    with pytest.raises(StorageError) as exc_info:
        handler.execute(ctx, video=None)
    assert exc_info.value.code == "STORAGE.STRUCTURED_MISSING"


# --- Tests unitaires de la renumerotation hierarchique ----------------------


def test_strip_existing_numbering_handles_various_formats() -> None:
    assert _strip_existing_numbering("1. Section") == "Section"
    assert _strip_existing_numbering("1.2 Section") == "Section"
    assert _strip_existing_numbering("1.2.3 - Section") == "Section"
    assert _strip_existing_numbering("Section") == "Section"
    assert _strip_existing_numbering("  1)  Section  ") == "Section"


def test_renumber_subheadings_assigns_hierarchical_numbers() -> None:
    body = (
        "## Section A\n"
        "texte A\n"
        "### Sous-section A1\n"
        "texte\n"
        "### Sous-section A2\n"
        "texte\n"
        "## Section B\n"
        "### Sous-section B1\n"
    )
    renumbered, subs = _renumber_subheadings(body, chapter_index=2)
    assert "## 2.1 Section A" in renumbered
    assert "### 2.1.1 Sous-section A1" in renumbered
    assert "### 2.1.2 Sous-section A2" in renumbered
    assert "## 2.2 Section B" in renumbered
    assert "### 2.2.1 Sous-section B1" in renumbered
    assert [s.number for s in subs] == ["2.1", "2.1.1", "2.1.2", "2.2", "2.2.1"]


def test_renumber_subheadings_strips_llm_existing_numbering() -> None:
    body = "## 1. Section LLM\n## 2.1 Autre section\n### 2.1.3 - Detail\n"
    renumbered, subs = _renumber_subheadings(body, chapter_index=1)
    assert "## 1.1 Section LLM" in renumbered
    assert "## 1.2 Autre section" in renumbered
    assert "### 1.2.1 Detail" in renumbered
    assert [s.title for s in subs] == ["Section LLM", "Autre section", "Detail"]


def test_renumber_subheadings_skips_code_blocks() -> None:
    body = (
        "## Vraie section\n"
        "```python\n"
        "## ce n'est pas un titre\n"
        "### non plus\n"
        "```\n"
        "### Reelle sous-section\n"
    )
    renumbered, subs = _renumber_subheadings(body, chapter_index=1)
    assert "## 1.1 Vraie section" in renumbered
    assert "## ce n'est pas un titre" in renumbered
    assert "### 1.1.1 Reelle sous-section" in renumbered
    # Le titre "ce n'est pas un titre" est dans un fence -> pas dans subs
    assert [s.title for s in subs] == ["Vraie section", "Reelle sous-section"]


def test_assemble_consolidated_includes_subheadings_in_toc() -> None:
    structured_by_video = {
        "v1": (
            "# Chapitre Un\n"
            "## Premiere section\n"
            "texte\n"
            "### Detail un\n"
            "texte\n"
            "## Deuxieme section\n"
        ),
        "v2": (
            "# Chapitre Deux\n"
            "## Section unique\n"
        ),
    }
    summaries = [
        {"video_id": "v1", "title": "Chapitre Un"},
        {"video_id": "v2", "title": "Chapitre Deux"},
    ]
    meta = {
        "global_title": "Mon Cours",
        "introduction_markdown": "Intro.",
        "conclusion_markdown": "Conclusion.",
    }
    md = _assemble_consolidated(meta, structured_by_video, summaries)
    # En-tetes numerotes presents dans le corps
    assert "# 1. Chapitre Un" in md
    assert "## 1.1 Premiere section" in md
    assert "### 1.1.1 Detail un" in md
    assert "## 1.2 Deuxieme section" in md
    assert "# 2. Chapitre Deux" in md
    assert "## 2.1 Section unique" in md
    # Sommaire avec ancres
    assert "[Chapitre Un](#1-chapitre-un)" in md
    assert "[1.1 Premiere section](#11-premiere-section)" in md
    assert "[1.1.1 Detail un](#111-detail-un)" in md
    assert "[1.2 Deuxieme section](#12-deuxieme-section)" in md
    assert "[2.1 Section unique](#21-section-unique)" in md


def test_assemble_consolidated_strips_llm_numbering_in_chapter_title() -> None:
    structured_by_video = {"v1": "# Vrai contenu\n## Section\n"}
    summaries = [{"video_id": "v1", "title": "1. Chapitre Pre-Numerote"}]
    meta = {
        "global_title": "T",
        "introduction_markdown": "",
        "conclusion_markdown": "",
    }
    md = _assemble_consolidated(meta, structured_by_video, summaries)
    # Le "1. " du LLM est decape, puis le chapitre est renumerote "1. ..."
    assert "# 1. Chapitre Pre-Numerote" in md
    assert "# 1. 1. " not in md


def test_assemble_consolidated_includes_summary_between_title_and_intro() -> None:
    structured_by_video = {"v1": "# Chap\n## Sec\ntexte\n"}
    summaries = [{"video_id": "v1", "title": "Chap"}]
    meta = {
        "global_title": "Mon Cours",
        "summary_markdown": "Un abstract synthétique du cours.",
        "introduction_markdown": "Intro développée.",
        "conclusion_markdown": "Conclusion.",
    }
    md = _assemble_consolidated(meta, structured_by_video, summaries)
    assert "## Résumé" in md
    assert "Un abstract synthétique du cours." in md
    # Ordre : titre < résumé < introduction
    assert md.index("# Mon Cours") < md.index("## Résumé")
    assert md.index("## Résumé") < md.index("## Introduction générale")


def test_assemble_consolidated_omits_summary_when_empty() -> None:
    structured_by_video = {"v1": "# Chap\n"}
    summaries = [{"video_id": "v1", "title": "Chap"}]
    meta = {
        "global_title": "T",
        "summary_markdown": "   ",
        "introduction_markdown": "Intro.",
        "conclusion_markdown": "",
    }
    md = _assemble_consolidated(meta, structured_by_video, summaries)
    assert "## Résumé" not in md


def test_assemble_consolidated_omits_summary_when_key_missing() -> None:
    structured_by_video = {"v1": "# Chap\n"}
    summaries = [{"video_id": "v1", "title": "Chap"}]
    meta = {"global_title": "T", "introduction_markdown": "", "conclusion_markdown": ""}
    md = _assemble_consolidated(meta, structured_by_video, summaries)
    assert "## Résumé" not in md


def test_assemble_consolidated_summary_not_referenced_in_toc() -> None:
    structured_by_video = {"v1": "# Chap\n## Sec\ntexte\n"}
    summaries = [{"video_id": "v1", "title": "Chap"}]
    meta = {
        "global_title": "T",
        "summary_markdown": "Abstract.",
        "introduction_markdown": "",
        "conclusion_markdown": "",
    }
    md = _assemble_consolidated(meta, structured_by_video, summaries)
    # La portion sommaire (entre "## Sommaire" et le 1er chapitre) ne cite pas le résumé.
    toc = md.split("## Sommaire", 1)[1].split("# 1.", 1)[0]
    assert "Résumé" not in toc


def test_consolidation_parallel_summaries(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    videos = tuple(
        VideoExecution(video_id=VideoId.new(), source_path=tmp_path / f"v{i}.mp4")
        for i in range(3)
    )
    fixed = LLMResponse(
        content=json.dumps(
            {
                "title": "T",
                "global_title": "G",
                "summary_markdown": "S",
                "introduction_markdown": "I",
                "conclusion_markdown": "C",
            }
        ),
        thinking_content=None,
        prompt_tokens=10,
        completion_tokens=10,
        cached_prompt_tokens=0,
        cost_usd=0.003,
    )
    ctx, _ = build_phase_context(
        tmp_path,
        make_generation_settings,
        llm_response=fixed,
        videos=videos,
        settings_overrides={"parallelism": ParallelismConfig(llm_workers=4)},
    )
    for v in videos:
        _write_structured(
            ctx.workspace, v.video_id.value, f"# Chap {v.video_id.value}\n\nContenu."
        )

    result = Phase5ConsolidationHandler().execute(ctx, video=None)
    assert result.status is PhaseStatus.SUCCEEDED
    assert (ctx.workspace / "consolidated_master.md").exists()
    assert result.cost_usd > 0
