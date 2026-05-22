"""Tests de l'assemblage des messages du chat."""

from __future__ import annotations

from fahmi2.chat.prompt_builder import (
    build_chat_messages,
    format_passages,
    truncate_history,
)
from fahmi2.domain.chat import ChatMessage, ChatSettings, CorpusChunk, RetrievedPassage
from fahmi2.domain.enums import ChatGroundingMode, Language
from fahmi2.infra.prompts.loader import PromptLoader


def _passage(idx: int, text: str) -> RetrievedPassage:
    chunk = CorpusChunk(
        chunk_id=f"c::{idx}",
        chapter_title=f"Chap {idx}",
        section_title=f"Sec {idx}",
        anchor=f"a{idx}",
        text=text,
        origin="consolidated",
    )
    return RetrievedPassage(chunk=chunk, score=1.0)


def test_format_passages_numbered() -> None:
    text = format_passages((_passage(1, "alpha"), _passage(2, "beta")))
    assert "§1" in text and "§2" in text
    assert "alpha" in text and "beta" in text


def test_truncate_history_keeps_recent() -> None:
    history = tuple(ChatMessage(role="user", content="x" * 400) for _ in range(10))
    kept = truncate_history(history, max_tokens=50)
    assert len(kept) < len(history)
    assert kept[-1] is history[-1]  # les plus récents sont conservés


def test_build_chat_messages_strict_has_system_and_question() -> None:
    loader = PromptLoader()
    messages = build_chat_messages(
        question="Qu'est-ce que le PIB ?",
        passages=(_passage(1, "Le PIB mesure la richesse."),),
        glossary_text="",
        history=(),
        settings=ChatSettings(grounding_mode=ChatGroundingMode.STRICT),
        language=Language.FR,
        prompt_loader=loader,
    )
    assert messages[0].role == "system"
    assert "Extraits du cours" in messages[0].content
    assert messages[-1].role == "user"
    assert messages[-1].content == "Qu'est-ce que le PIB ?"
