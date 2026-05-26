"""Tests du décorateur de query expansion."""

from __future__ import annotations

import pytest

from fahmi2.chat.query_expander import QueryExpander
from fahmi2.core.retrieval.passages import TfidfPassageRetriever
from fahmi2.domain.chat import ChatSettings, CorpusChunk
from fahmi2.infra.llm._fakes import FakeLLMProvider
from fahmi2.infra.llm.interface import DEFAULT_MAX_OUTPUT_TOKENS, LLMResponse
from fahmi2.infra.prompts.loader import PromptLoader


def _chunk(cid: str, text: str) -> CorpusChunk:
    return CorpusChunk(
        chunk_id=cid,
        chapter_title="C",
        section_title="S",
        anchor=cid,
        text=text,
        origin="consolidated",
    )


def _expander(inner: TfidfPassageRetriever, *, expansion: str) -> QueryExpander:
    llm = FakeLLMProvider(
        default_response=LLMResponse(
            content=expansion,
            thinking_content=None,
            prompt_tokens=10,
            completion_tokens=5,
            cached_prompt_tokens=0,
            cost_usd=0.0,
        )
    )
    return QueryExpander(
        inner=inner,
        llm_provider=llm,
        prompt_loader=PromptLoader(),
        settings=ChatSettings(),
    )


def test_strong_match_skips_expansion() -> None:
    inner = TfidfPassageRetriever((_chunk("1", "le pib mesure la richesse"),))
    expander = _expander(inner, expansion="ignored")
    results = expander.retrieve(query="pib richesse", top_k=3)
    assert results[0].chunk.chunk_id == "1"


def test_weak_match_triggers_expansion_and_merges() -> None:
    inner = TfidfPassageRetriever(
        (_chunk("1", "produit intérieur brut richesse nationale"),)
    )
    expander = _expander(inner, expansion="produit intérieur brut richesse")
    results = expander.retrieve(query="économie agrégée ?", top_k=3)
    assert any(r.chunk.chunk_id == "1" for r in results)


def test_consumed_cost_includes_expansion() -> None:
    inner = TfidfPassageRetriever(
        (_chunk("1", "produit intérieur brut richesse nationale"),)
    )
    llm = FakeLLMProvider(
        default_response=LLMResponse(
            content="produit intérieur brut richesse",
            thinking_content=None,
            prompt_tokens=10,
            completion_tokens=5,
            cached_prompt_tokens=0,
            cost_usd=0.002,
        )
    )
    expander = QueryExpander(
        inner=inner,
        llm_provider=llm,
        prompt_loader=PromptLoader(),
        settings=ChatSettings(),
    )
    expander.retrieve(query="économie agrégée ?", top_k=3)  # déclenche l'expansion
    assert expander.consumed_cost_usd() == pytest.approx(0.002)


def test_expansion_requests_generous_max_tokens() -> None:
    inner = TfidfPassageRetriever(
        (_chunk("1", "produit intérieur brut richesse nationale"),)
    )
    llm = FakeLLMProvider(
        default_response=LLMResponse(
            content="produit intérieur brut richesse",
            thinking_content=None,
            prompt_tokens=10,
            completion_tokens=5,
            cached_prompt_tokens=0,
            cost_usd=0.0,
        )
    )
    expander = QueryExpander(
        inner=inner,
        llm_provider=llm,
        prompt_loader=PromptLoader(),
        settings=ChatSettings(),
    )
    expander.retrieve(query="économie agrégée ?", top_k=3)  # déclenche l'expansion
    assert llm.calls[-1]["max_tokens"] == DEFAULT_MAX_OUTPUT_TOKENS
