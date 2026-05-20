"""Smoke tests : les 8 prompts pédagogie bundlés se rendent sans erreur."""

from __future__ import annotations

import pytest

from fahmi2.infra.prompts.loader import PromptLoader

_PEDAGOGY_TEMPLATES = [
    "pedagogy_flashcards_concepts",
    "pedagogy_qcm",
    "pedagogy_true_false",
    "pedagogy_cloze",
    "pedagogy_open_questions",
    "pedagogy_revision_sheet",
    "pedagogy_key_points",
    "pedagogy_mock_exam",
]

# Sur-ensemble des variables : un template qui n'en utilise pas une l'ignore.
_SAMPLE_CONTEXT = {
    "output_language_label": "français",
    "audience_label": "licence",
    "bloom_label": "comprendre et appliquer",
    "density_label": "standard",
    "pedagogy_directives": "Insister sur les exemples.",
    "glossary_terms": "- PIB (PIB) : Produit intérieur brut",
    "chapter_title": "Bases",
    "chapter_markdown": "Contenu du chapitre.",
    "consolidated_markdown": "# 1. Bases\n\nContenu.",
}


@pytest.mark.parametrize("name", _PEDAGOGY_TEMPLATES)
def test_pedagogy_prompt_renders(name: str) -> None:
    rendered = PromptLoader().render(name, **_SAMPLE_CONTEXT)
    assert rendered.strip()
    assert "JSON" in rendered


@pytest.mark.parametrize("name", _PEDAGOGY_TEMPLATES)
def test_pedagogy_prompt_renders_without_directives(name: str) -> None:
    context = {**_SAMPLE_CONTEXT, "pedagogy_directives": "", "glossary_terms": ""}
    rendered = PromptLoader().render(name, **context)
    assert rendered.strip()
