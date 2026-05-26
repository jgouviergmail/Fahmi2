"""Tests de la stratégie THEMATIC (map-reduce à provenance)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fahmi2.domain.enums import ConsolidationMode, SourceKind
from fahmi2.domain.generation import ParallelismConfig
from fahmi2.domain.ids import SourceId
from fahmi2.domain.source import InputSource, SourceExecution
from fahmi2.infra.llm._fakes import FakeLLMProvider
from fahmi2.infra.llm.interface import LLMResponse
from fahmi2.pipeline.handlers._consolidation._base import load_all_structured
from fahmi2.pipeline.handlers._consolidation.thematic import (
    COMPLEMENTARY_CHAPTER_TITLE,
    ThematicConsolidationStrategy,
    _chapter_coverage_gaps,
    _elements_from_payload,
    _elements_payload_for_chapter,
    _FactElement,
    _PlannedChapter,
    _reconcile_coverage,
    _render_facts_md,
)
from tests.unit.pipeline.handlers._helpers import build_phase_context

# --------------------------------------------------------------------------- #
# Helpers de test (réponses LLM séquentielles couplées à l'ordre des appels).
# --------------------------------------------------------------------------- #


def _write_structured(workspace: Path, source_id: str, content: str) -> None:
    path = workspace / "structured" / f"{source_id}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _resp(content: str, cost: float = 0.001) -> LLMResponse:
    return LLMResponse(
        content=content,
        thinking_content=None,
        prompt_tokens=100,
        completion_tokens=50,
        cached_prompt_tokens=0,
        cost_usd=cost,
    )


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


def _two_sources(tmp_path: Path) -> tuple[SourceExecution, ...]:
    return tuple(
        SourceExecution(
            source_id=SourceId.new(),
            source=InputSource(
                kind=SourceKind.VIDEO, location=str(tmp_path / f"v{i}.mp4")
            ),
        )
        for i in range(2)
    )


# --------------------------------------------------------------------------- #
# Fonctions pures.
# --------------------------------------------------------------------------- #


def test_elements_from_payload_prefixes_source() -> None:
    payload = {
        "elements": [
            {"n": 1, "type": "fait", "enonce": "E1", "donnees": "", "extrait_verbatim": "v1"},
            {"n": 2, "type": "chiffre", "enonce": "E2", "donnees": "42", "extrait_verbatim": "v2"},
        ]
    }
    elements = _elements_from_payload(payload, source_id="s1")
    assert [e.id for e in elements] == ["s1#1", "s1#2"]
    assert elements[1].donnees == "42"


def test_render_facts_md_groups_by_source() -> None:
    els = [
        _FactElement("s1#1", "s1", "fait", "E1", "", "v1"),
        _FactElement("s2#1", "s2", "chiffre", "E2", "42", "v2"),
    ]
    md = _render_facts_md(els)
    assert "s1" in md and "s2" in md and "E1" in md and "42" in md


def test_reconcile_coverage_adds_complementary_for_orphans() -> None:
    planned = [_PlannedChapter("Thème A", 1, ("s1#1",))]
    chapters, orphans = _reconcile_coverage(planned, all_ids=["s1#1", "s1#2", "s2#1"])
    assert orphans == ["s1#2", "s2#1"]
    assert chapters[-1].title == COMPLEMENTARY_CHAPTER_TITLE
    assert chapters[-1].element_ids == ("s1#2", "s2#1")


def test_reconcile_coverage_no_orphans_keeps_plan() -> None:
    planned = [_PlannedChapter("A", 1, ("s1#1", "s1#2"))]
    chapters, orphans = _reconcile_coverage(planned, all_ids=["s1#1", "s1#2"])
    assert orphans == []
    assert len(chapters) == 1


def test_reconcile_coverage_drops_unknown_ids() -> None:
    planned = [_PlannedChapter("A", 1, ("s1#1", "ghost#9"))]
    chapters, orphans = _reconcile_coverage(planned, all_ids=["s1#1"])
    assert chapters[0].element_ids == ("s1#1",)
    assert orphans == []


def test_chapter_coverage_gaps() -> None:
    assert _chapter_coverage_gaps(assigned=("a", "b", "c"), used=("a", "c")) == ["b"]
    assert _chapter_coverage_gaps(assigned=("a",), used=("a", "z")) == []


def test_conflicting_elements_reach_same_chapter_payload() -> None:
    # Deux énoncés contradictoires (selon source) destinés au même chapitre :
    # le payload T3 doit contenir LES DEUX (co-localisation → conflit visible).
    by_id = {
        "s1#1": _FactElement("s1#1", "s1", "chiffre", "La valeur est 10", "10", "…10…"),
        "s2#1": _FactElement("s2#1", "s2", "chiffre", "La valeur est 20", "20", "…20…"),
    }
    payload = _elements_payload_for_chapter(("s1#1", "s2#1"), by_id)
    assert {p["id"] for p in payload} == {"s1#1", "s2#1"}
    assert {p["source"] for p in payload} == {"s1", "s2"}


# --------------------------------------------------------------------------- #
# Bout en bout (avec FakeLLMProvider séquentiel).
# --------------------------------------------------------------------------- #


def _ledger(enonce: str) -> str:
    return json.dumps(
        {
            "elements": [
                {
                    "n": 1,
                    "type": "fait",
                    "enonce": enonce,
                    "donnees": "",
                    "extrait_verbatim": f"…{enonce}…",
                }
            ]
        }
    )


def _full_responses(sources: tuple[SourceExecution, ...]) -> list[LLMResponse]:
    """Séquence T1×2, T2, T3, T4 couvrant tous les ids en un seul chapitre."""
    ids = [f"{s.source_id.value}#1" for s in sources]
    plan = {"global_title": "GT", "chapters": [{"title": "Thème", "order": 1, "element_ids": ids}]}
    chapter = {"body_markdown": "## Sous-titre\nTexte.", "used_element_ids": ids}
    meta = {
        "global_title": "GT",
        "summary_markdown": "Résumé.",
        "introduction_markdown": "Intro.",
        "conclusion_markdown": "Conclusion.",
    }
    return [
        _resp(_ledger("E0")),
        _resp(_ledger("E1")),
        _resp(json.dumps(plan)),
        _resp(json.dumps(chapter)),
        _resp(json.dumps(meta), 0.005),
    ]


def test_thematic_consolidate_end_to_end(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    sources = _two_sources(tmp_path)
    fake = _sequential(_full_responses(sources))
    ctx, _ = build_phase_context(
        tmp_path,
        make_generation_settings,
        sources=sources,
        settings_overrides={
            "consolidation_mode": ConsolidationMode.THEMATIC,
            "parallelism": ParallelismConfig(llm_workers=1),
        },
    )
    ctx = _with_llm(ctx, fake)
    _write_structured(ctx.workspace, sources[0].source_id.value, "# A\nContenu A")
    _write_structured(ctx.workspace, sources[1].source_id.value, "# B\nContenu B")

    structured = load_all_structured(ctx.workspace, ctx.run.sources)
    result = ThematicConsolidationStrategy().consolidate(ctx, structured)

    assert result.consolidated_markdown.startswith("# GT")
    assert "## Sommaire" in result.consolidated_markdown
    assert "# 1. Thème" in result.consolidated_markdown
    assert result.cost_usd > 0
    base = ctx.workspace / "consolidation"
    assert (base / "facts_master.json").exists()
    assert (base / "facts.md").exists()
    assert (base / "thematic_plan.json").exists()
    assert (base / "coverage.json").exists()
    assert (base / "chapters" / "1.md").exists()


def test_thematic_reuses_fresh_artifacts_on_resume(
    tmp_path: Path, make_generation_settings: Any
) -> None:
    sources = _two_sources(tmp_path)
    # 5 réponses pour le 1er run + 1 réponse méta pour le 2e (seule T4 rappelle le LLM).
    responses = _full_responses(sources) + [
        _resp(json.dumps({"global_title": "GT", "introduction_markdown": "Intro2."}), 0.005)
    ]
    fake = _sequential(responses)
    ctx, _ = build_phase_context(
        tmp_path,
        make_generation_settings,
        sources=sources,
        settings_overrides={
            "consolidation_mode": ConsolidationMode.THEMATIC,
            "parallelism": ParallelismConfig(llm_workers=1),
        },
    )
    ctx = _with_llm(ctx, fake)
    _write_structured(ctx.workspace, sources[0].source_id.value, "# A\nContenu A")
    _write_structured(ctx.workspace, sources[1].source_id.value, "# B\nContenu B")
    structured = load_all_structured(ctx.workspace, ctx.run.sources)

    strategy = ThematicConsolidationStrategy()
    strategy.consolidate(ctx, structured)
    calls_after_first = len(fake.calls)
    assert calls_after_first == 5  # 2×T1 + T2 + T3 + T4

    strategy.consolidate(ctx, structured)
    # Reprise : T1/T2/T3 réutilisés (artefacts frais) ; seule la méta T4 rappelle.
    assert len(fake.calls) == calls_after_first + 1
