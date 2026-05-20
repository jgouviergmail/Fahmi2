"""Tests des entités de support de révision."""

from __future__ import annotations

import pytest

from fahmi2.domain.enums import Language, SupportType
from fahmi2.domain.supports import Flashcard, SupportArtifact


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
    assert artifact.items[0].front == "X"
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
