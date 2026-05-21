"""Tests des enums de la fonctionnalité pédagogique."""

from __future__ import annotations

from fahmi2.domain.enums import (
    BloomObjective,
    ExportFormat,
    SupportDensity,
    SupportType,
    TargetAudience,
)


def test_support_type_has_eight_members() -> None:
    assert len(SupportType) == 8
    assert SupportType.FLASHCARDS_CONCEPTS in SupportType


def test_other_pedagogy_enums() -> None:
    assert BloomObjective.AUTO in BloomObjective
    assert TargetAudience.LICENCE in TargetAudience
    assert SupportDensity.STANDARD in SupportDensity
    assert ExportFormat.APKG in ExportFormat
