"""Tests du registre de générateurs de supports."""

from __future__ import annotations

import pytest

from fahmi2.core.corpus import Chapter
from fahmi2.domain.enums import Language, SupportType
from fahmi2.domain.glossary import Term
from fahmi2.domain.supports import Flashcard, SupportArtifact
from fahmi2.pedagogy.support_generator import SupportContext, SupportGenerator
from fahmi2.pedagogy.support_registry import SupportGeneratorRegistry


class _FakeGen(SupportGenerator):
    @property
    def support_type(self) -> SupportType:
        return SupportType.FLASHCARDS_CONCEPTS

    @property
    def uses_llm(self) -> bool:
        return False

    def generate(
        self,
        ctx: SupportContext,
        *,
        language: Language,
        chapters: tuple[Chapter, ...],
        glossary: tuple[Term, ...],
    ) -> SupportArtifact:
        del ctx, chapters, glossary
        return SupportArtifact(
            support_type=self.support_type,
            language=language,
            items=(Flashcard(front="a", back="b", source_ref="a"),),
            rendered_markdown="x",
        )


def test_register_and_get() -> None:
    registry = SupportGeneratorRegistry([_FakeGen()])
    assert registry.has(SupportType.FLASHCARDS_CONCEPTS)
    assert registry.get(SupportType.FLASHCARDS_CONCEPTS).uses_llm is False


def test_duplicate_registration_raises() -> None:
    with pytest.raises(ValueError, match="already registered"):
        SupportGeneratorRegistry([_FakeGen(), _FakeGen()])


def test_get_unknown_raises_key_error() -> None:
    registry = SupportGeneratorRegistry()
    with pytest.raises(KeyError):
        registry.get(SupportType.QCM)


def test_canonical_order_has_eight_supports() -> None:
    assert len(SupportGeneratorRegistry.canonical_order()) == 8
    assert (
        SupportGeneratorRegistry.canonical_order()[0]
        is SupportType.FLASHCARDS_CONCEPTS
    )


def test_ordered_generators_follows_canonical_order() -> None:
    registry = SupportGeneratorRegistry([_FakeGen()])
    ordered = registry.ordered_generators()
    assert [g.support_type for g in ordered] == [SupportType.FLASHCARDS_CONCEPTS]
