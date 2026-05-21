"""Tests des constantes/helpers de chemins de la fonctionnalité Génération."""

from __future__ import annotations

from fahmi2.domain.enums import Language
from fahmi2.domain.generation import (
    GENERATION_OUTPUT_SUBDIR,
    consolidated_doc_filename,
)


def test_output_subdir_constant() -> None:
    assert GENERATION_OUTPUT_SUBDIR == "output"


def test_consolidated_doc_filename() -> None:
    assert consolidated_doc_filename(Language.FR) == "consolidated.fr.md"
    assert consolidated_doc_filename(Language.EN) == "consolidated.en.md"
