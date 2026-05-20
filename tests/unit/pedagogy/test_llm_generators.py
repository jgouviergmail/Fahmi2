"""Tests des 8 générateurs de supports LLM (JSON crafté via FakeLLMProvider)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fahmi2.core.retry.policy import RetryPolicy
from fahmi2.domain.enums import Language, SupportType
from fahmi2.domain.supports import (
    ClozeItem,
    Flashcard,
    KeyPoints,
    MockExam,
    OpenQuestion,
    QcmItem,
    RevisionSheet,
    TrueFalseItem,
)
from fahmi2.infra.llm._fakes import FakeLLMProvider
from fahmi2.infra.llm.interface import LLMResponse
from fahmi2.infra.prompts.loader import PromptLoader
from fahmi2.infra.storage.fs_artifacts import FsArtifactStore
from fahmi2.pedagogy.chapters import Chapter
from fahmi2.pedagogy.events import PedagogyEvent
from fahmi2.pedagogy.generators.cloze import ClozeGenerator
from fahmi2.pedagogy.generators.flashcards_concepts import FlashcardsConceptsGenerator
from fahmi2.pedagogy.generators.key_points import KeyPointsGenerator
from fahmi2.pedagogy.generators.mock_exam import MockExamGenerator
from fahmi2.pedagogy.generators.open_questions import OpenQuestionsGenerator
from fahmi2.pedagogy.generators.qcm import QcmGenerator
from fahmi2.pedagogy.generators.revision_sheet import RevisionSheetGenerator
from fahmi2.pedagogy.generators.true_false import TrueFalseGenerator
from fahmi2.pedagogy.support_generator import SupportContext
from fahmi2.pipeline.event_bus import EventBus
from fahmi2.pipeline.pause_token import PauseToken

_CHAPTER = Chapter(index=1, title="Bases", anchor="1-bases", body_markdown="Contenu.")


def _provider(content: str) -> FakeLLMProvider:
    return FakeLLMProvider(
        default_response=LLMResponse(
            content=content,
            thinking_content=None,
            prompt_tokens=1,
            completion_tokens=1,
            cached_prompt_tokens=0,
            cost_usd=0.0,
        )
    )


def _ctx(provider: FakeLLMProvider, make_pedagogy_settings: Any, **ped: Any) -> SupportContext:
    return SupportContext(
        pedagogy=make_pedagogy_settings(**ped),
        generation_output_dir=Path("."),
        pedagogy_dir=Path("."),
        llm_provider=provider,
        prompts=PromptLoader(),
        artifacts=FsArtifactStore(),
        event_bus=EventBus[PedagogyEvent](),
        pause_token=PauseToken(),
        retry_policy=RetryPolicy(jitter=False),
    )


def test_key_points_generator(make_pedagogy_settings: Any) -> None:
    provider = _provider('{"points": ["Idée 1", "Idée 2"]}')
    artifact = KeyPointsGenerator().generate(
        _ctx(provider, make_pedagogy_settings),
        language=Language.FR, chapters=(_CHAPTER,), glossary=(),
    )
    assert isinstance(artifact.items[0], KeyPoints)
    assert artifact.items[0].points == ("Idée 1", "Idée 2")
    assert "Idée 1" in artifact.rendered_markdown
    assert artifact.correction_markdown is None


def test_flashcards_concepts_generator(make_pedagogy_settings: Any) -> None:
    provider = _provider('{"cards": [{"front": "Q1", "back": "R1"}]}')
    artifact = FlashcardsConceptsGenerator().generate(
        _ctx(provider, make_pedagogy_settings),
        language=Language.FR, chapters=(_CHAPTER,), glossary=(),
    )
    assert isinstance(artifact.items[0], Flashcard)
    assert artifact.items[0].front == "Q1"
    assert "Q1" in artifact.rendered_markdown


def test_revision_sheet_generator(make_pedagogy_settings: Any) -> None:
    provider = _provider('{"summary_markdown": "## Synthèse\\n- a"}')
    artifact = RevisionSheetGenerator().generate(
        _ctx(provider, make_pedagogy_settings),
        language=Language.FR, chapters=(_CHAPTER,), glossary=(),
    )
    assert isinstance(artifact.items[0], RevisionSheet)
    assert "Synthèse" in artifact.rendered_markdown


_QCM_JSON = (
    '{"questions": [{"question": "Q?", "choices": ["a", "b", "c", "d"], '
    '"correct_index": 0, "justification": "car a"}]}'
)


def test_qcm_generator_parses_and_balances(make_pedagogy_settings: Any) -> None:
    # 3 questions toutes correct_index=0 -> positions équilibrées 0,1,2.
    three = (
        '{"questions": ['
        '{"question": "Q1", "choices": ["a", "b", "c"], "correct_index": 0, "justification": "j"},'
        '{"question": "Q2", "choices": ["a", "b", "c"], "correct_index": 0, "justification": "j"},'
        '{"question": "Q3", "choices": ["a", "b", "c"], "correct_index": 0, "justification": "j"}'
        "]}"
    )
    provider = _provider(three)
    artifact = QcmGenerator().generate(
        _ctx(provider, make_pedagogy_settings),
        language=Language.FR, chapters=(_CHAPTER,), glossary=(),
    )
    assert all(isinstance(i, QcmItem) for i in artifact.items)
    indices = [i.correct_index for i in artifact.items if isinstance(i, QcmItem)]
    assert indices == [0, 1, 2]


def test_qcm_separate_correction(make_pedagogy_settings: Any) -> None:
    provider = _provider(_QCM_JSON)
    ctx = _ctx(
        provider,
        make_pedagogy_settings,
        selected_supports=frozenset({SupportType.QCM}),
        separate_correction=frozenset({SupportType.QCM}),
    )
    artifact = QcmGenerator().generate(
        ctx, language=Language.FR, chapters=(_CHAPTER,), glossary=()
    )
    assert artifact.correction_markdown is not None
    assert "Réponse" in artifact.correction_markdown
    assert "Réponse" not in artifact.rendered_markdown


def test_qcm_combined_when_not_separate(make_pedagogy_settings: Any) -> None:
    provider = _provider(_QCM_JSON)
    ctx = _ctx(
        provider,
        make_pedagogy_settings,
        selected_supports=frozenset({SupportType.QCM}),
        separate_correction=frozenset(),
    )
    artifact = QcmGenerator().generate(
        ctx, language=Language.FR, chapters=(_CHAPTER,), glossary=()
    )
    assert artifact.correction_markdown is None
    assert "Réponse" in artifact.rendered_markdown


def test_true_false_generator(make_pedagogy_settings: Any) -> None:
    provider = _provider(
        '{"items": [{"statement": "S", "is_true": true, "justification": "j"}]}'
    )
    artifact = TrueFalseGenerator().generate(
        _ctx(provider, make_pedagogy_settings),
        language=Language.FR, chapters=(_CHAPTER,), glossary=(),
    )
    assert isinstance(artifact.items[0], TrueFalseItem)
    assert artifact.items[0].is_true is True


def test_cloze_generator(make_pedagogy_settings: Any) -> None:
    provider = _provider('{"items": [{"text": "a ___", "answers": ["x"]}]}')
    artifact = ClozeGenerator().generate(
        _ctx(provider, make_pedagogy_settings),
        language=Language.FR, chapters=(_CHAPTER,), glossary=(),
    )
    assert isinstance(artifact.items[0], ClozeItem)
    assert artifact.items[0].answers == ("x",)


def test_open_questions_generator(make_pedagogy_settings: Any) -> None:
    provider = _provider(
        '{"questions": [{"question": "Q?", "expected_points": ["p1", "p2"]}]}'
    )
    artifact = OpenQuestionsGenerator().generate(
        _ctx(provider, make_pedagogy_settings),
        language=Language.FR, chapters=(_CHAPTER,), glossary=(),
    )
    assert isinstance(artifact.items[0], OpenQuestion)
    assert artifact.items[0].expected_points == ("p1", "p2")


_EXAM_JSON = (
    '{"title": "Examen", "sections": [{"title": "Partie 1", '
    '"statement_markdown": "Énoncé"}], "grading_markdown": "Barème : 20 pts"}'
)


def test_mock_exam_generator(make_pedagogy_settings: Any) -> None:
    provider = _provider(_EXAM_JSON)
    ctx = _ctx(
        provider,
        make_pedagogy_settings,
        selected_supports=frozenset({SupportType.MOCK_EXAM}),
        separate_correction=frozenset({SupportType.MOCK_EXAM}),
    )
    artifact = MockExamGenerator().generate(
        ctx, language=Language.FR, chapters=(_CHAPTER,), glossary=()
    )
    assert isinstance(artifact.items[0], MockExam)
    assert artifact.items[0].sections[0].title == "Partie 1"
    assert artifact.correction_markdown == "Barème : 20 pts"
    assert "Barème" not in artifact.rendered_markdown
