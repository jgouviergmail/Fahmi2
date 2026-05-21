"""Tests de la factory du registre des générateurs de supports."""

from __future__ import annotations

from fahmi2.domain.enums import SupportType
from fahmi2.pedagogy.default_registry import build_default_support_registry


def test_registry_covers_all_supports() -> None:
    registry = build_default_support_registry()
    for support_type in SupportType:
        assert registry.has(support_type)


def test_ordered_generators_count_and_order() -> None:
    registry = build_default_support_registry()
    ordered = registry.ordered_generators()
    assert len(ordered) == len(SupportType)
    assert [g.support_type for g in ordered] == list(
        build_default_support_registry().canonical_order()
    )


def test_uses_llm_flags() -> None:
    registry = build_default_support_registry()
    assert registry.get(SupportType.FLASHCARDS_GLOSSARY).uses_llm is False
    assert registry.get(SupportType.QCM).uses_llm is True
