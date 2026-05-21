"""Tests des entités de support de révision."""

from __future__ import annotations

import pytest

from fahmi2.domain.enums import Language, SupportType
from fahmi2.domain.supports import (
    ClozeItem,
    Flashcard,
    KeyPoints,
    MockExam,
    MockExamSection,
    OpenQuestion,
    QcmItem,
    RevisionSheet,
    SupportArtifact,
    TrueFalseItem,
)


def test_qcm_item_validates_correct_index() -> None:
    QcmItem(
        question="q", choices=("a", "b"), correct_index=1, justification="j",
        source_ref="r",
    )
    with pytest.raises(ValueError, match="correct_index"):
        QcmItem(
            question="q", choices=("a", "b"), correct_index=2, justification="j",
            source_ref="r",
        )


def test_qcm_item_requires_two_choices() -> None:
    with pytest.raises(ValueError, match="choices"):
        QcmItem(
            question="q", choices=("a",), correct_index=0, justification="j",
            source_ref="r",
        )


def test_qcm_item_rejects_too_many_choices() -> None:
    with pytest.raises(ValueError, match="at most"):
        QcmItem(
            question="q",
            choices=tuple(f"c{i}" for i in range(27)),
            correct_index=0,
            justification="j",
            source_ref="r",
        )


def test_cloze_item_requires_answers() -> None:
    with pytest.raises(ValueError, match="answers"):
        ClozeItem(text="a ___", answers=(), source_ref="r")


def test_other_entities_construct() -> None:
    assert TrueFalseItem(
        statement="s", is_true=True, justification="j", source_ref="r"
    ).is_true
    assert ClozeItem(text="a ___", answers=("x",), source_ref="r").answers == ("x",)
    assert OpenQuestion(
        question="q", expected_points=("p",), source_ref="r"
    ).question == "q"
    assert RevisionSheet(
        chapter_title="c", summary_markdown="m", source_ref="r"
    ).source_ref == "r"
    assert KeyPoints(chapter_title="c", points=("p1", "p2"), source_ref="r").points[
        0
    ] == "p1"
    exam = MockExam(
        title="t",
        sections=(MockExamSection(title="s1", statement_markdown="..."),),
        grading_markdown="bareme",
    )
    assert exam.sections[0].title == "s1"


def test_support_artifact_correction_default_none() -> None:
    artifact = SupportArtifact(
        support_type=SupportType.QCM,
        language=Language.FR,
        items=(),
        rendered_markdown="x",
    )
    assert artifact.correction_markdown is None


def test_flashcard_defaults() -> None:
    card = Flashcard(front="PIB", back="Produit intérieur brut", source_ref="PIB")
    assert card.tags == ()


def test_support_artifact_holds_items() -> None:
    card = Flashcard(front="X", back="def", source_ref="X", tags=("t",))
    artifact = SupportArtifact(
        support_type=SupportType.FLASHCARDS_GLOSSARY,
        language=Language.FR,
        items=(card,),
        rendered_markdown="# Flashcards",
        cost_usd=0.0,
    )
    stored = artifact.items[0]
    assert isinstance(stored, Flashcard)
    assert stored.front == "X"
    assert artifact.cost_usd == 0.0


def test_support_artifact_rejects_negative_cost() -> None:
    with pytest.raises(ValueError, match="cost_usd"):
        SupportArtifact(
            support_type=SupportType.FLASHCARDS_GLOSSARY,
            language=Language.FR,
            items=(),
            rendered_markdown="",
            cost_usd=-1.0,
        )
