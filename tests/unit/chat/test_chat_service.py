"""Tests du moteur de chat (réponse non-streaming)."""

from __future__ import annotations

from fahmi2.chat.chat_service import ChatService
from fahmi2.core.retrieval.passages import TfidfPassageRetriever
from fahmi2.domain.chat import ChatSettings, CorpusChunk
from fahmi2.domain.enums import Language
from fahmi2.infra.llm._fakes import FakeLLMProvider
from fahmi2.infra.llm.interface import LLMResponse
from fahmi2.infra.prompts.loader import PromptLoader


def _chunk(cid: str, text: str) -> CorpusChunk:
    return CorpusChunk(
        chunk_id=cid,
        chapter_title="Économie",
        section_title="PIB",
        anchor="pib",
        text=text,
        origin="consolidated",
    )


def _service(answer: str) -> ChatService:
    response = LLMResponse(
        content=answer,
        thinking_content=None,
        prompt_tokens=120,
        completion_tokens=30,
        cached_prompt_tokens=0,
        cost_usd=0.01,
    )
    return ChatService(
        llm_provider=FakeLLMProvider(default_response=response),
        prompt_loader=PromptLoader(),
    )


def test_answer_returns_message_with_citation() -> None:
    retriever = TfidfPassageRetriever(
        (_chunk("1", "Le produit intérieur brut mesure la richesse."),)
    )
    service = _service("Le PIB mesure la richesse produite [§1].")
    message = service.answer(
        question="Qu'est-ce que le PIB ?",
        retriever=retriever,
        glossary_text="",
        history=(),
        settings=ChatSettings(),
        language=Language.FR,
    )
    assert message.role == "assistant"
    assert "[§1]" in message.content
    assert message.cost_usd == 0.01
    assert len(message.citations) == 1
    assert message.citations[0].anchor == "pib"


def test_stream_answer_yields_deltas_then_final_message() -> None:
    retriever = TfidfPassageRetriever(
        (_chunk("1", "Le produit intérieur brut mesure la richesse."),)
    )
    service = _service("Le PIB mesure la richesse [§1].")
    chunks = list(
        service.stream_answer(
            question="Qu'est-ce que le PIB ?",
            retriever=retriever,
            glossary_text="",
            history=(),
            settings=ChatSettings(),
            language=Language.FR,
        )
    )
    streamed = "".join(c.content_delta for c in chunks if c.message is None)
    assert streamed == "Le PIB mesure la richesse [§1]."
    final = chunks[-1]
    assert final.message is not None
    assert final.message.role == "assistant"
    assert final.message.citations[0].anchor == "pib"
    assert final.message.cost_usd == 0.01


def test_answer_no_citation_when_empty_corpus() -> None:
    service = _service("Ce point n'est pas couvert par le cours.")
    message = service.answer(
        question="Question hors sujet ?",
        retriever=TfidfPassageRetriever(()),
        glossary_text="",
        history=(),
        settings=ChatSettings(),
        language=Language.FR,
    )
    assert message.citations == ()
