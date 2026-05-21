"""Factory du registre des générateurs de supports (les 8 supports)."""

from __future__ import annotations

from fahmi2.pedagogy.generators.cloze import ClozeGenerator
from fahmi2.pedagogy.generators.flashcards_concepts import FlashcardsConceptsGenerator
from fahmi2.pedagogy.generators.key_points import KeyPointsGenerator
from fahmi2.pedagogy.generators.mock_exam import MockExamGenerator
from fahmi2.pedagogy.generators.open_questions import OpenQuestionsGenerator
from fahmi2.pedagogy.generators.qcm import QcmGenerator
from fahmi2.pedagogy.generators.revision_sheet import RevisionSheetGenerator
from fahmi2.pedagogy.generators.true_false import TrueFalseGenerator
from fahmi2.pedagogy.support_registry import SupportGeneratorRegistry


def build_default_support_registry() -> SupportGeneratorRegistry:
    """Construit le registre avec les 8 générateurs de supports (tous LLM).

    Returns:
        Un ``SupportGeneratorRegistry`` peuplé.
    """
    return SupportGeneratorRegistry(
        [
            FlashcardsConceptsGenerator(),
            QcmGenerator(),
            TrueFalseGenerator(),
            ClozeGenerator(),
            OpenQuestionsGenerator(),
            RevisionSheetGenerator(),
            KeyPointsGenerator(),
            MockExamGenerator(),
        ]
    )
